"""Snooze a conversation (GR-45).

- conversations.snoozed_until: the conversation is hidden from every inbox view but "snoozed"
  until then; NULL when it is not snoozed. A partial index serves the wake_snoozed job, which
  finds due rows across workspaces, and the snoozed view.

Expand-only: a nullable column.

Revision ID: 0063
Revises: 0062
Create Date: 2026-11-19 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        op.f("ix_conversations_snoozed"),
        "conversations",
        ["snoozed_until"],
        postgresql_where=sa.text("snoozed_until IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversations_snoozed"), table_name="conversations")
    op.drop_column("conversations", "snoozed_until")
