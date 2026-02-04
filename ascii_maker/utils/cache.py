"""LRU frame cache keyed by (frame_index, settings_hash)."""

from __future__ import annotations

from collections import OrderedDict
from typing import TypeVar

T = TypeVar("T")


class FrameCache:
    """Simple LRU cache for processed frames.

    Keys are (frame_index, settings_hash) tuples.
    """

    def __init__(self, max_size: int = 64) -> None:
        self._max_size = max_size
        self._cache: OrderedDict[tuple[int, str], object] = OrderedDict()

    def get(self, frame_idx: int, settings_hash: str) -> object | None:
        """Get a cached frame, or None if not present."""
        key = (frame_idx, settings_hash)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, frame_idx: int, settings_hash: str, value: object) -> None:
        """Cache a processed frame."""
        key = (frame_idx, settings_hash)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[key] = value

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
