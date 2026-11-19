"""API FastAPI. Rodar com: uvicorn --factory app.main:create_app"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import security
from .config import Settings
from .llm import LLMProvider, build_provider
from .logging_setup import configure, log
from .models import WebhookEvent
from .store import EventStore, IdempotencyConflict
from .worker import Worker

logger = logging.getLogger("triage.api")


def _error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def _validation_details(exc: ValidationError) -> list[dict]:
    return [
        {
            "field": ".".join(str(p) for p in err["loc"]) or "(body)",
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors(include_url=False, include_input=False)
    ]


def create_app(settings: Settings | None = None, provider: LLMProvider | None = None) -> FastAPI:
    configure()
    settings = settings or Settings.from_env()
    store = EventStore(settings.db_path)
    provider = provider or build_provider(
        settings.llm_provider,
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
        settings.llm_timeout_s,
    )
    worker = Worker(
        store,
        provider,
        max_attempts=settings.max_attempts,
        backoff_base_s=settings.backoff_base_s,
        backoff_max_s=settings.backoff_max_s,
        rpa_handoff_dir=settings.rpa_handoff_dir,
    )
    counters: Counter[str] = Counter()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop = threading.Event()
        thread = None
        if settings.worker_enabled:
            thread = threading.Thread(
                target=worker.run_forever,
                args=(stop, settings.worker_poll_s),
                name="triage-worker",
                daemon=True,
            )
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=10)

    app = FastAPI(title="webhook-llm-triage", version="0.1.0", lifespan=lifespan)
    app.state.settings, app.state.store, app.state.worker = settings, store, worker

    @app.post("/webhooks/pedidos", status_code=202)
    async def receive(request: Request):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > settings.max_body_bytes:
            counters["rejected_too_large"] += 1
            return _error(413, "payload_too_large", "Corpo acima do limite configurado.")
        raw = await request.body()
        if len(raw) > settings.max_body_bytes:
            counters["rejected_too_large"] += 1
            return _error(413, "payload_too_large", "Corpo acima do limite configurado.")
        if not security.verify(settings.webhook_secret, raw, request.headers.get(security.SIGNATURE_HEADER)):
            counters["rejected_signature"] += 1
            log(logger, "webhook_rejected", logging.WARNING, reason="invalid_signature")
            return _error(
                401, "invalid_signature", f"Cabeçalho {security.SIGNATURE_HEADER} ausente ou inválido."
            )
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            counters["rejected_validation"] += 1
            return _error(415, "unsupported_media_type", "Envie Content-Type: application/json.")
        try:
            event = WebhookEvent.model_validate_json(raw)
        except ValidationError as exc:
            details = _validation_details(exc)
            malformed = any(d["type"] == "json_invalid" for d in details)
            counters["rejected_validation"] += 1
            log(
                logger,
                "webhook_rejected",
                logging.WARNING,
                reason="validation",
                fields_with_error=[d["field"] for d in details],
            )
            if malformed:
                return _error(400, "malformed_json", "Corpo não é um JSON válido.", details)
            return _error(422, "validation_error", "Evento inválido.", details)

        key = request.headers.get("Idempotency-Key") or event.event_id
        if not 8 <= len(key) <= 128:
            counters["rejected_validation"] += 1
            return _error(422, "validation_error", "Idempotency-Key deve ter de 8 a 128 caracteres.")
        payload = event.model_dump(mode="json")
        digest = hashlib.sha256(event.model_dump_json().encode()).hexdigest()
        try:
            row, created = store.enqueue(key, digest, event.type, payload)
        except IdempotencyConflict:
            counters["rejected_idempotency_conflict"] += 1
            return _error(
                409, "idempotency_conflict", "Esta chave de idempotência já foi usada com outro conteúdo."
            )
        counters["accepted" if created else "duplicates"] += 1
        log(
            logger,
            "webhook_accepted" if created else "webhook_duplicate",
            queue_id=row.id,
            event_id=event.event_id,
            event_type=event.type,
        )
        body = {
            "id": row.id,
            "status": row.status,
            "duplicate": not created,
            "status_url": f"/events/{row.id}",
        }
        return JSONResponse(status_code=202 if created else 200, content=body)

    @app.get("/events/{event_id}")
    def get_event(event_id: str):
        row = store.get(event_id)
        if row is None:
            return _error(404, "not_found", "Evento não encontrado.")
        return row.public()

    @app.get("/stats")
    def stats():
        return {**store.stats(), "webhook_since_start": dict(counters), "llm_provider": provider.name}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app
