"""Permanent execution failures whose messages are safe to show users."""

from typing import Any


class JobExecutionError(Exception):
    """The job cannot succeed by retrying the same input."""


class InputValidationError(Exception):
    """Request input failed domain validation."""

    def __init__(self, details: list[dict[str, Any]]) -> None:
        self.details = details
        super().__init__("invalid input")


class IdempotencyConflict(Exception):
    """The same idempotency key was reused with a different request body."""
