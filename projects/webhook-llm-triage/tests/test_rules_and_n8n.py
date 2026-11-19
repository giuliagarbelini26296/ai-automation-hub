from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.llm import RuleBasedLLM
from app.models import WebhookEvent

from .conftest import example

N8N = Path(__file__).resolve().parent.parent / "n8n" / "webhook-llm-triage.json"


def _event(message: str) -> WebhookEvent:
    return WebhookEvent.model_validate({**example("suporte-atraso.json"), "message": message})


@pytest.mark.parametrize(
    ("message", "category", "action"),
    [
        ("Quero cancelar meu pedido", "cancellation", "escalate_human"),
        ("Fui cobrado duas vezes", "refund", "escalate_human"),
        ("Meu pedido está atrasado", "delivery_issue", "reply_customer"),
        ("Preciso alterar o endereço", "order_change", "reply_customer"),
        ("Qual o prazo de garantia?", "question", "reply_customer"),
        ("Bom dia", "other", "escalate_human"),
    ],
)
def test_rule_based_classifier(message, category, action):
    result = RuleBasedLLM().classify(_event(message))
    assert (result.category, result.suggested_action) == (category, action)


def test_high_value_order_goes_to_human():
    data = example("pedido-novo.json")
    data["order"]["amount"] = "15000.00"
    result = RuleBasedLLM().classify(WebhookEvent.model_validate(data))
    assert result.priority == "high" and result.suggested_action == "escalate_human"


def test_n8n_workflow_structure():
    wf = json.loads(N8N.read_text(encoding="utf-8"))
    nodes = {n["name"]: n for n in wf["nodes"]}
    types = [n["type"] for n in wf["nodes"]]
    assert types.count("n8n-nodes-base.webhook") == 1
    for t in ("n8n-nodes-base.crypto", "n8n-nodes-base.httpRequest", "n8n-nodes-base.if"):
        assert t in types
    assert types.count("n8n-nodes-base.set") == 2
    assert len({n["id"] for n in wf["nodes"]}) == len(wf["nodes"])
    for n in wf["nodes"]:
        assert {"parameters", "name", "type", "typeVersion", "position"} <= n.keys()

    # conexões apontam para nós existentes e formam Webhook -> Crypto -> HTTP -> IF -> 2x Set
    for source, conn in wf["connections"].items():
        assert source in nodes
        for branch in conn["main"]:
            for target in branch:
                assert target["node"] in nodes
    chain = ["Webhook", "Assinar HMAC", "Enviar para Triage API", "Aceito?"]
    for a, b in zip(chain, chain[1:], strict=False):
        assert wf["connections"][a]["main"][0][0]["node"] == b
    assert len(wf["connections"]["Aceito?"]["main"]) == 2

    http = nodes["Enviar para Triage API"]["parameters"]
    assert http["method"] == "POST" and http["url"].endswith("/webhooks/pedidos")
    header = http["headerParameters"]["parameters"][0]
    assert header["name"] == "X-Signature-256"
    # o corpo assinado e o corpo enviado usam a mesma expressão
    assert http["body"] == nodes["Assinar HMAC"]["parameters"]["value"]
    # nenhum segredo literal no arquivo
    assert "$env.WEBHOOK_SECRET" in nodes["Assinar HMAC"]["parameters"]["secret"]
    assert "segredo" not in N8N.read_text(encoding="utf-8").lower()
