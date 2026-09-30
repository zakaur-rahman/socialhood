"""The end-to-end database and Valkey db (T9.4; scripts/e2e-stack.mjs). Test-only.

    python db.py reset   drop and re-create DATABASE_URL_DIRECT's database; flush REDIS_URL's db
    python db.py drop    drop the database; flush the db

Only a database named ``socialhood_test_<n>`` or ``socialhood_e2e*`` and a Valkey db other than
0 are touched, so the development data can never be dropped by mistake.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse

import psycopg
import redis
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

SAFE_DATABASE = re.compile(r"^socialhood_(test_\d+|e2e\w*)$")


def _database() -> tuple[str, dict[str, object]]:
    info = conninfo_to_dict(os.environ["DATABASE_URL_DIRECT"])
    name = str(info.get("dbname", ""))
    if not SAFE_DATABASE.match(name):
        raise SystemExit(f"Refusing to touch database {name!r}: not an e2e database")
    return name, {**info, "dbname": "postgres"}


def _redis_url() -> str:
    url = os.environ["REDIS_URL"]
    db = urlparse(url).path.lstrip("/") or "0"
    if db == "0":
        raise SystemExit("Refusing to flush Valkey db 0: the e2e stack uses its own db")
    return url


def drop(*, create: bool) -> None:
    name, admin = _database()
    with psycopg.connect(**admin, autocommit=True) as conn:  # type: ignore[arg-type]
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
        if create:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    client = redis.Redis.from_url(_redis_url())
    try:
        client.flushdb()
    finally:
        client.close()


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in ("reset", "drop"):
        raise SystemExit("usage: python db.py reset|drop")
    drop(create=command == "reset")


if __name__ == "__main__":
    main()
