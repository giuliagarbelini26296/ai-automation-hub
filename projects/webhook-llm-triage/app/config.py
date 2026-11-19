"""Configuração lida de variáveis de ambiente (veja .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    webhook_secret: str
    db_path: str = "data/triage.sqlite3"
    llm_provider: str = "fake"  # "fake" (regras determinísticas) ou "openai" (API compatível)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_s: float = 20.0
    max_attempts: int = 5
    backoff_base_s: float = 2.0
    backoff_max_s: float = 300.0
    worker_enabled: bool = True
    worker_poll_s: float = 1.0
    rpa_handoff_dir: str = ""  # vazio = hand-off desativado
    max_body_bytes: int = 64_000

    def __post_init__(self) -> None:
        if len(self.webhook_secret) < 16:
            raise ValueError("WEBHOOK_SECRET deve ter pelo menos 16 caracteres.")
        if self.llm_provider not in {"fake", "openai"}:
            raise ValueError("LLM_PROVIDER deve ser 'fake' ou 'openai'.")
        if self.max_attempts < 1:
            raise ValueError("MAX_ATTEMPTS deve ser >= 1.")

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        secret = env.get("WEBHOOK_SECRET", "")
        if not secret:
            raise RuntimeError("Defina WEBHOOK_SECRET (veja .env.example).")
        return cls(
            webhook_secret=secret,
            db_path=env.get("DB_PATH", cls.db_path),
            llm_provider=env.get("LLM_PROVIDER", cls.llm_provider),
            llm_base_url=env.get("LLM_BASE_URL", cls.llm_base_url),
            llm_api_key=env.get("LLM_API_KEY", ""),
            llm_model=env.get("LLM_MODEL", cls.llm_model),
            llm_timeout_s=float(env.get("LLM_TIMEOUT_S", cls.llm_timeout_s)),
            max_attempts=int(env.get("MAX_ATTEMPTS", cls.max_attempts)),
            backoff_base_s=float(env.get("BACKOFF_BASE_S", cls.backoff_base_s)),
            backoff_max_s=float(env.get("BACKOFF_MAX_S", cls.backoff_max_s)),
            worker_enabled=_bool(env.get("WORKER_ENABLED"), True),
            worker_poll_s=float(env.get("WORKER_POLL_S", cls.worker_poll_s)),
            rpa_handoff_dir=env.get("RPA_HANDOFF_DIR", ""),
            max_body_bytes=int(env.get("MAX_BODY_BYTES", cls.max_body_bytes)),
        )
