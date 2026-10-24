"""Conversation assignment (GR-20): who has a conversation, who is available, round-robin.

- conversations.assignee_user_id / assigned_at: the member who has the conversation (null:
  nobody). Set to null if the user row goes (ON DELETE SET NULL). A partial index serves the
  "Assigned to me" view and filter;
- workspace_members.available_for_assignment: whether round-robin may hand the member new
  conversations (default true);
- workspaces.assignment_round_robin (default false) and assignment_cursor_user_id: the setting and
  the member who had the last turn.

Expand-only: nullable columns and columns with defaults, one index; nothing is rewritten.

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-25 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("assignee_user_id", sa.Uuid(), nullable=True))
    op.add_column(
        "conversations", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_conversations_assignee_user_id_users"),
        "conversations",
        "users",
        ["assignee_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_conversations_assignee"),
        "conversations",
        ["workspace_id", "assignee_user_id", sa.text("last_message_at DESC")],
        postgresql_where=sa.text("assignee_user_id IS NOT NULL"),
    )
    op.add_column(
        "workspace_members",
        sa.Column(
            "available_for_assignment",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "assignment_round_robin", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column("workspaces", sa.Column("assignment_cursor_user_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "assignment_cursor_user_id")
    op.drop_column("workspaces", "assignment_round_robin")
    op.drop_column("workspace_members", "available_for_assignment")
    op.drop_index(op.f("ix_conversations_assignee"), table_name="conversations")
    op.drop_constraint(
        op.f("fk_conversations_assignee_user_id_users"), "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "assigned_at")
    op.drop_column("conversations", "assignee_user_id")
