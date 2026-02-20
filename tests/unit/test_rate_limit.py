import asyncio

import pytest

from app.core.rate_limit import InMemoryRateLimiter, RateLimitRule


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=2, window_seconds=60)

    assert await limiter.allow("session-a", rule)
    assert await limiter.allow("session-a", rule)
    assert not await limiter.allow("session-a", rule)


@pytest.mark.asyncio
async def test_rate_limiter_resets_after_window() -> None:
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=1)

    assert await limiter.allow("session-b", rule)
    assert not await limiter.allow("session-b", rule)

    await asyncio.sleep(1.05)
    assert await limiter.allow("session-b", rule)
