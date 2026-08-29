"""Async Redis client.

Kept small: just one module-level factory that returns a redis.asyncio client.
Tests inject a `fakeredis.aioredis.FakeRedis` instance via `init_redis()`.
"""
from __future__ import annotations

import redis.asyncio as aioredis

from app.config import get_settings

_client: aioredis.Redis | None = None


def init_redis(url: str | None = None, *, fake: bool = False) -> aioredis.Redis:
    """Initialise the module-level redis client.

    Pass `fake=True` (used by tests) to create a `fakeredis` instance instead.
    """
    global _client
    if fake:
        from fakeredis import aioredis as fake_aioredis  # local import to keep prod dep-light

        _client = fake_aioredis.FakeRedis(decode_responses=True)
    else:
        target_url = url or get_settings().effective_redis_url
        _client = aioredis.from_url(target_url, decode_responses=True)
    return _client


def get_redis() -> aioredis.Redis:
    """Return the current redis client, creating one if needed."""
    if _client is None:
        init_redis()
    assert _client is not None  # noqa: S101
    return _client


async def close_redis() -> None:
    """Tear down the redis client (used in test teardown + app shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


__all__ = ["get_redis", "init_redis", "close_redis"]
