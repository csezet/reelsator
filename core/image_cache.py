"""Bounded, thread-safe cache of normalized source images."""

from collections import OrderedDict
from threading import Lock
from typing import Hashable, Optional
from PIL import Image


class NormalizedImageCache:
    """Owns cached pixels and returns copies so workers cannot mutate shared images."""

    def __init__(self, max_bytes: int = 64 * 1024 * 1024):
        self.max_bytes = max_bytes
        self._entries = OrderedDict()
        self._size_bytes = 0
        self._lock = Lock()

    @property
    def size_bytes(self) -> int:
        with self._lock:
            return self._size_bytes

    def get(self, key: Hashable) -> Optional[Image.Image]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            return entry[0].copy()

    def put(self, key: Hashable, image: Image.Image) -> None:
        size = image.width * image.height * len(image.getbands())
        with self._lock:
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._size_bytes -= previous[1]
            if size > self.max_bytes:
                return
            while self._entries and self._size_bytes + size > self.max_bytes:
                _, (_, evicted_size) = self._entries.popitem(last=False)
                self._size_bytes -= evicted_size
            self._entries[key] = (image.copy(), size)
            self._size_bytes += size

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._size_bytes = 0
