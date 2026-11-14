"""YouTube channels (C-195).

- social_accounts.platform allows ``youtube``: a connected YouTube channel is an account;
- scheduled_post_targets.options: per-target choices a platform needs beyond the caption
  (YouTube's title and privacy, used from its publishing step on). Nullable, no default.

Expand-only: a wider check and one nullable column.

Revision ID: 0060
Revises: 0059
Create Date: 2026-11-14 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PLATFORMS = "platform IN ('instagram', 'whatsapp', 'facebook', 'linkedin', 'web')"
NEW_PLATFORMS = "platform IN ('instagram', 'whatsapp', 'facebook', 'linkedin', 'web', 'youtube')"


def _swap(table: str, name: str, expression: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, expression)


def upgrade() -> None:
    _swap("social_accounts", "platform", NEW_PLATFORMS)
    op.add_column(
        "scheduled_post_targets",
        sa.Column("options", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scheduled_post_targets", "options")
    # Fails while a YouTube account exists: remove those rows first.
    _swap("social_accounts", "platform", OLD_PLATFORMS)
