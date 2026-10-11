"""Dijkstra shortest paths for non-negative edge weights.

Time: O((V + E) log V) with a binary heap.
Space: O(V + E).
Limits: 300 nodes and 2,000 edges.

Equal-length paths keep the predecessor discovered first. Adjacency lists are
sorted by neighbor name, and the heap breaks distance ties by node name, so the
path is deterministic.
"""

import heapq
from typing import Any

from northstar.domain.errors import JobExecutionError
from northstar.domain.inputs import ShortestPathInput
from northstar.domain.numbers import canonicalize


def dijkstra(graph: ShortestPathInput) -> dict[str, Any]:
    nodes = list(graph.nodes)
    node_set = set(nodes)
    if graph.source not in node_set or graph.target not in node_set:
        raise JobExecutionError("Source and target must be included in the graph.")

    adjacency: dict[str, list[tuple[str, int | float]]] = {node: [] for node in nodes}
    for edge in graph.edges:
        weight = canonicalize(edge.weight)
        if not isinstance(weight, int | float) or isinstance(weight, bool):
            raise JobExecutionError("Edge weights must be non-negative numbers.")
        if weight < 0:
            raise JobExecutionError("Dijkstra requires non-negative edge weights.")
        _add_edge(adjacency, edge.source, edge.target, weight)
        if not graph.directed:
            _add_edge(adjacency, edge.target, edge.source, weight)

    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (str(item[0]), float(item[1])))

    distances: dict[str, int | float] = {graph.source: 0}
    previous: dict[str, str] = {}
    heap: list[tuple[int | float, str]] = [(0, graph.source)]
    settled: set[str] = set()

    while heap:
        current_distance, node = heapq.heappop(heap)
        if node in settled:
            continue
        best = distances.get(node)
        if best is None or current_distance > best:
            continue
        settled.add(node)
        if node == graph.target:
            break
        for neighbor, weight in adjacency[node]:
            candidate = current_distance + weight
            known = distances.get(neighbor)
            if known is None or candidate < known:
                distances[neighbor] = candidate
                previous[neighbor] = node
                heapq.heappush(heap, (candidate, neighbor))

    reachable = graph.target in distances
    path = _reconstruct(previous, graph.source, graph.target) if reachable else []
    distance = canonicalize(distances[graph.target]) if reachable else None
    return {
        "algorithm": "dijkstra",
        "directed": graph.directed,
        "reachable": reachable,
        "distance": distance,
        "path": path,
        "node_count": len(nodes),
        "edge_count": len(graph.edges),
    }


def _add_edge(
    adjacency: dict[str, list[tuple[str, int | float]]],
    source: str,
    target: str,
    weight: int | float,
) -> None:
    neighbors = adjacency.setdefault(source, [])
    for index, (existing_target, existing_weight) in enumerate(neighbors):
        if existing_target == target:
            if weight < existing_weight:
                neighbors[index] = (target, weight)
            return
    neighbors.append((target, weight))


def _reconstruct(previous: dict[str, str], source: str, target: str) -> list[str]:
    if source == target:
        return [source]
    cursor: str | None = target
    reversed_path: list[str] = []
    seen: set[str] = set()
    while cursor is not None and cursor not in seen:
        reversed_path.append(cursor)
        if cursor == source:
            reversed_path.reverse()
            return reversed_path
        seen.add(cursor)
        cursor = previous.get(cursor)
    return []
