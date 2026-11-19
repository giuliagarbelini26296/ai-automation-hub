"""Fila persistente em SQLite: deduplicação por chave de idempotência, estados e dead-letter."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_sha256 TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'done', 'dead_letter')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL NOT NULL,
    last_error TEXT,
    result TEXT,
    llm_provider TEXT,
    fallback_used INTEGER,
    handoff_file TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ready ON events (status, next_attempt_at);
"""


UPDATABLE = {
    "status",
    "result",
    "llm_provider",
    "fallback_used",
    "handoff_file",
    "last_error",
    "next_attempt_at",
    "updated_at",
}


class IdempotencyConflict(Exception):
    """Mesma chave de idempotência com conteúdo diferente."""


@dataclass
class EventRow:
    id: str
    idempotency_key: str
    event_type: str
    payload: dict
    status: str
    attempts: int
    next_attempt_at: float
    last_error: str | None
    result: dict | None
    llm_provider: str | None
    fallback_used: bool | None
    handoff_file: str | None
    created_at: str
    updated_at: str

    def public(self) -> dict:
        return {
            "id": self.id,
            "idempotency_key": self.idempotency_key,
            "event_type": self.event_type,
            "status": self.status,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "triage": self.result,
            "llm_provider": self.llm_provider,
            "fallback_used": self.fallback_used,
            "rpa_handoff_file": self.handoff_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "payload": self.payload,
        }


def _iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class EventStore:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _row(r: sqlite3.Row | None) -> EventRow | None:
        if r is None:
            return None
        return EventRow(
            id=r["id"],
            idempotency_key=r["idempotency_key"],
            event_type=r["event_type"],
            payload=json.loads(r["payload"]),
            status=r["status"],
            attempts=r["attempts"],
            next_attempt_at=r["next_attempt_at"],
            last_error=r["last_error"],
            result=json.loads(r["result"]) if r["result"] else None,
            llm_provider=r["llm_provider"],
            fallback_used=None if r["fallback_used"] is None else bool(r["fallback_used"]),
            handoff_file=r["handoff_file"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def enqueue(
        self, key: str, payload_sha256: str, event_type: str, payload: dict, now: float | None = None
    ) -> tuple[EventRow, bool]:
        """Retorna (evento, criado). Se a chave já existe com o mesmo conteúdo, criado=False."""
        now = time.time() if now is None else now
        ts = _iso()
        with self._conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute("SELECT * FROM events WHERE idempotency_key = ?", (key,)).fetchone()
                if existing:
                    db.execute("COMMIT")
                    if existing["payload_sha256"] != payload_sha256:
                        raise IdempotencyConflict(key)
                    return self._row(existing), False  # type: ignore[return-value]
                event_id = "evq_" + uuid.uuid4().hex[:16]
                db.execute(
                    "INSERT INTO events (id, idempotency_key, payload_sha256, event_type, payload,"
                    " status, attempts, next_attempt_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?)",
                    (
                        event_id,
                        key,
                        payload_sha256,
                        event_type,
                        json.dumps(payload, ensure_ascii=False),
                        now,
                        ts,
                        ts,
                    ),
                )
                db.execute("COMMIT")
            except IdempotencyConflict:
                raise
            except Exception:
                db.execute("ROLLBACK")
                raise
        return self.get(event_id), True  # type: ignore[return-value]

    def get(self, event_id: str) -> EventRow | None:
        with self._conn() as db:
            return self._row(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())

    def claim_next(self, now: float | None = None) -> EventRow | None:
        """Pega o próximo evento pronto e marca como 'processing' (transação exclusiva)."""
        now = time.time() if now is None else now
        with self._conn() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM events WHERE status = 'queued' AND next_attempt_at <= ?"
                " ORDER BY next_attempt_at, created_at LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                db.execute("COMMIT")
                return None
            db.execute(
                "UPDATE events SET status = 'processing', attempts = attempts + 1, updated_at = ?"
                " WHERE id = ?",
                (_iso(), row["id"]),
            )
            db.execute("COMMIT")
        return self.get(row["id"])

    def _update(self, event_id: str, **fields: object) -> None:
        fields["updated_at"] = _iso()
        unknown = set(fields) - UPDATABLE
        if unknown:
            raise ValueError(f"Colunas não permitidas: {unknown}")
        # Nomes de coluna vêm só da allowlist acima; valores vão como parâmetros.
        cols = ", ".join(f"{k} = ?" for k in fields)
        sql = f"UPDATE events SET {cols} WHERE id = ?"  # noqa: S608
        with self._conn() as db:
            db.execute(sql, (*fields.values(), event_id))

    def mark_done(
        self, event_id: str, result: dict, provider: str, fallback_used: bool, handoff: str | None
    ) -> None:
        self._update(
            event_id,
            status="done",
            result=json.dumps(result, ensure_ascii=False),
            llm_provider=provider,
            fallback_used=int(fallback_used),
            handoff_file=handoff,
            last_error=None,
        )

    def mark_retry(self, event_id: str, error: str, next_attempt_at: float) -> None:
        self._update(event_id, status="queued", last_error=error, next_attempt_at=next_attempt_at)

    def mark_dead_letter(self, event_id: str, error: str) -> None:
        self._update(event_id, status="dead_letter", last_error=error)

    def recover_processing(self) -> int:
        """Após queda do processo, itens 'processing' voltam para a fila (mesma ideia do rpa-pedidos)."""
        with self._conn() as db:
            cur = db.execute(
                "UPDATE events SET status = 'queued', updated_at = ? WHERE status = 'processing'",
                (_iso(),),
            )
            return cur.rowcount

    def stats(self) -> dict:
        with self._conn() as db:
            by_status = {
                r[0]: r[1] for r in db.execute("SELECT status, COUNT(*) FROM events GROUP BY status")
            }
            by_category = {
                r[0]: r[1]
                for r in db.execute(
                    "SELECT json_extract(result, '$.category'), COUNT(*) FROM events"
                    " WHERE status = 'done' GROUP BY 1"
                )
            }
            totals = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(attempts), 0),"
                " COALESCE(SUM(fallback_used), 0),"
                " COALESCE(SUM(handoff_file IS NOT NULL), 0) FROM events"
            ).fetchone()
        return {
            "events_total": totals[0],
            "by_status": {s: by_status.get(s, 0) for s in ("queued", "processing", "done", "dead_letter")},
            "by_category": by_category,
            "attempts_total": totals[1],
            "llm_fallback_used": totals[2],
            "rpa_handoffs": totals[3],
        }
