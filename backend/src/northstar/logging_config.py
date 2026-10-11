"""JSON logs for API and worker processes."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Structured fields passed via ``extra={"ns_job_id": ...}`` are copied without
    the ``ns_`` prefix. Payloads should not be placed in those fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key.startswith("ns_"):
                payload[key.removeprefix("ns_")] = value
        if record.exc_info:
            payload["exception_type"] = (
                record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            )
        return json.dumps(payload, default=str, ensure_ascii=True)


class NorthstarHandler(logging.StreamHandler[Any]):
    """Marker handler so configuration is idempotent."""


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if any(isinstance(handler, NorthstarHandler) for handler in root.handlers):
        return
    handler = NorthstarHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


def log_event(logger: logging.Logger, message: str, **fields: object) -> None:
    extra = {f"ns_{key}": value for key, value in fields.items()}
    logger.info(message, extra=extra)
