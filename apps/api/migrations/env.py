"""Async Alembic environment.

Migrations run over the direct connection (DATABASE_URL_DIRECT, never PgBouncer) with psycopg,
which accepts multi-statement SQL files such as the job queue's schema (TR-OPS-02).
"""

from __future__ import annotations

import asyncio
import sys

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import socialhood.models  # noqa: F401  (registers every model on Base.metadata)
from socialhood.db.base import Base
from socialhood.settings import get_settings

config = context.config
target_metadata = Base.metadata


def migration_url() -> str:
    url = get_settings().database_url_direct
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(migration_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif sys.platform == "win32":
    # Async psycopg cannot use Windows' default Proactor loop (local development only).
    asyncio.run(run_migrations_online(), loop_factory=asyncio.SelectorEventLoop)
else:
    asyncio.run(run_migrations_online())
