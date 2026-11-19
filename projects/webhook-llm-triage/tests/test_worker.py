from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import OpenAICompatibleLLM, RuleBasedLLM, TransientLLMError
from app.main import create_app
from app.models import Triage, WebhookEvent
from app.store import EventStore
from app.worker import Worker

from .conftest import SECRET, example, post_event

RPA_READER = Path(__file__).resolve().parents[2] / "rpa-pedidos" / "ler_csv.py"


class FakeClock:
    def __init__(self) -> None:
        self.t = 1_000_000.0

    def __call__(self) -> float:
        return self.t


class FlakyProvider:
    """Falha de forma transitória nas primeiras `failures` chamadas."""

    name = "flaky"

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def classify(self, event: WebhookEvent) -> Triage:
        self.calls += 1
        if self.calls <= self.failures:
            raise TransientLLMError("HTTP 503 do provedor de LLM")
        return RuleBasedLLM().classify(event)


def _enqueue(store: EventStore, name: str) -> str:
    ev = WebhookEvent.model_validate(example(name))
    row, _ = store.enqueue(ev.event_id, "h", ev.type, ev.model_dump(mode="json"), now=0)
    return row.id


def test_worker_success_with_rpa_handoff(client, app, settings):
    queue_id = post_event(client, example("pedido-novo.json")).json()["id"]
    row = app.state.worker.process_one()
    assert row.id == queue_id and row.status == "done" and row.attempts == 1
    assert row.result == {
        "category": "new_order",
        "priority": "low",
        "summary": "Novo pedido PED-0101 de Fornecedor Horizonte Fictício, valor R$ 890.00.",
        "suggested_action": "send_to_rpa",
    }
    csv_text = Path(row.handoff_file).read_text(encoding="utf-8")
    assert csv_text == (
        "pedido;fornecedor;email;valor\n"
        "PED-0101;Fornecedor Horizonte Fictício;contato@horizonte.example;890,00\n"
    )
    public = client.get(f"/events/{queue_id}").json()
    assert public["triage"]["suggested_action"] == "send_to_rpa"
    stats = client.get("/stats").json()
    assert stats["by_status"]["done"] == 1 and stats["rpa_handoffs"] == 1
    assert app.state.worker.process_one() is None


