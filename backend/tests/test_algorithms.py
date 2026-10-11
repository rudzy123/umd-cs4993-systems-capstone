"""Algorithm contracts."""

import random

from northstar.algorithms.fibonacci import fibonacci
from northstar.algorithms.registry import run_job
from northstar.algorithms.shortest_path import dijkstra
from northstar.algorithms.sort import merge_sort
from northstar.algorithms.word_frequency import word_frequencies
from northstar.domain.inputs import ShortestPathInput


def test_merge_sort_matches_builtin_and_is_deterministic() -> None:
    generator = random.Random(4993)
    for _ in range(30):
        values = [generator.randint(-1000, 1000) for _ in range(generator.randint(0, 40))]
        ordered, comparisons = merge_sort(values)
        assert ordered == sorted(values)
        assert comparisons >= 0
        again, again_comparisons = merge_sort(values)
        assert again == ordered
        assert again_comparisons == comparisons


def test_merge_sort_small_cases() -> None:
    assert merge_sort([]) == ([], 0)
    assert merge_sort([2]) == ([2], 0)
    ordered, comparisons = merge_sort([3, 1, 2])
    assert ordered == [1, 2, 3]
    assert comparisons == 3
    assert merge_sort([2, 2, 1])[0] == [1, 2, 2]


def test_dijkstra_prefers_the_cheaper_deterministic_path() -> None:
    graph = ShortestPathInput.model_validate(
        {
            "nodes": ["A", "B", "C"],
            "edges": [
                {"source": "A", "target": "C", "weight": 10},
                {"source": "A", "target": "B", "weight": 1},
                {"source": "B", "target": "C", "weight": 2},
            ],
            "source": "A",
            "target": "C",
        }
    )
    result = dijkstra(graph)
    assert result["reachable"] is True
    assert result["distance"] == 3
    assert result["path"] == ["A", "B", "C"]


def test_dijkstra_tie_keeps_the_alphabetically_earlier_predecessor() -> None:
    graph = ShortestPathInput.model_validate(
        {
            "nodes": ["A", "B", "C", "D"],
            "edges": [
                {"source": "A", "target": "C", "weight": 1},
                {"source": "A", "target": "B", "weight": 1},
                {"source": "C", "target": "D", "weight": 1},
                {"source": "B", "target": "D", "weight": 1},
            ],
            "source": "A",
            "target": "D",
        }
    )
    assert dijkstra(graph)["path"] == ["A", "B", "D"]


def test_dijkstra_unreachable_and_same_node() -> None:
    disconnected = ShortestPathInput.model_validate(
        {"nodes": ["A", "B"], "edges": [], "source": "A", "target": "B"}
    )
    missing = dijkstra(disconnected)
    assert missing["reachable"] is False
    assert missing["distance"] is None
    assert missing["path"] == []

    loop = ShortestPathInput.model_validate(
        {"nodes": ["A"], "edges": [], "source": "A", "target": "A"}
    )
    assert dijkstra(loop)["path"] == ["A"]
    assert dijkstra(loop)["distance"] == 0


def test_word_frequency_ranks_ties_alphabetically() -> None:
    result = word_frequencies("The cat sat on the mat. The cat sat.", 10)
    assert result["token_count"] == 9
    assert result["frequencies"][0] == {"word": "the", "count": 3}
    assert [item["word"] for item in result["frequencies"][:3]] == ["the", "cat", "sat"]


def test_word_frequency_folds_case_and_apostrophes() -> None:
    result = word_frequencies("Don't stop. don't stop!", 5)
    assert result["frequencies"] == [
        {"word": "don't", "count": 2},
        {"word": "stop", "count": 2},
    ]


def test_fibonacci_known_values() -> None:
    assert fibonacci(0)["value"] == "0"
    assert fibonacci(1)["value"] == "1"
    assert fibonacci(10)["value"] == "55"
    assert fibonacci(20) == {
        "algorithm": "bottom_up_dynamic_programming",
        "n": 20,
        "value": "6765",
        "digit_count": 4,
    }
    assert fibonacci(100)["value"] == "354224848179261915075"


def test_run_job_is_deterministic() -> None:
    payload = {"numbers": [5, 1, 4]}
    assert run_job("sort", payload) == run_job("sort", payload)
    assert run_job("sort", payload)["sorted"] == [1, 4, 5]
