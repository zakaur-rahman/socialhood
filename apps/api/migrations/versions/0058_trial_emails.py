"""Trial use that survives account deletion (TR-BIL-05): a hash of each owner email that has had
the trial, filled from the workspaces that have used one.

Revision ID: 0058
Revises: 0057
Create Date: 2026-11-04 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trial_emails",
        sa.Column("email_hash", sa.Text(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email_hash", name=op.f("pk_trial_emails")),
    )
    op.execute(
        """
        INSERT INTO trial_emails (email_hash, used_at)
        SELECT encode(sha256(convert_to(lower(trim(u.email)), 'UTF8')), 'hex'),
               min(w.trial_used_at)
        FROM workspaces w
        JOIN users u ON u.id = w.owner_user_id
        WHERE w.trial_used_at IS NOT NULL
        GROUP BY 1
        """
    )


def downgrade() -> None:
    op.drop_table("trial_emails")
