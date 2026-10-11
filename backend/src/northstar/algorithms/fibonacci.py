"""Bottom-up Fibonacci.

The recurrence F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2) is filled in order.
Loop iterations: O(n).
Each addition costs O(n) bits, so the bit complexity is O(n^2).
Extra memory beyond the output integer is O(1) integers (two rolling values).
n is limited to 10,000. The value is returned as a decimal string so clients
do not lose precision.
"""

from typing import Any

from northstar.domain.errors import JobExecutionError
from northstar.domain.inputs import MAX_FIBONACCI_N


def fibonacci(n: int) -> dict[str, Any]:
    if n < 0 or n > MAX_FIBONACCI_N:
        raise JobExecutionError("Fibonacci n must be between 0 and 10000.")
    if n == 0:
        value = 0
    else:
        previous = 0
        current = 1
        for _ in range(1, n):
            previous, current = current, previous + current
        value = current
    text = str(value)
    return {
        "algorithm": "bottom_up_dynamic_programming",
        "n": n,
        "value": text,
        "digit_count": len(text),
    }
