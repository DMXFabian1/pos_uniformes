"""Cache pequeno para snapshots de UI que se invalidan por mutacion."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class SnapshotCache(Generic[T]):
    def __init__(self) -> None:
        self._value: T | None = None

    @property
    def has_value(self) -> bool:
        return self._value is not None

    def get_or_load(self, loader: Callable[[], T]) -> T:
        if self._value is None:
            self._value = loader()
        return self._value

    def invalidate(self) -> None:
        self._value = None
