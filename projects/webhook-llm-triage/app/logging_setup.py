"""Logs estruturados em JSON (uma linha por evento) no stdout."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        data.update(getattr(record, "fields", {}) or {})
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def configure(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("triage")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False


def log(logger: logging.Logger, msg: str, level: int = logging.INFO, **fields: object) -> None:
    logger.log(level, msg, extra={"fields": fields})
