"""A person approves what AI apps add to the knowledge base: a source can wait in the new status
``awaiting_approval``. Existing sources keep the status they have, so they count as approved.

Revision ID: 0059
Revises: 0058
Create Date: 2026-11-04 20:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_knowledge_sources_status"), "knowledge_sources", type_="check")
    op.create_check_constraint(
        op.f("ck_knowledge_sources_status"),
        "knowledge_sources",
        "status IN ('awaiting_approval', 'pending', 'processing', 'ready', 'failed')",
    )


def downgrade() -> None:
    # Never queued, so they stay unread as pending; removing them would lose a member's text.
    op.execute("UPDATE knowledge_sources SET status = 'pending' WHERE status = 'awaiting_approval'")
    op.drop_constraint(op.f("ck_knowledge_sources_status"), "knowledge_sources", type_="check")
    op.create_check_constraint(
        op.f("ck_knowledge_sources_status"),
        "knowledge_sources",
        "status IN ('pending', 'processing', 'ready', 'failed')",
    )
