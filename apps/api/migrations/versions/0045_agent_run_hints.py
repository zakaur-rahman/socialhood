"""Structured follow-ups on an Ask run (VIS-11).

- agent_runs.hints: the validated range, platform or "prepare replies" follow-up a run was made
  from (JSON; null for every question typed in words). The run's ``request`` holds its readable
  words, so the thread shows words, not ids.

Expand-only: one nullable column; nothing is rewritten.

Revision ID: 0045
Revises: 0044
Create Date: 2026-10-26 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs", sa.Column("hints", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "hints")
