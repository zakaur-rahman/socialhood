"""Story insights (C-131): a metric snapshot's window may be ``23h``.

A Story is gone after 24 hours, so its insights are read at 1 h, 6 h and 23 h; the 23 h reading
is only ever taken for Stories. The window check is re-created with the new value. Expand-only:
a wider check, no rows change.

Revision ID: 0049
Revises: 0048
Create Date: 2026-10-25 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WINDOW_CHECK = "ck_post_metric_snapshots_window"
OLD_WINDOWS = ("1h", "6h", "24h", "72h", "7d", "30d")
NEW_WINDOWS = ("1h", "6h", "23h", "24h", "72h", "7d", "30d")


def _condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f'"window" IN ({listed})'


def upgrade() -> None:
    op.drop_constraint(op.f(WINDOW_CHECK), "post_metric_snapshots", type_="check")
    op.create_check_constraint(
        op.f(WINDOW_CHECK), "post_metric_snapshots", _condition(NEW_WINDOWS)
    )


def downgrade() -> None:
    # A Story's 23 h reading can't stay under the old check.
    op.execute('DELETE FROM post_metric_snapshots WHERE "window" = \'23h\'')
    op.drop_constraint(op.f(WINDOW_CHECK), "post_metric_snapshots", type_="check")
    op.create_check_constraint(
        op.f(WINDOW_CHECK), "post_metric_snapshots", _condition(OLD_WINDOWS)
    )
