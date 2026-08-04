from __future__ import annotations

import redis.asyncio as aioredis

_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """全局复用的 Redis 客户端（decode_responses=True）。"""
    global _client
    if _client is None:
        from .settings import get_settings

        _client = aioredis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            encoding="utf-8",
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None
