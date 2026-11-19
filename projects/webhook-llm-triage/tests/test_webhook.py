from __future__ import annotations

import json

from app.security import sign, verify

from .conftest import SECRET, example, post_event


def test_valid_signature_is_accepted_and_queued(client):
    resp = post_event(client, example("pedido-novo.json"))
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued" and body["duplicate"] is False
    assert client.get(body["status_url"]).json()["status"] == "queued"


def test_invalid_or_missing_signature_is_rejected(client):
    payload = example("pedido-novo.json")
    assert post_event(client, payload, secret="outro-segredo-qualquer-123").status_code == 401
    raw = json.dumps(payload).encode()
    resp = client.post("/webhooks/pedidos", content=raw, headers={"Content-Type": "application/json"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_signature"
    # corpo alterado depois de assinado
    tampered = raw.replace(b"890.00", b"990.00")
    resp = client.post(
        "/webhooks/pedidos",
        content=tampered,
        headers={"Content-Type": "application/json", "X-Signature-256": sign(SECRET, raw)},
    )
    assert resp.status_code == 401
    assert client.get("/stats").json()["events_total"] == 0


def test_verify_uses_prefix_and_constant_time_compare():
    assert verify(SECRET, b"{}", sign(SECRET, b"{}"))
    assert not verify(SECRET, b"{}", sign(SECRET, b"{}").removeprefix("sha256="))
    assert not verify(SECRET, b"{}", None)


def test_validation_errors_are_clear_4xx(client):
    resp = post_event(client, example("invalido.json"))
    assert resp.status_code == 422
    fields = {d["field"] for d in resp.json()["error"]["details"]}
    assert {"customer.email", "order.order_id", "order.amount"} <= fields

    resp = post_event(client, b'{"event_id": "evt_quebrado"')
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "malformed_json"

    missing_order = {**example("pedido-novo.json"), "order": None}
    resp = post_event(client, missing_order)
    assert resp.status_code == 422
    assert "order" in resp.json()["error"]["details"][0]["message"]

    extra = {**example("pedido-novo.json"), "campo_extra": 1}
    assert post_event(client, extra).status_code == 422

    resp = post_event(client, example("pedido-novo.json"), headers={"Content-Type": "text/plain"})
    assert resp.status_code == 415


def test_body_size_limit(client, settings):
    big = b"{" + b" " * (settings.max_body_bytes + 1) + b"}"
    assert post_event(client, big).status_code == 413


def test_idempotency_dedupes_same_event(client):
    payload = example("pedido-novo.json")
    first = post_event(client, payload)
    second = post_event(client, payload)
    assert first.status_code == 202 and second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    stats = client.get("/stats").json()
    assert stats["events_total"] == 1
    assert stats["webhook_since_start"]["duplicates"] == 1


def test_idempotency_key_header_conflict_returns_409(client):
    a = example("pedido-novo.json")
    b = {**a, "event_id": "evt_outro_evento_99"}
    headers = {"Idempotency-Key": "chave-fixa-0001"}
    assert post_event(client, a, headers=headers).status_code == 202
    resp = post_event(client, b, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "idempotency_conflict"


def test_unknown_event_returns_404(client):
    assert client.get("/events/evq_inexistente").status_code == 404
