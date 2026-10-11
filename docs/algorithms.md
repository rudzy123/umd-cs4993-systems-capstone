# Algorithms

The implementations live in `backend/src/northstar/algorithms`. `run_job` is the only entry the worker uses. It re-validates the stored JSON and then calls one function. Tests in `backend/tests/test_algorithms.py` lock the contracts below. Given the same input, each function returns the same structure and the same values.

## Sort

`merge_sort(values) -> (sorted_values, comparison_count)`

Stable merge sort. Equal elements keep their original order because the merge takes from the left run when values are equal.

- Time: O(n log n) comparisons.
- Extra space: O(n) for the merge buffers.
- Limit: at most 10,000 numbers. Each number is finite and its absolute value is at most 1e15. Booleans are rejected. Integers that are exactly representable stay integers in the stored payload; other values stay finite floats.
- Result: `{"sorted": [...], "comparisons": <int>}`.

Example: `[5, 1, 4, 2, 3]` sorts to `[1, 2, 3, 4, 5]`.

## Shortest path

`dijkstra(graph) -> {"reachable", "distance", "path"}`

Binary-heap Dijkstra. Weights must be greater than or equal to zero, so the first time a node is settled its distance is final.

- Time: O((V + E) log V).
- Space: O(V + E).
- Limits: 300 nodes, 2,000 edges. Node ids match `^[A-Za-z0-9_-]{1,64}$` and are unique. Every edge endpoint, the source, and the target must be in `nodes`. Weights are at most 1e9.
- Directed graphs are the default. `directed: false` inserts the reverse edge. Parallel edges keep the smaller weight.
- Ties: adjacency lists are sorted, and a new path does not replace the predecessor when the distance is equal. The path is deterministic.
- Source equal to target returns distance 0 and a one-node path.
- An unreachable target is a success: `reachable` is false, `distance` is null, and `path` is empty. That is a computed answer, not a worker failure.

Example: edges A→B weight 1, B→C weight 2, A→C weight 10. The path is `["A", "B", "C"]` and the distance is 3.

## Word frequency

`word_frequencies(text, top_n) -> {"token_count", "unique_count", "frequencies"}`

Tokens match `[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?` and are case-folded. `Don't` and `don't` count as the same token. Ranking is by count descending, then word ascending.

- Time: O(n) in characters, then O(u log u) to sort u unique words.
- Space: O(u).
- Limits: 100,000 characters. `top_n` is an integer from 1 through 100 and defaults to 20.
- Result rows are `{"word", "count"}` and contain at most `top_n` entries.

Example: `The cat sat on the mat.` yields token count 6 and the first row `{"word": "the", "count": 2}`.

## Fibonacci

`fibonacci(n) -> {"n", "value", "digit_count"}`

Bottom-up dynamic programming with two rolling integers. F(0) = 0, F(1) = 1, and F(k) = F(k-1) + F(k-2).

- Loop iterations: O(n).
- Each addition touches O(n) bits, so bit complexity is O(n²).
- Extra memory beyond the output is two integers.
- Limit: n is an integer from 0 through 10,000. The value is a decimal string so it is not rounded through IEEE-754. F(20) is `6765`. F(100) is `354224848179261915075`.

The cap is the safety control. An unbounded n would make one job dominate the worker for an unreasonable time and produce an enormous JSON result.

## Why these four

| Job | Course idea |
| --- | --- |
| Merge sort | Divide and conquer, stability, comparison counts |
| Dijkstra | Greedy choice on a graph, heap, deterministic tie break |
| Word frequency | Hash map plus an explicit sort for a stable ranking |
| Fibonacci | Dynamic programming and the cost of big-integer arithmetic |

None of the functions perform I/O. The worker can retry or abandon a run without the algorithm itself having written anything.
