"""Shared resources for worker processes, created once per process on first use."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.engine import make_engine, make_sessionmaker
from socialhood.kv import make_redis
from socialhood.settings import Settings, get_settings


@dataclass(frozen=True)
class Runtime:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    http: httpx.AsyncClient


def make_http_client() -> httpx.AsyncClient:
    """One shared client per process with the TR-PL-05 timeouts."""
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))


@lru_cache
def runtime() -> Runtime:
    settings = get_settings()
    return Runtime(
        settings=settings,
        sessionmaker=make_sessionmaker(make_engine(settings)),
        redis=make_redis(settings),
        http=make_http_client(),
    )
