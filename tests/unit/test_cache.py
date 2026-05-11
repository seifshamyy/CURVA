import asyncio
import pytest
from curva_agent.cache.lru import AsyncTTLCache


@pytest.mark.asyncio
async def test_cache_miss_calls_loader_once():
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return {"value": 42}

    c = AsyncTTLCache(maxsize=10, ttl=60)
    v1 = await c.get_or_load("k", loader)
    v2 = await c.get_or_load("k", loader)
    assert v1 == v2 == {"value": 42}
    assert calls == 1


@pytest.mark.asyncio
async def test_single_flight_dedupes_concurrent_calls():
    calls = 0

    async def slow_loader():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return "v"

    c = AsyncTTLCache(maxsize=10, ttl=60)
    results = await asyncio.gather(*[c.get_or_load("same_key", slow_loader) for _ in range(8)])
    assert results == ["v"] * 8
    assert calls == 1


@pytest.mark.asyncio
async def test_ttl_expiry_triggers_reload():
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return calls

    c = AsyncTTLCache(maxsize=10, ttl=0.05)
    v1 = await c.get_or_load("k", loader)
    await asyncio.sleep(0.1)
    v2 = await c.get_or_load("k", loader)
    assert v1 == 1
    assert v2 == 2


@pytest.mark.asyncio
async def test_different_keys_isolated():
    c = AsyncTTLCache(maxsize=10, ttl=60)
    assert await c.get_or_load("a", lambda: _async_value(1)) == 1
    assert await c.get_or_load("b", lambda: _async_value(2)) == 2


async def _async_value(v):
    return v


@pytest.mark.asyncio
async def test_metrics_reports_hits_and_misses():
    c = AsyncTTLCache(maxsize=10, ttl=60)
    await c.get_or_load("k", lambda: _async_value("x"))
    await c.get_or_load("k", lambda: _async_value("x"))
    await c.get_or_load("k", lambda: _async_value("x"))
    assert c.metrics() == {"hits": 2, "misses": 1, "size": 1}