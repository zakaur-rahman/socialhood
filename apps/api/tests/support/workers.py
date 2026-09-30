"""Parallel runs (pytest-xdist, ``pytest -n N``): a database and a Valkey db per worker.

Each worker (``PYTEST_XDIST_WORKER`` = ``gw0``, ``gw1``, ...) gets:

- its own database, the base test database's name plus the worker id (``socialhood_test`` →
  ``socialhood_test_gw0``), created on first use and migrated once per worker session. The
  extensions (vector, pg_trgm, pgcrypto) come from migration 0001, exactly as on the base test
  database, so the test role needs the same rights it already needs there;
- its own Valkey db, the base db plus the worker's index (``TEST_REDIS_URL`` db 6 → gw0 uses 6,
  gw1 uses 7, ...). Valkey has dbs 0 to 15, so the base db plus the worker count must stay at or
  below 16; a worker past db 15 stops the run with an error rather than sharing a db.

A serial run (no ``-n``) has no worker id and uses the base database and db unchanged. Worker
databases are kept between runs, like the base one; drop them by hand to start clean.
"""

from __future__ import annotations

import contextlib
import os
import re
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

VALKEY_DBS = 16

WORKER: str | None = os.environ.get("PYTEST_XDIST_WORKER") or None


def worker_index(worker: str) -> int:
    match = re.fullmatch(r"gw(\d+)", worker)
    if match is None:
        raise RuntimeError(f"unexpected PYTEST_XDIST_WORKER {worker!r} (expected gw<N>)")
    return int(match.group(1))


def database_url(url: str, worker: str | None = WORKER) -> str:
    """The worker's database: the base name plus ``_<worker>``; the base URL when serial."""
    if worker is None:
        return url
    base = make_url(url)
    return base.set(database=f"{base.database}_{worker}").render_as_string(hide_password=False)


def redis_url(url: str, worker: str | None = WORKER) -> str:
    """The worker's Valkey db: the base db plus the worker's index; the base URL when serial."""
    if worker is None:
        return url
    parts = urlsplit(url)
    path = parts.path.strip("/")
    base_db = int(path) if path else 0
    db = base_db + worker_index(worker)
    if db >= VALKEY_DBS:
        raise RuntimeError(
            f"worker {worker} would use Valkey db {db} (base {base_db}), past db {VALKEY_DBS - 1}: "
            "run fewer workers (-n) or lower the db in TEST_REDIS_URL"
        )
    return urlunsplit(parts._replace(path=f"/{db}"))


def ensure_database(direct_url: str) -> None:
    """Create the database in ``direct_url`` when it does not exist yet."""
    url = make_url(direct_url)
    name = url.database
    assert name, "the test database URL names no database"
    maintenance = url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(
        maintenance.render_as_string(hide_password=False), autocommit=True
    ) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists is None:
            # Another run may create it meanwhile.
            with contextlib.suppress(
                psycopg.errors.DuplicateDatabase, psycopg.errors.UniqueViolation
            ):
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
