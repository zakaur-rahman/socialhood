"""The Agency plan (C-174): subscriptions.plan accepts ``agency``.

Revision ID: 0057
Revises: 0056
Create Date: 2026-11-04 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_subscriptions_plan"), "subscriptions", type_="check")
    op.create_check_constraint(
        op.f("ck_subscriptions_plan"), "subscriptions", "plan IN ('free', 'pro', 'max', 'agency')"
    )


def downgrade() -> None:
    # Older code has no Agency: Business is the nearest plan it knows.
    op.execute("UPDATE subscriptions SET plan = 'max' WHERE plan = 'agency'")
    op.drop_constraint(op.f("ck_subscriptions_plan"), "subscriptions", type_="check")
    op.create_check_constraint(
        op.f("ck_subscriptions_plan"), "subscriptions", "plan IN ('free', 'pro', 'max')"
    )
