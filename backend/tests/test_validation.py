"""Request contract tests that do not need PostgreSQL."""

import pytest

from northstar.domain.errors import InputValidationError
from northstar.domain.inputs import parse_job_input


def test_sort_rejects_bools_strings_and_oversized_lists() -> None:
    with pytest.raises(InputValidationError):
        parse_job_input("sort", {"numbers": [True]})
    with pytest.raises(InputValidationError):
        parse_job_input("sort", {"numbers": ["1"]})
    with pytest.raises(InputValidationError):
        parse_job_input("sort", {"numbers": [0] * 10001})
    with pytest.raises(InputValidationError):
        parse_job_input("sort", {"numbers": [1], "extra": 1})


def test_fibonacci_bounds() -> None:
    assert parse_job_input("fibonacci", {"n": 0}).n == 0  # type: ignore[attr-defined]
    with pytest.raises(InputValidationError):
        parse_job_input("fibonacci", {"n": -1})
    with pytest.raises(InputValidationError):
        parse_job_input("fibonacci", {"n": 10001})


def test_shortest_path_rejects_negative_weight_and_unknown_nodes() -> None:
    with pytest.raises(InputValidationError):
        parse_job_input(
            "shortest_path",
            {
                "nodes": ["A", "B"],
                "edges": [{"source": "A", "target": "B", "weight": -1}],
                "source": "A",
                "target": "B",
            },
        )
    with pytest.raises(InputValidationError) as caught:
        parse_job_input(
            "shortest_path",
            {
                "nodes": ["A"],
                "edges": [{"source": "A", "target": "B", "weight": 1}],
                "source": "A",
                "target": "A",
            },
        )
    assert caught.value.details


def test_word_frequency_limits() -> None:
    with pytest.raises(InputValidationError):
        parse_job_input("word_frequency", {"text": "a" * 100_001})
    with pytest.raises(InputValidationError):
        parse_job_input("word_frequency", {"text": "hello", "top_n": 0})


def test_unknown_job_type() -> None:
    with pytest.raises(InputValidationError):
        parse_job_input("compress", {"text": "hello"})
