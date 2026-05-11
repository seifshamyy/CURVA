"""TTL-bounded LRU cache with single-flight semantics for async loaders."""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from cachetools import TTLCache


class AsyncTTLCache:
    def __init__(self, *, maxsize: int, ttl: float) -> None:
        self._store: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl)
        self._inflight: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        try:
            v = self._store[key]
            self._hits += 1
            return v
        except KeyError:
            pass

        async with self._lock:
            try:
                v = self._store[key]
                self._hits += 1
                return v
            except KeyError:
                pass
            if key in self._inflight:
                fut = self._inflight[key]
            else:
                fut = asyncio.get_running_loop().create_future()
                self._inflight[key] = fut
                asyncio.create_task(self._fill(key, loader, fut))

        self._misses += 1
        return await fut

    async def _fill(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        fut: asyncio.Future,
    ) -> None:
        try:
            v = await loader()
            self._store[key] = v
            fut.set_result(v)
        except Exception as e:
            fut.set_exception(e)
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

    def metrics(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0