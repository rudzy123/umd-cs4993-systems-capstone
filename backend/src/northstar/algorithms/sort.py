"""Stable merge sort.

Time: O(n log n) comparisons.
Extra space: O(n) for the merged buffers.
n is limited to 10,000 numbers by the request contract.
"""

from collections.abc import Sequence


def merge_sort(values: Sequence[int | float]) -> tuple[list[int | float], int]:
    """Return a new sorted list and the number of element comparisons."""

    comparisons = 0

    def sort(items: Sequence[int | float]) -> list[int | float]:
        nonlocal comparisons
        if len(items) <= 1:
            return list(items)
        mid = len(items) // 2
        left = sort(items[:mid])
        right = sort(items[mid:])
        return _merge(left, right)

    def _merge(left: list[int | float], right: list[int | float]) -> list[int | float]:
        nonlocal comparisons
        merged: list[int | float] = []
        index_left = 0
        index_right = 0
        while index_left < len(left) and index_right < len(right):
            comparisons += 1
            if left[index_left] <= right[index_right]:
                merged.append(left[index_left])
                index_left += 1
            else:
                merged.append(right[index_right])
                index_right += 1
        merged.extend(left[index_left:])
        merged.extend(right[index_right:])
        return merged

    return sort(values), comparisons
