"""UTC timestamps used by the API and the worker."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
