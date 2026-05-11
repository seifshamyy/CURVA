import asyncio
import pytest
from curva_agent.observability.rate_limit import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_blocks():
    rl = SlidingWindowRateLimiter(max_events=3, window_seconds=60)
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is False


@pytest.mark.asyncio
async def test_isolated_per_key():
    rl = SlidingWindowRateLimiter(max_events=1, window_seconds=60)
    assert await rl.try_acquire("a") is True
    assert await rl.try_acquire("b") is True


@pytest.mark.asyncio
async def test_window_slides_to_allow_new_events():
    rl = SlidingWindowRateLimiter(max_events=2, window_seconds=0.1)
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is False
    await asyncio.sleep(0.12)
    assert await rl.try_acquire("k") is True