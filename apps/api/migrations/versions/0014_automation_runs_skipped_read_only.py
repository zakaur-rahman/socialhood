"""Automation runs skipped because the account is read-only after a downgrade (FR-BIL-07):
automation_runs.result gains skipped_read_only.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-30 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESULTS = (
    "'queued', 'sent', 'partial', 'failed', 'skipped_cooldown', 'skipped_expired', 'escalated', "
    "'awaiting_reply'"
)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_automation_runs_result"), "automation_runs", type_="check")
    op.create_check_constraint(
        op.f("ck_automation_runs_result"),
        "automation_runs",
        f"result IN ({RESULTS}, 'skipped_read_only')",
    )


def downgrade() -> None:
    op.execute("UPDATE automation_runs SET result = 'failed' WHERE result = 'skipped_read_only'")
    op.drop_constraint(op.f("ck_automation_runs_result"), "automation_runs", type_="check")
    op.create_check_constraint(
        op.f("ck_automation_runs_result"), "automation_runs", f"result IN ({RESULTS})"
    )
