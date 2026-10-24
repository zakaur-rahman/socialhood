"""WhatsApp broadcasts (GR-23): broadcasts, their recipients and a number's health.

- messages.source accepts ``broadcast`` (the check is re-created), so a broadcast's messages are
  told apart from an automation's in the inbox and in Activity;
- broadcasts: one row per broadcast (template copy, variable mapping, segment, schedule, status,
  cost estimate);
- broadcast_recipients: the audience fixed when the broadcast starts, with the state we know and
  the message that carries WhatsApp's statuses;
- whatsapp_number_health: a number's quality rating and daily limit as last heard.

Expand-only: a wider check and new tables; nothing is rewritten.

Revision ID: 0036
Revises: 0030
Create Date: 2026-10-24 18:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_CHECK = "ck_messages_source"
OLD_SOURCES = ("customer", "human", "ai_auto", "automation", "native_app", "system")
NEW_SOURCES = (*OLD_SOURCES[:4], "broadcast", *OLD_SOURCES[4:])


def _source_condition(values: Sequence[str]) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"source IN ({listed})"


def _id_and_times() -> list[sa.Column[object]]:
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
    op.drop_constraint(op.f(SOURCE_CHECK), "messages", type_="check")
    op.create_check_constraint(op.f(SOURCE_CHECK), "messages", _source_condition(NEW_SOURCES))

    op.create_table(
        "broadcasts",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("segment_id", sa.Uuid(), nullable=True),
        sa.Column("segment_name", sa.Text(), nullable=False),
        sa.Column("template_name", sa.Text(), nullable=False),
        sa.Column("template_language", sa.Text(), nullable=False),
        sa.Column("template_category", sa.Text(), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_code", sa.Text(), nullable=True),
        sa.Column("paused_reason", sa.Text(), nullable=True),
        sa.Column("audience_size", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rate_per_message", sa.Numeric(10, 4), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_currency", sa.Text(), server_default=sa.text("'INR'"), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "status IN ('draft', 'scheduled', 'sending', 'paused', 'completed', 'cancelled',"
            " 'failed')",
            name=op.f("ck_broadcasts_status"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 80", name=op.f("ck_broadcasts_name_length")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(variables) = 'array'", name=op.f("ck_broadcasts_variables_array")
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name=op.f("fk_broadcasts_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["contact_segments.id"],
            name=op.f("fk_broadcasts_segment_id_contact_segments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_broadcasts_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_broadcasts_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_broadcasts")),
    )
    op.create_index(op.f("ix_broadcasts_workspace_id"), "broadcasts", ["workspace_id"])
    op.create_index(
        "ix_broadcasts_listing",
        "broadcasts",
        ["workspace_id", sa.text("created_at DESC"), "id"],
    )
    op.create_index(
        "ix_broadcasts_active",
        "broadcasts",
        ["status", "scheduled_at"],
        postgresql_where=sa.text("status IN ('scheduled', 'sending')"),
    )

    op.create_table(
        "broadcast_recipients",
        sa.Column("broadcast_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "state IN ('pending', 'dispatched', 'skipped', 'failed')",
            name=op.f("ck_broadcast_recipients_state"),
        ),
        sa.CheckConstraint(
            "skip_reason IS NULL OR skip_reason IN ('opted_out', 'no_consent', 'missing_value',"
            " 'cancelled')",
            name=op.f("ck_broadcast_recipients_skip_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["broadcast_id"],
            ["broadcasts.id"],
            name=op.f("fk_broadcast_recipients_broadcast_id_broadcasts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_broadcast_recipients_contact_id_contacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_broadcast_recipients_message_id_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_broadcast_recipients_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_broadcast_recipients")),
        sa.UniqueConstraint(
            "broadcast_id", "contact_id", name=op.f("uq_broadcast_recipients_broadcast_id_contact_id")
        ),
    )
    op.create_index(
        op.f("ix_broadcast_recipients_workspace_id"), "broadcast_recipients", ["workspace_id"]
    )
    op.create_index(
        "ix_broadcast_recipients_queue",
        "broadcast_recipients",
        ["broadcast_id", "state", "position"],
    )
    op.create_index("ix_broadcast_recipients_contact", "broadcast_recipients", ["contact_id"])
    op.create_index("ix_broadcast_recipients_message", "broadcast_recipients", ["message_id"])
    op.create_index(
        "ix_broadcast_recipients_dispatched",
        "broadcast_recipients",
        ["workspace_id", "dispatched_at"],
        postgresql_where=sa.text("dispatched_at IS NOT NULL"),
    )

    op.create_table(
        "whatsapp_number_health",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quality_rating", sa.Text(), server_default=sa.text("'unknown'"), nullable=False
        ),
        sa.Column("messaging_tier", sa.Text(), nullable=True),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), server_default=sa.text("'webhook'"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        *_id_and_times(),
        sa.CheckConstraint(
            "quality_rating IN ('green', 'yellow', 'red', 'unknown')",
            name=op.f("ck_whatsapp_number_health_quality_rating"),
        ),
        sa.CheckConstraint(
            "daily_limit IS NULL OR daily_limit > 0",
            name=op.f("ck_whatsapp_number_health_daily_limit"),
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name=op.f("fk_whatsapp_number_health_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_whatsapp_number_health_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_number_health")),
        sa.UniqueConstraint(
            "social_account_id", name=op.f("uq_whatsapp_number_health_social_account_id")
        ),
    )
    op.create_index(
        op.f("ix_whatsapp_number_health_workspace_id"), "whatsapp_number_health", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_table("whatsapp_number_health")
    op.drop_table("broadcast_recipients")
    op.drop_table("broadcasts")
    # Messages from a broadcast can't stay under the old check: they become automation messages.
    op.execute("UPDATE messages SET source = 'automation' WHERE source = 'broadcast'")
    op.drop_constraint(op.f(SOURCE_CHECK), "messages", type_="check")
    op.create_check_constraint(op.f(SOURCE_CHECK), "messages", _source_condition(OLD_SOURCES))
