from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import sign

SECRET = "segredo-de-teste-local-123456"
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def post_event(client: TestClient, payload: dict | bytes, secret: str = SECRET, headers: dict | None = None):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    h = {"Content-Type": "application/json", "X-Signature-256": sign(secret, body)}
    h.update(headers or {})
    return client.post("/webhooks/pedidos", content=body, headers=h)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        webhook_secret=SECRET,
        db_path=str(tmp_path / "t.sqlite3"),
        worker_enabled=False,
        max_attempts=3,
        backoff_base_s=2.0,
        rpa_handoff_dir=str(tmp_path / "handoff"),
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c
