"""A reading on connect (C-213): a metric snapshot's window may be ``connect``.

Posts published before an account was connected have missed their early windows, so they showed
no figures until their next window (up to days away). One reading is taken after the first media
sync and stored as the ``connect`` window: it has no age, so it is shown as the post's lifetime
figures and never joins a comparison at an age. The window check is re-created with the new value.
Expand-only: a wider check, no rows change.

Revision ID: 0066
Revises: 0065
Create Date: 2026-11-27 13:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WINDOW_CHECK = "ck_post_metric_snapshots_window"
OLD_WINDOWS = ("1h", "6h", "23h", "24h", "72h", "7d", "30d")
NEW_WINDOWS = ("1h", "6h", "23h", "24h", "72h", "7d", "30d", "connect")


def _condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f'"window" IN ({listed})'


def upgrade() -> None:
    op.drop_constraint(op.f(WINDOW_CHECK), "post_metric_snapshots", type_="check")
    op.create_check_constraint(op.f(WINDOW_CHECK), "post_metric_snapshots", _condition(NEW_WINDOWS))


def downgrade() -> None:
    op.execute("DELETE FROM post_metric_snapshots WHERE \"window\" = 'connect'")
    op.drop_constraint(op.f(WINDOW_CHECK), "post_metric_snapshots", type_="check")
    op.create_check_constraint(op.f(WINDOW_CHECK), "post_metric_snapshots", _condition(OLD_WINDOWS))
