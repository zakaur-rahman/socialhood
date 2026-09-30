"""Workspace deletion (T9.6; FR-ACC-05, F-16): who asked, and a deleting workspace may outlive its
owner.

- workspaces.deletion_requested_by_user_id records who asked (deletion_requested_at already
  records when); SET NULL when that user is deleted.
- workspaces.owner_user_id becomes ON DELETE SET NULL and nullable, but only a deleting workspace
  may lack an owner (ck_workspaces_owner). Clerk's user.deleted marks the person's solely owned
  workspaces deleting and deletes the user at once; the workspace (with its subscription row, so
  a failed Dodo cancel is retried) is purged afterwards. An active workspace's owner still can't
  be deleted from under it: the SET NULL would break the check.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-30 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER_FK = "fk_workspaces_owner_user_id_users"
REQUESTER_FK = "fk_workspaces_deletion_requested_by_user_id_users"


def upgrade() -> None:
    op.add_column(
        "workspaces", sa.Column("deletion_requested_by_user_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        op.f(REQUESTER_FK),
        "workspaces",
        "users",
        ["deletion_requested_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(op.f(OWNER_FK), "workspaces", type_="foreignkey")
    op.alter_column("workspaces", "owner_user_id", existing_type=sa.Uuid(), nullable=True)
    op.create_foreign_key(
        op.f(OWNER_FK), "workspaces", "users", ["owner_user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_check_constraint(
        op.f("ck_workspaces_owner"),
        "workspaces",
        "owner_user_id IS NOT NULL OR status = 'deleting'",
    )


def downgrade() -> None:
    # A deleting workspace without an owner can't go back under NOT NULL; it was going anyway.
    op.execute("DELETE FROM workspaces WHERE owner_user_id IS NULL")
    op.drop_constraint(op.f("ck_workspaces_owner"), "workspaces", type_="check")
    op.drop_constraint(op.f(OWNER_FK), "workspaces", type_="foreignkey")
    op.alter_column("workspaces", "owner_user_id", existing_type=sa.Uuid(), nullable=False)
    op.create_foreign_key(op.f(OWNER_FK), "workspaces", "users", ["owner_user_id"], ["id"])
    op.drop_constraint(op.f(REQUESTER_FK), "workspaces", type_="foreignkey")
    op.drop_column("workspaces", "deletion_requested_by_user_id")