@pytest.mark.skipif(not RPA_READER.exists(), reason="rpa-pedidos não está ao lado deste projeto")
def test_handoff_csv_is_accepted_by_rpa_pedidos_reader(client, app):
    post_event(client, example("pedido-novo.json"))
    row = app.state.worker.process_one()
    out = subprocess.run(
        [sys.executable, str(RPA_READER), row.handoff_file],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"pedido": "PED-0101"' in out.stdout and '"valor": "890,00"' in out.stdout


def test_support_messages_are_not_sent_to_rpa(client, app):
    post_event(client, example("suporte-reembolso.json"))
    row = app.state.worker.process_one()
    assert row.result["category"] == "refund"
    assert row.result["suggested_action"] == "escalate_human"
    assert row.handoff_file is None


def test_retry_with_backoff_then_success(tmp_path):
    store, clock = EventStore(str(tmp_path / "q.sqlite3")), FakeClock()
    provider = FlakyProvider(failures=1)
    worker = Worker(store, provider, max_attempts=3, backoff_base_s=2.0, clock=clock, rng=lambda: 1.0)
    queue_id = _enqueue(store, "suporte-atraso.json")

    row = worker.process_one()
    assert row.status == "queued" and row.attempts == 1
    assert "503" in row.last_error
    assert row.next_attempt_at == pytest.approx(clock.t + 2.0)  # 2*2^0 com jitter máximo
    assert worker.process_one() is None  # ainda dentro do backoff

    clock.t += 2.0
    row = worker.process_one()
    assert row.id == queue_id and row.status == "done" and row.attempts == 2
    assert row.result["category"] == "delivery_issue"
    assert provider.calls == 2


def test_backoff_is_exponential_with_jitter_and_capped(tmp_path):
    store = EventStore(str(tmp_path / "q.sqlite3"))
    lo = Worker(store, RuleBasedLLM(), backoff_base_s=2, backoff_max_s=30, rng=lambda: 0.0)
    hi = Worker(store, RuleBasedLLM(), backoff_base_s=2, backoff_max_s=30, rng=lambda: 1.0)
    assert [lo.backoff_delay(a) for a in (1, 2, 3, 4, 5, 6)] == [1, 2, 4, 8, 15, 15]
    assert [hi.backoff_delay(a) for a in (1, 2, 3, 4, 5, 6)] == [2, 4, 8, 16, 30, 30]


def test_dead_letter_after_max_attempts(tmp_path):
    store, clock = EventStore(str(tmp_path / "q.sqlite3")), FakeClock()
    worker = Worker(store, FlakyProvider(failures=99), max_attempts=3, clock=clock)
    queue_id = _enqueue(store, "suporte-atraso.json")
    for _ in range(3):
        clock.t += 1_000
        row = worker.process_one()
    assert row.id == queue_id and row.status == "dead_letter" and row.attempts == 3
    assert "TransientLLMError" in row.last_error
    clock.t += 1_000
    assert worker.process_one() is None
    assert store.stats()["by_status"]["dead_letter"] == 1


def _openai_transport(content: str | None = None, status: int = 200, seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if status != 200:
            return httpx.Response(status, json={"error": "x"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler)


def test_llm_valid_structured_output_is_used(tmp_path):
    seen: list[httpx.Request] = []
    content = (
        '{"category": "delivery_issue", "priority": "medium", '
        '"summary": "Cliente relata atraso.", "suggested_action": "reply_customer"}'
    )
    llm = OpenAICompatibleLLM(
        "http://llm.test/v1", "chave-falsa", "modelo-x", transport=_openai_transport(content, seen=seen)
    )
    store = EventStore(str(tmp_path / "q.sqlite3"))
    _enqueue(store, "suporte-atraso.json")
    row = Worker(store, llm).process_one()
    assert row.status == "done" and row.fallback_used is False
    assert row.llm_provider == "openai-compatible:modelo-x"
    sent = seen[0]
    assert sent.url.path == "/v1/chat/completions"
    fmt = __import__("json").loads(sent.content)["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True


@pytest.mark.parametrize(
    "content",
    [
        "isto não é JSON",
        '{"category": "urgente_demais", "priority": "high", "summary": "x", "suggested_action": "no_action"}',
        '{"category": "question", "priority": "low", "summary": "x", "suggested_action": "no_action", '
        '"extra": 1}',
        '{"category": "question", "priority": "low", "suggested_action": "no_action"}',
    ],
)
def test_llm_output_validation_failure_falls_back_to_rules(tmp_path, content):
    llm = OpenAICompatibleLLM("http://llm.test/v1", "", "modelo-x", transport=_openai_transport(content))
    store = EventStore(str(tmp_path / "q.sqlite3"))
    _enqueue(store, "suporte-atraso.json")
    row = Worker(store, llm).process_one()
    assert row.status == "done" and row.fallback_used is True
    assert row.llm_provider == "fake-rules"
    assert row.result["category"] == "delivery_issue"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_llm_transient_http_errors_raise_transient(status):
    llm = OpenAICompatibleLLM("http://llm.test/v1", "", "m", transport=_openai_transport(status=status))
    with pytest.raises(TransientLLMError):
        llm.classify(WebhookEvent.model_validate(example("suporte-atraso.json")))


def test_llm_timeout_is_transient():
    def handler(request):
        raise httpx.ReadTimeout("timeout simulado", request=request)

    llm = OpenAICompatibleLLM("http://llm.test/v1", "", "m", transport=httpx.MockTransport(handler))
    with pytest.raises(TransientLLMError):
        llm.classify(WebhookEvent.model_validate(example("suporte-atraso.json")))


def test_recover_processing_requeues_after_crash(tmp_path):
    store = EventStore(str(tmp_path / "q.sqlite3"))
    _enqueue(store, "suporte-atraso.json")
    assert store.claim_next(now=10).status == "processing"
    assert store.recover_processing() == 1
    assert store.claim_next(now=10).attempts == 2


def test_background_worker_end_to_end(tmp_path):
    settings = Settings(
        webhook_secret=SECRET, db_path=str(tmp_path / "e2e.sqlite3"), worker_enabled=True, worker_poll_s=0.05
    )
    with TestClient(create_app(settings)) as client:
        queue_id = post_event(client, example("suporte-reembolso.json")).json()["id"]
        deadline = time.time() + 5
        while time.time() < deadline:
            event = client.get(f"/events/{queue_id}").json()
            if event["status"] == "done":
                break
            time.sleep(0.05)
    assert event["status"] == "done"
    assert event["triage"]["category"] == "refund"
