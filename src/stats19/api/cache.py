"""Small in-process caches for API responses.

Results only change when the pipeline publishes a new release, so keys include
the latest successful run (``data_load``) and nothing is served stale after a load.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

import psycopg


def data_load(conn: psycopg.Connection) -> int | None:
    """The latest successful pipeline run: results change when a new release loads."""
    row = conn.execute(
        "SELECT max(run_id) AS run_id FROM etl.run WHERE status = 'success'"
    ).fetchone()
    return row["run_id"] if row else None


class BytesLRU:
    """Least-recently-used cache of byte strings, bounded by total size."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self.size = 0
        self._items: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> bytes | None:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: str, value: bytes) -> None:
        if len(value) > self.max_bytes:
            return
        with self._lock:
            old = self._items.pop(key, None)
            if old is not None:
                self.size -= len(old)
            self._items[key] = value
            self.size += len(value)
            while self.size > self.max_bytes:
                _, evicted = self._items.popitem(last=False)
                self.size -= len(evicted)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.size = 0
