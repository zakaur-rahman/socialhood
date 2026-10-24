"""Website chat widget (GR-28).

- social_accounts.platform allows ``web``: a workspace's widget is an account of that platform;
- contact_consents.source allows ``widget``: the consent box in the widget's email form;
- one web account per workspace (a partial unique index);
- widget_settings: the widget's allowed domains, colour, texts, email capture and branding, one row
  per web account.

Expand-only: a wider check, a new check list, one new table.

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-27 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PLATFORMS = "platform IN ('instagram', 'whatsapp', 'facebook', 'linkedin')"
NEW_PLATFORMS = "platform IN ('instagram', 'whatsapp', 'facebook', 'linkedin', 'web')"
OLD_SOURCES = "source IN ('platform_optin', 'flow', 'stop_reply', 'member', 'import')"
NEW_SOURCES = "source IN ('platform_optin', 'flow', 'stop_reply', 'member', 'import', 'widget')"


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


def _swap(table: str, name: str, expression: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, expression)


def upgrade() -> None:
    _swap("social_accounts", "platform", NEW_PLATFORMS)
    _swap("contact_consents", "source", NEW_SOURCES)
    op.create_index(
        "uq_social_accounts_workspace_web",
        "social_accounts",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("platform = 'web'"),
    )

    op.create_table(
        "widget_settings",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "allowed_domains",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("accent_color", sa.Text(), server_default=sa.text("'#4467E6'"), nullable=False),
        sa.Column("title", sa.Text(), server_default=sa.text("'Chat with us'"), nullable=False),
        sa.Column(
            "greeting",
            sa.Text(),
            server_default=sa.text("'Hi! How can we help?'"),
            nullable=False,
        ),
        sa.Column("position", sa.Text(), server_default=sa.text("'right'"), nullable=False),
        sa.Column("email_capture", sa.Text(), server_default=sa.text("'optional'"), nullable=False),
        sa.Column(
            "email_prompt",
            sa.Text(),
            server_default=sa.text("'Leave your email so we can reply if you leave this page.'"),
            nullable=False,
        ),
        sa.Column(
            "marketing_consent_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "marketing_consent_text",
            sa.Text(),
            server_default=sa.text("'Email me news and offers. You can unsubscribe at any time.'"),
            nullable=False,
        ),
        sa.Column("show_branding", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_stamps(),
        sa.CheckConstraint(
            "position IN ('right', 'left')", name=op.f("ck_widget_settings_position")
        ),
        sa.CheckConstraint(
            "email_capture IN ('off', 'optional', 'required')",
            name=op.f("ck_widget_settings_email_capture"),
        ),
        sa.CheckConstraint(
            "accent_color ~ '^#[0-9A-Fa-f]{6}$'", name=op.f("ck_widget_settings_accent_color")
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 40", name=op.f("ck_widget_settings_title_length")
        ),
        sa.CheckConstraint(
            "char_length(greeting) BETWEEN 1 AND 300",
            name=op.f("ck_widget_settings_greeting_length"),
        ),
        sa.CheckConstraint(
            "char_length(email_prompt) BETWEEN 1 AND 200",
            name=op.f("ck_widget_settings_email_prompt_length"),
        ),
        sa.CheckConstraint(
            "char_length(marketing_consent_text) BETWEEN 1 AND 300",
            name=op.f("ck_widget_settings_marketing_consent_text_length"),
        ),
        sa.CheckConstraint(
            "cardinality(allowed_domains) <= 20",
            name=op.f("ck_widget_settings_allowed_domains_count"),
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name=op.f("fk_widget_settings_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_widget_settings_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_widget_settings")),
        sa.UniqueConstraint("social_account_id", name=op.f("uq_widget_settings_social_account_id")),
    )
    op.create_index(op.f("ix_widget_settings_workspace_id"), "widget_settings", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("widget_settings")
    op.drop_index("uq_social_accounts_workspace_web", table_name="social_accounts")
    # Rows that use the new values would block the narrower checks: remove them first.
    op.execute("DELETE FROM contact_consents WHERE source = 'widget'")
    op.execute("DELETE FROM social_accounts WHERE platform = 'web'")
    _swap("contact_consents", "source", OLD_SOURCES)
    _swap("social_accounts", "platform", OLD_PLATFORMS)
