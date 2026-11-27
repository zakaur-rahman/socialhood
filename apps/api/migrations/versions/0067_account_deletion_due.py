"""Deleting an account waits 15 days (C-214): ``social_accounts.deletion_due_at``.

Delete account and data now disconnects at once and purges once this time has passed, so a
reconnect before then keeps everything. A Meta data-deletion request sets it to the time of the
request. Accounts already being deleted are due at once (their request time). Expand-only: a
nullable column, filled for the rows being deleted.

Revision ID: 0067
Revises: 0066
Create Date: 2026-11-27 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "social_accounts", sa.Column("deletion_due_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE social_accounts SET deletion_due_at = deletion_requested_at "
        "WHERE deletion_requested_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("social_accounts", "deletion_due_at")
