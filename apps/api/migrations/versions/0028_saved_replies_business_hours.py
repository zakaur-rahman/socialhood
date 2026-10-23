"""Saved replies (GR-21) and business hours with away messages (GR-22).

- saved_replies: a workspace's snippets (title, shortcut, body); the shortcut is unique per
  workspace;
- business_hours: the workspace's weekly schedule (account null) and an account's own, with the
  away message and whether Auto mode works always or only out of hours;
- conversations.away_sent_at: when the away message was last sent, so it goes once per closed
  window;
- automations.hours_condition: run only inside or only outside business hours.

Expand-only: two new tables and nullable columns; nothing is rewritten. The automations'
send step that names a saved reply is part of the flow JSON, not the schema.

Revision ID: 0028
Revises: 0025
Create Date: 2026-10-26 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stamps() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "saved_replies",
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("shortcut", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_stamps(),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 60", name=op.f("ck_saved_replies_title_length")
        ),
        sa.CheckConstraint(
            "shortcut ~ '^[a-z0-9][a-z0-9_-]{0,29}$'",
            name=op.f("ck_saved_replies_shortcut_format"),
        ),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 1000", name=op.f("ck_saved_replies_body_length")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_saved_replies_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_saved_replies_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_replies")),
        sa.UniqueConstraint("workspace_id", "shortcut", name=op.f("uq_saved_replies_workspace_id_shortcut")),
    )
    op.create_index(op.f("ix_saved_replies_workspace_id"), "saved_replies", ["workspace_id"])

    op.create_table(
        "business_hours",
        sa.Column("social_account_id", sa.Uuid(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("away_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("away_message", sa.Text(), nullable=True),
        sa.Column("auto_mode", sa.Text(), server_default=sa.text("'always'"), nullable=False),
        *_stamps(),
        sa.CheckConstraint(
            "auto_mode IN ('always', 'out_of_hours')", name=op.f("ck_business_hours_auto_mode")
        ),
        sa.CheckConstraint(
            "away_message IS NULL OR char_length(away_message) <= 1000",
            name=op.f("ck_business_hours_away_message_length"),
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name=op.f("fk_business_hours_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_business_hours_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_hours")),
        sa.UniqueConstraint(
            "workspace_id",
            "social_account_id",
            name=op.f("uq_business_hours_workspace_id_social_account_id"),
        ),
    )
    op.create_index(op.f("ix_business_hours_workspace_id"), "business_hours", ["workspace_id"])
    op.create_index(
        "uq_business_hours_workspace",
        "business_hours",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("social_account_id IS NULL"),
    )

    op.add_column(
        "conversations", sa.Column("away_sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("automations", sa.Column("hours_condition", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_automations_hours_condition"),
        "automations",
        "hours_condition IS NULL OR hours_condition IN ('inside', 'outside')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_automations_hours_condition"), "automations", type_="check")
    op.drop_column("automations", "hours_condition")
    op.drop_column("conversations", "away_sent_at")
    op.drop_table("business_hours")
    op.drop_table("saved_replies")
