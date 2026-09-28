"""Valkey (Redis-compatible) client for non-durable roles: streams, rate limits, caches, locks."""

from __future__ import annotations

from redis.asyncio import Redis

from socialhood.settings import Settings


def make_redis(settings: Settings) -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, health_check_interval=30)
