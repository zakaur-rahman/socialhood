"""Account data deletion (C-067; FR-CON-06, F-16): a connected account's data can be purged.

- social_accounts.deletion_requested_at and deletion_requested_by_user_id: the account is being
  deleted (it shows "Deleting…" until purge_account_data removes it), who asked and when. A null
  requester is Meta's data-deletion callback. SET NULL when that user is deleted.
- data_deletion_requests.status takes ``failed``: a purge for the request failed and is being
  retried (it goes back to processing on the next try, then completed).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-01 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUESTER_FK = "fk_social_accounts_deletion_requested_by_user_id_users"
STATUS_CHECK = "ck_data_deletion_requests_status"


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "social_accounts", sa.Column("deletion_requested_by_user_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        op.f(REQUESTER_FK),
        "social_accounts",
        "users",
        ["deletion_requested_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(op.f(STATUS_CHECK), "data_deletion_requests", type_="check")
    op.create_check_constraint(
        op.f(STATUS_CHECK),
        "data_deletion_requests",
        "status IN ('received', 'processing', 'completed', 'failed')",
    )


def downgrade() -> None:
    # A failed request is still being retried: processing is the closest the old states have.
    op.execute("UPDATE data_deletion_requests SET status = 'processing' WHERE status = 'failed'")
    op.drop_constraint(op.f(STATUS_CHECK), "data_deletion_requests", type_="check")
    op.create_check_constraint(
        op.f(STATUS_CHECK),
        "data_deletion_requests",
        "status IN ('received', 'processing', 'completed')",
    )
    op.drop_constraint(op.f(REQUESTER_FK), "social_accounts", type_="foreignkey")
    op.drop_column("social_accounts", "deletion_requested_by_user_id")
    op.drop_column("social_accounts", "deletion_requested_at")
