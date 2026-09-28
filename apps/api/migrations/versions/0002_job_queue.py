"""Create the job queue's tables (Procrastinate 3.10.0), from its own schema file (TR-OPS-02).

The SQL file is vendored in migrations/sql/procrastinate/ so this migration never changes when
the library is upgraded; an upgrade adds a new migration that runs the library's migration files
for the versions in between.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_FILE = Path(__file__).parent.parent / "sql" / "procrastinate" / "schema-3.10.0.sql"


def run_script(sql: str) -> None:
    """Run a multi-statement script through the raw driver cursor.

    Without parameters psycopg sends it as one simple query, so ``%`` and ``;`` inside function
    bodies are left alone (SQLAlchemy's execute paths would pass parameters and break both).
    """
    cursor = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cursor.execute(sql)
    finally:
        cursor.close()


def upgrade() -> None:
    run_script(SCHEMA_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    run_script(
        """
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN SELECT tablename FROM pg_tables
                   WHERE schemaname = 'public' AND tablename LIKE 'procrastinate\\_%' LOOP
            EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', r.tablename);
          END LOOP;
          FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p
                   JOIN pg_namespace n ON n.oid = p.pronamespace
                   WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate\\_%' LOOP
            EXECUTE format('DROP ROUTINE IF EXISTS %s CASCADE', r.sig);
          END LOOP;
          FOR r IN SELECT t.typname FROM pg_type t
                   JOIN pg_namespace n ON n.oid = t.typnamespace
                   WHERE n.nspname = 'public' AND t.typname LIKE 'procrastinate\\_%'
                     AND t.typtype IN ('e', 'c', 'd') LOOP
            EXECUTE format('DROP TYPE IF EXISTS %I CASCADE', r.typname);
          END LOOP;
        END $$;
        """
    )
