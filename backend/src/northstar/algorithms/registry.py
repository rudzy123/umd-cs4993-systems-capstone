"""Dispatch a validated payload to its algorithm."""

from typing import Any

from northstar.algorithms.fibonacci import fibonacci
from northstar.algorithms.shortest_path import dijkstra
from northstar.algorithms.sort import merge_sort
from northstar.algorithms.word_frequency import word_frequencies
from northstar.domain.errors import InputValidationError, JobExecutionError
from northstar.domain.inputs import (
    FibonacciInput,
    ShortestPathInput,
    SortInput,
    WordFrequencyInput,
    parse_job_input,
)
from northstar.domain.numbers import canonicalize


def run_job(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Re-validate stored input and return a JSON-ready result object."""

    try:
        parsed = parse_job_input(job_type, payload)
    except InputValidationError:
        raise JobExecutionError("Stored input failed validation and cannot be executed.") from None

    if isinstance(parsed, SortInput):
        numbers: list[int | float] = []
        for number in parsed.numbers:
            canonical = canonicalize(number)
            if isinstance(canonical, bool) or not isinstance(canonical, int | float):
                raise JobExecutionError("Sort input must contain only finite numbers.")
            numbers.append(canonical)
        ordered, comparisons = merge_sort(numbers)
        return {
            "algorithm": "merge_sort",
            "count": len(ordered),
            "comparisons": comparisons,
            "sorted": ordered,
        }
    if isinstance(parsed, ShortestPathInput):
        return dijkstra(parsed)
    if isinstance(parsed, WordFrequencyInput):
        return word_frequencies(parsed.text, parsed.top_n)
    if isinstance(parsed, FibonacciInput):
        return fibonacci(parsed.n)
    raise JobExecutionError("Unsupported job type.")
