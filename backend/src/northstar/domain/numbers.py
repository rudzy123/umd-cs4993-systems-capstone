"""JSON-safe numeric canonicalization."""

import math
from typing import Any

from northstar.domain.errors import JobExecutionError

_SAFE_INT = 2**53
_MAX_ABS = 10**15


def canonicalize(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > _MAX_ABS:
            raise JobExecutionError(
                "Numeric values must be finite and within the allowed magnitude."
            )
        if value.is_integer() and abs(value) <= _SAFE_INT:
            return int(value)
        return value
    if isinstance(value, dict):
        return {str(key): canonicalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value
