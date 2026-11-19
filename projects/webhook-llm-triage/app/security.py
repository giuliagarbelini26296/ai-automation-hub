"""Assinatura HMAC-SHA256 do corpo bruto da requisição (estilo X-Hub-Signature-256)."""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Signature-256"


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(secret: str, body: bytes, header_value: str | None) -> bool:
    if not header_value or not header_value.startswith("sha256="):
        return False
    return hmac.compare_digest(sign(secret, body), header_value.strip())
