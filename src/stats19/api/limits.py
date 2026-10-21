"""Caps on expensive work running at once (PLAN-006 C5), and on how often things happen.

Each PDF render is a headless Chromium; exports stream large files. With few users a
concurrency cap fits better than per-IP rate limits: beyond it, a friendly 503.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager

from stats19.api.envelope import ApiError

BUSY_MESSAGE = "The server is busy with other reports or exports. Try again in a moment."


class Limiter:
    def __init__(self, name: str, slots: int):
        self.name = name
        self._slots = threading.BoundedSemaphore(slots)

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._slots.acquire(blocking=False):
            raise ApiError(503, "busy", BUSY_MESSAGE)
        try:
            yield
        finally:
            self._slots.release()


PDF = Limiter("pdf", 2)
EXPORT = Limiter("export", 2)


class RateLimit:
    """At most ``limit`` events in any ``window_s`` seconds (all clients together)."""

    def __init__(self, limit: int, window_s: float, clock=time.monotonic):
        self.limit, self.window_s, self._clock = limit, window_s, clock
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = self._clock()
        with self._lock:
            while self._times and now - self._times[0] >= self.window_s:
                self._times.popleft()
            if len(self._times) >= self.limit:
                return False
            self._times.append(now)
            return True
