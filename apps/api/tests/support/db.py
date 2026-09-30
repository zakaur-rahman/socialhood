"""Database and Valkey fixtures shared by the integration and tenancy suites."""

from __future__ import annotations

from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine

from socialhood.settings import get_settings
from tests.support import workers

API_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def migrated_database() -> None:
    if workers.WORKER is not None:
        # A parallel worker's own database (tests/support/workers.py); the base one must exist.
        workers.ensure_database(get_settings().database_url_direct)
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    # Alembic's env runs its own event loop, so keep it off the test loop's thread.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(command.upgrade, config, "head").result()


@pytest.fixture(scope="session")
async def engine(migrated_database: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_settings().database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A connection whose work is rolled back after the test."""
    async with engine.connect() as conn:
        transaction = await conn.begin()
        yield conn
        await transaction.rollback()


@pytest.fixture
async def session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as s:
        yield s


@pytest.fixture
async def clean_db(engine: AsyncEngine) -> AsyncIterator[None]:
    """For tests that go through the API, which commits: empty the tables before and after."""

    async def wipe() -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE users, workspaces, webhook_events, data_deletion_requests CASCADE")
            )

    await wipe()
    yield
    await wipe()


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
