"""Test configuration.

Tests always use their own database and Valkey db (TEST_* variables, or the local Docker
defaults), never whatever DATABASE_URL a developer has in their shell. Under pytest-xdist
(``pytest -n N``) each worker uses its own database and Valkey db, derived from those
(tests/support/workers.py). Tests marked ``serial`` run only without ``-n``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable, Mapping

import pydantic_ai.models
import pytest

from tests.support import workers

# No test reaches a real model through Pydantic AI (the agent's planner, TR-AGT-02): any model but
# FunctionModel and TestModel raises. AI calls through ai/ use the FakeProvider (tests/support/ai).
pydantic_ai.models.ALLOW_MODEL_REQUESTS = False

pytest_plugins = [
    "tests.support.db",
    # Before api, which imports their constants: Dodo, email and push are fakes in every test.
    "tests.support.billing",
    "tests.support.notify",
    "tests.support.api",
    "tests.support.instagram",
    "tests.support.ai",
]

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = workers.database_url(
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://socialhood:socialhood@localhost:5432/socialhood_test",
    )
)
os.environ["DATABASE_URL_DIRECT"] = workers.database_url(
    os.environ.get(
        "TEST_DATABASE_URL_DIRECT",
        "postgresql://socialhood:socialhood@localhost:5432/socialhood_test",
    )
)
os.environ["REDIS_URL"] = workers.redis_url(
    os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
)
os.environ.setdefault("LOG_LEVEL", "INFO")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # A serial test must not share the machine, Postgres or Valkey with other workers' tests.
    # CI runs `pytest -n 4 -m "not serial"`, then `pytest -m serial`.
    if workers.WORKER is None:
        return
    skip = pytest.mark.skip(reason="serial: run it without -n (pytest -m serial)")
    for item in items:
        if item.get_closest_marker("serial") is not None:
            item.add_marker(skip)


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    # Async psycopg (the job queue) cannot use Windows' default Proactor loop.
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
