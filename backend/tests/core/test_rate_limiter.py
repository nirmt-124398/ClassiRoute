from __future__ import annotations

import asyncio
import time

import pytest

from core.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_allows_request_within_limit():
    rl = SlidingWindowRateLimiter()
    allowed, remaining, retry_after = await rl.check("key", 5, 10)
    assert allowed is True
    assert remaining == 4
    assert retry_after == 0


@pytest.mark.asyncio
async def test_blocks_when_limit_exceeded():
    rl = SlidingWindowRateLimiter()
    for _ in range(3):
        await rl.check("key", 3, 10)
    allowed, remaining, retry_after = await rl.check("key", 3, 10)
    assert allowed is False
    assert remaining == 0
    assert retry_after >= 1


@pytest.mark.asyncio
async def test_independent_keys():
    rl = SlidingWindowRateLimiter()
    for _ in range(3):
        await rl.check("a", 3, 10)
    allowed, remaining, _ = await rl.check("b", 3, 10)
    assert allowed is True
    assert remaining == 2


@pytest.mark.asyncio
async def test_window_expires():
    rl = SlidingWindowRateLimiter()
    await rl.check("key", 2, 1)
    await rl.check("key", 2, 1)
    allowed, _, _ = await rl.check("key", 2, 1)
    assert allowed is False
    await asyncio.sleep(1.1)
    allowed, _, _ = await rl.check("key", 2, 1)
    assert allowed is True


@pytest.mark.asyncio
async def test_get_remaining():
    rl = SlidingWindowRateLimiter()
    assert await rl.get_remaining("k", 5, 10) == 5
    await rl.check("k", 5, 10)
    assert await rl.get_remaining("k", 5, 10) == 4


@pytest.mark.asyncio
async def test_reset_clears_all():
    rl = SlidingWindowRateLimiter()
    for _ in range(5):
        await rl.check("k", 5, 10)
    assert await rl.get_remaining("k", 5, 10) == 0
    rl.reset()
    assert await rl.get_remaining("k", 5, 10) == 5


@pytest.mark.asyncio
async def test_concurrent_safety():
    rl = SlidingWindowRateLimiter()
    async def hit():
        return await rl.check("k", 5, 10)
    tasks = [asyncio.create_task(hit()) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    assert sum(1 for r in results if r[0]) == 5
    allowed, _, _ = await rl.check("k", 5, 10)
    assert allowed is False


@pytest.mark.asyncio
async def test_retry_after_calculation():
    rl = SlidingWindowRateLimiter()
    for _ in range(2):
        await rl.check("key", 2, 60)
    _, _, retry_after = await rl.check("key", 2, 60)
    assert 1 <= retry_after <= 60
