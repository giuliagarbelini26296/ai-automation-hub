"""Worker: consome a fila, chama o LLM, aplica retry com backoff exponencial + jitter e dead-letter."""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable

from .handoff import write_job
from .llm import LLMOutputError, LLMProvider, RuleBasedLLM, TransientLLMError
from .logging_setup import log
from .models import Triage, WebhookEvent
from .store import EventRow, EventStore

logger = logging.getLogger("triage.worker")


class Worker:
    def __init__(
        self,
        store: EventStore,
        provider: LLMProvider,
        *,
        max_attempts: int = 5,
        backoff_base_s: float = 2.0,
        backoff_max_s: float = 300.0,
        rpa_handoff_dir: str = "",
        fallback: LLMProvider | None = None,
        clock: Callable[[], float] = time.time,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.store = store
        self.provider = provider
        self.fallback = fallback or RuleBasedLLM()
        self.max_attempts = max_attempts
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self.rpa_handoff_dir = rpa_handoff_dir
        self.clock = clock
        self.rng = rng

    def backoff_delay(self, attempt: int) -> float:
        """Backoff exponencial com 'equal jitter': metade fixa + metade aleatória."""
        cap = min(self.backoff_max_s, self.backoff_base_s * 2 ** (attempt - 1))
        return cap / 2 + self.rng() * cap / 2

    def _triage(self, event: WebhookEvent) -> tuple[Triage, str, bool]:
        try:
            return self.provider.classify(event), self.provider.name, False
        except LLMOutputError as exc:
            if self.provider is self.fallback:
                raise
            log(
                logger,
                "llm_output_invalid_fallback",
                logging.WARNING,
                event_id=event.event_id,
                provider=self.provider.name,
                error=str(exc)[:300],
            )
            return self.fallback.classify(event), self.fallback.name, True

    def process_one(self) -> EventRow | None:
        row = self.store.claim_next(self.clock())
        if row is None:
            return None
        fields = {"queue_id": row.id, "attempt": row.attempts, "event_type": row.event_type}
        try:
            event = WebhookEvent.model_validate(row.payload)
            triage, provider, fallback_used = self._triage(event)
            handoff = None
            if self.rpa_handoff_dir and triage.suggested_action == "send_to_rpa" and event.order:
                handoff = write_job(self.rpa_handoff_dir, event.event_id, event.order)
            self.store.mark_done(row.id, triage.model_dump(), provider, fallback_used, handoff)
            log(
                logger,
                "event_processed",
                **fields,
                provider=provider,
                fallback_used=fallback_used,
                category=triage.category,
                priority=triage.priority,
                action=triage.suggested_action,
                rpa_handoff=bool(handoff),
            )
        except (TransientLLMError, OSError) as exc:
            error = f"{type(exc).__name__}: {exc}"[:500]
            if row.attempts >= self.max_attempts:
                self.store.mark_dead_letter(row.id, error)
                log(logger, "event_dead_letter", logging.ERROR, **fields, error=error)
            else:
                delay = self.backoff_delay(row.attempts)
                self.store.mark_retry(row.id, error, self.clock() + delay)
                log(
                    logger,
                    "event_retry_scheduled",
                    logging.WARNING,
                    **fields,
                    error=error,
                    retry_in_s=round(delay, 3),
                )
        except Exception as exc:  # erro permanente (ex.: bug ou payload antigo inválido)
            error = f"permanent {type(exc).__name__}: {exc}"[:500]
            self.store.mark_dead_letter(row.id, error)
            log(logger, "event_dead_letter", logging.ERROR, **fields, error=error)
        return self.store.get(row.id)

    def run_forever(self, stop: threading.Event, poll_s: float = 1.0) -> None:
        recovered = self.store.recover_processing()
        log(logger, "worker_started", provider=self.provider.name, recovered=recovered)
        while not stop.is_set():
            try:
                if self.process_one() is None:
                    stop.wait(poll_s)
            except Exception:  # não deixa a thread morrer por erro de infraestrutura
                logger.exception("worker_loop_error")
                stop.wait(poll_s)
        log(logger, "worker_stopped")
