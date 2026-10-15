"""The three required sorts, written explicitly for the course project.

All functions return a new list. The objects inside that list are shared so
the threat radar and targeting system refer to the actual living enemies.
"""

from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")


def bubble_sort(items: Iterable[T], key: Callable = lambda x: x,
                reverse: bool = False) -> list[T]:
    """Repeated adjacent comparisons; O(n^2), O(n) best with early exit."""
    result = list(items)
    for end in range(len(result) - 1, 0, -1):
        swapped = False
        for index in range(end):
            left, right = key(result[index]), key(result[index + 1])
            if (left < right) if reverse else (left > right):
                result[index], result[index + 1] = result[index + 1], result[index]
                swapped = True
        if not swapped:
            break
    return result


def insert_ordered(items: Iterable[T], item: T,
                   key: Callable = lambda x: x,
                   reverse: bool = False) -> list[T]:
    """Insertion-sort step: shift larger/smaller predecessors to insert item."""
    result = list(items)
    result.append(item)
    index = len(result) - 2
    value = key(item)
    while index >= 0:
        previous = key(result[index])
        should_shift = previous < value if reverse else previous > value
        if not should_shift:
            break
        result[index + 1] = result[index]
        index -= 1
    result[index + 1] = item
    return result


def insertion_sort(items: Iterable[T], key: Callable = lambda x: x,
                   reverse: bool = False) -> list[T]:
    """Shift predecessors to grow an ordered prefix; O(n^2), best O(n)."""
    result = list(items)
    for position in range(1, len(result)):
        item = result[position]
        value = key(item)
        index = position - 1
        while index >= 0:
            previous = key(result[index])
            should_shift = previous < value if reverse else previous > value
            if not should_shift:
                break
            result[index + 1] = result[index]
            index -= 1
        result[index + 1] = item
    return result


def selection_sort(items: Iterable[T], key: Callable = lambda x: x,
                   reverse: bool = False) -> list[T]:
    """Select the best remaining item for every position; O(n^2)."""
    result = list(items)
    for start in range(len(result) - 1):
        best = start
        for candidate in range(start + 1, len(result)):
            value, best_value = key(result[candidate]), key(result[best])
            if (value > best_value) if reverse else (value < best_value):
                best = candidate
        if best != start:
            result[start], result[best] = result[best], result[start]
    return result
