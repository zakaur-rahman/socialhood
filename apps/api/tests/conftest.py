"""Test configuration.

Tests always use their own database and Valkey db (TEST_* variables, or the local Docker
defaults), never whatever DATABASE_URL a developer has in their shell.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable, Mapping

import pytest

pytest_plugins = ["tests.support.db", "tests.support.api"]

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://socialhood:socialhood@localhost:5432/socialhood_test",
)
os.environ["DATABASE_URL_DIRECT"] = os.environ.get(
    "TEST_DATABASE_URL_DIRECT",
    "postgresql://socialhood:socialhood@localhost:5432/socialhood_test",
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("LOG_LEVEL", "INFO")


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    # Async psycopg (the job queue) cannot use Windows' default Proactor loop.
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
