"""Assina um arquivo JSON com WEBHOOK_SECRET e envia para a API (uso local/demonstração).

Uso: python scripts/send_event.py examples/pedido-novo.json [--url http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--url", default=os.environ.get("TRIAGE_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--bad-signature", action="store_true", help="envia assinatura incorreta")
    args = parser.parse_args()
    secret = os.environ.get("WEBHOOK_SECRET")
    if not secret:
        print("Defina WEBHOOK_SECRET no ambiente.", file=sys.stderr)
        return 2
    body = Path(args.file).read_bytes()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if args.bad_signature:
        signature = "sha256=" + "0" * 64
    resp = httpx.post(
        f"{args.url}/webhooks/pedidos",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature-256": signature},
    )
    print(resp.status_code, json.dumps(resp.json(), ensure_ascii=False))
    return 0 if resp.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
