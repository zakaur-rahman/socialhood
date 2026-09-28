"""Identity, billing, AI settings and webhook events (T1.2, T1.5; §5.3, §5.5, §5.8, §5.9)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-28 14:49:31.067871+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("clerk_user_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("last_workspace_id", sa.Uuid(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("clerk_user_id", name=op.f("uq_users_clerk_user_id")),
    )
    op.create_index(
        "ix_users_lower_email", "users", [sa.literal_column("lower(email)")], unique=False
    )
    op.create_table(
        "webhook_events",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("platform_account_id", sa.Text(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'received'"), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "provider IN ('instagram', 'whatsapp', 'dodo', 'clerk')",
            name=op.f("ck_webhook_events_provider"),
        ),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'processed', 'ignored', 'failed')",
            name=op.f("ck_webhook_events_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
        sa.UniqueConstraint(
            "provider", "dedupe_key", name=op.f("uq_webhook_events_provider_dedupe_key")
        ),
    )
    op.create_index(
        "ix_webhook_events_status_received_at",
        "webhook_events",
        ["status", "received_at"],
        unique=False,
    )
    op.create_table(
        "workspaces",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'UTC'"), nullable=False),
        sa.Column("reply_language", sa.Text(), server_default=sa.text("'auto'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("trial_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checklist_dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("automation_disclosure", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$'", name=op.f("ck_workspaces_slug")
        ),
        sa.CheckConstraint("status IN ('active', 'deleting')", name=op.f("ck_workspaces_status")),
        sa.CheckConstraint(
            "automation_disclosure IS NULL OR char_length(automation_disclosure) <= 60",
            name=op.f("ck_workspaces_automation_disclosure"),
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 80", name=op.f("ck_workspaces_name")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name=op.f("fk_workspaces_owner_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("slug", name=op.f("uq_workspaces_slug")),
    )
    op.create_table(
        "ai_settings",
        sa.Column("business_name", sa.Text(), nullable=True),
        sa.Column("business_description", sa.Text(), nullable=True),
        sa.Column("tone", sa.Text(), server_default=sa.text("'friendly'"), nullable=False),
        sa.Column("emoji_policy", sa.Text(), server_default=sa.text("'light'"), nullable=False),
        sa.Column(
            "do_list", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "dont_list", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "escalation_phrases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("sign_off", sa.Text(), nullable=True),
        sa.Column("takeover_minutes", sa.Integer(), server_default=sa.text("120"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "emoji_policy IN ('none', 'light', 'lots')", name=op.f("ck_ai_settings_emoji_policy")
        ),
        sa.CheckConstraint(
            "tone IN ('friendly', 'professional', 'playful', 'concise')",
            name=op.f("ck_ai_settings_tone"),
        ),
        sa.CheckConstraint(
            "takeover_minutes IN (0, 30, 120, 1440)", name=op.f("ck_ai_settings_takeover_minutes")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_ai_settings_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_settings")),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_ai_settings_workspace_id")),
    )
    op.create_index(
        op.f("ix_ai_settings_workspace_id"), "ai_settings", ["workspace_id"], unique=False
    )
    op.create_table(
        "subscriptions",
        sa.Column("plan", sa.Text(), server_default=sa.text("'free'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'free'"), nullable=False),
        sa.Column("dodo_customer_id", sa.Text(), nullable=True),
        sa.Column("dodo_subscription_id", sa.Text(), nullable=True),
        sa.Column("dodo_product_id", sa.Text(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("billing_anchor_day", sa.SmallInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("plan IN ('free', 'pro', 'max')", name=op.f("ck_subscriptions_plan")),
        sa.CheckConstraint(
            "status IN ('free', 'trialing', 'active', 'on_hold', 'expired')",
            name=op.f("ck_subscriptions_status"),
        ),
        sa.CheckConstraint(
            "billing_anchor_day BETWEEN 1 AND 28", name=op.f("ck_subscriptions_billing_anchor_day")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_subscriptions_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint(
            "dodo_subscription_id", name=op.f("uq_subscriptions_dodo_subscription_id")
        ),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_subscriptions_workspace_id")),
    )
    op.create_index(
        op.f("ix_subscriptions_workspace_id"), "subscriptions", ["workspace_id"], unique=False
    )
    op.create_table(
        "usage_counters",
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("used", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=True),
        sa.Column("notified_80_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_100_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "metric IN ('ai_credits', 'scheduled_posts')", name=op.f("ck_usage_counters_metric")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_usage_counters_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_counters")),
        sa.UniqueConstraint(
            "workspace_id",
            "metric",
            "period_start",
            name=op.f("uq_usage_counters_workspace_id_metric_period_start"),
        ),
    )
    op.create_index(
        op.f("ix_usage_counters_workspace_id"), "usage_counters", ["workspace_id"], unique=False
    )
    op.create_table(
        "workspace_members",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), server_default=sa.text("'owner'"), nullable=False),
        sa.Column(
            "notification_prefs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(
                '\'{"email_digest": true, "push": {"needs_you": true, "new_lead": true, "window_closing": true, "account": true}}\'::jsonb'
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'agent')", name=op.f("ck_workspace_members_role")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_workspace_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_members_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_members")),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name=op.f("uq_workspace_members_workspace_id_user_id")
        ),
    )
    op.create_index(
        op.f("ix_workspace_members_user_id"), "workspace_members", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_workspace_members_workspace_id"),
        "workspace_members",
        ["workspace_id"],
        unique=False,
    )
    # users <-> workspaces reference each other, so this key is added once both exist.
    op.create_foreign_key(
        op.f("fk_users_last_workspace_id_workspaces"),
        "users",
        "workspaces",
        ["last_workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_users_last_workspace_id_workspaces"), "users", type_="foreignkey")
    op.drop_index(op.f("ix_workspace_members_workspace_id"), table_name="workspace_members")
    op.drop_index(op.f("ix_workspace_members_user_id"), table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index(op.f("ix_usage_counters_workspace_id"), table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index(op.f("ix_subscriptions_workspace_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index(op.f("ix_ai_settings_workspace_id"), table_name="ai_settings")
    op.drop_table("ai_settings")
    op.drop_table("workspaces")
    op.drop_index("ix_webhook_events_status_received_at", table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_index("ix_users_lower_email", table_name="users")
    op.drop_table("users")
