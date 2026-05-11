"""Sliding-window per-key rate limiter (in-memory).

Suitable for single-container deployments. If we scale beyond one replica, swap
this for a Redis-backed implementation — interface stays the same.
"""
import asyncio
import time
from collections import deque


class SlidingWindowRateLimiter:
    def __init__(self, *, max_events: int, window_seconds: float) -> None:
        self._max = max_events
        self._window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def try_acquire(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            buf = self._events.setdefault(key, deque())
            cutoff = now - self._window
            while buf and buf[0] < cutoff:
                buf.popleft()
            if len(buf) >= self._max:
                return False
            buf.append(now)
            return True