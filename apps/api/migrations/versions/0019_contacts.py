"""Contacts foundation (GR-02): tags, custom fields, consent, and what a business knows.

- tags (per workspace, a unique case-insensitive name, an identity-palette colour) and
  contact_tags (which contacts carry them);
- contact_field_definitions (a workspace's custom fields: key, label, type, choice options) and
  contacts.fields (their values by key);
- contact_consents: an append-only history of marketing consent per channel, with its source
  and evidence;
- contacts.email, phone (E.164), each with *_source and *_verified, and last_activity_at (their
  activity outside the conversation, a comment), backfilled from their last comment.

Expand-only: new tables and columns; last_activity_at is backfilled once.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-23 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIELD_TYPES = ("text", "email", "phone", "number", "date", "choice")
CHANNELS = ("instagram", "whatsapp", "email")
PURPOSES = ("marketing",)
STATUSES = ("granted", "revoked")
SOURCES = ("platform_optin", "flow", "stop_reply", "member", "import")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def _workspace(table: str) -> list[object]:
    return [
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f(f"fk_{table}_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        *_workspace("tags"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 40", name=op.f("ck_tags_name_length")),
        sa.CheckConstraint("color BETWEEN 0 AND 15", name=op.f("ck_tags_color")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
    )
    op.create_index(op.f("ix_tags_workspace_id"), "tags", ["workspace_id"])
    op.create_index(
        "uq_tags_workspace_name",
        "tags",
        ["workspace_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "contact_tags",
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        *_workspace("contact_tags"),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_contact_tags_contact_id_contacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name=op.f("fk_contact_tags_tag_id_tags"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["added_by_user_id"],
            ["users.id"],
            name=op.f("fk_contact_tags_added_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_tags")),
        sa.UniqueConstraint("contact_id", "tag_id", name=op.f("uq_contact_tags_contact_id_tag_id")),
    )
    op.create_index(op.f("ix_contact_tags_workspace_id"), "contact_tags", ["workspace_id"])
    op.create_index("ix_contact_tags_tag", "contact_tags", ["tag_id"])

    op.create_table(
        "contact_field_definitions",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), server_default=sa.text("'text'"), nullable=False),
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("position", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        *_workspace("contact_field_definitions"),
        sa.CheckConstraint(
            "key ~ '^[a-z][a-z0-9_]{0,39}$'", name=op.f("ck_contact_field_definitions_key_format")
        ),
        sa.CheckConstraint(
            "char_length(label) BETWEEN 1 AND 60",
            name=op.f("ck_contact_field_definitions_label_length"),
        ),
        sa.CheckConstraint(
            _in("type", FIELD_TYPES), name=op.f("ck_contact_field_definitions_type")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_field_definitions")),
        sa.UniqueConstraint(
            "workspace_id", "key", name=op.f("uq_contact_field_definitions_workspace_id_key")
        ),
    )
    op.create_index(
        op.f("ix_contact_field_definitions_workspace_id"),
        "contact_field_definitions",
        ["workspace_id"],
    )

    op.create_table(
        "contact_consents",
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), server_default=sa.text("'marketing'"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *_timestamps(),
        *_workspace("contact_consents"),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_contact_consents_contact_id_contacts"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(_in("channel", CHANNELS), name=op.f("ck_contact_consents_channel")),
        sa.CheckConstraint(_in("purpose", PURPOSES), name=op.f("ck_contact_consents_purpose")),
        sa.CheckConstraint(_in("status", STATUSES), name=op.f("ck_contact_consents_status")),
        sa.CheckConstraint(_in("source", SOURCES), name=op.f("ck_contact_consents_source")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_consents")),
    )
    op.create_index(op.f("ix_contact_consents_workspace_id"), "contact_consents", ["workspace_id"])
    op.create_index(
        "ix_contact_consents_current",
        "contact_consents",
        ["contact_id", "channel", "purpose", sa.text("occurred_at DESC")],
    )

    op.add_column(
        "contacts",
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("contacts", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("email_source", sa.Text(), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("contacts", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("phone_source", sa.Text(), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("phone_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "contacts", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Backfill: their last comment.
    op.execute(
        "UPDATE contacts c SET last_activity_at ="
        " (SELECT max(m.commented_at) FROM comments m WHERE m.contact_id = c.id)"
    )


def downgrade() -> None:
    for column in (
        "last_activity_at",
        "phone_verified",
        "phone_source",
        "phone",
        "email_verified",
        "email_source",
        "email",
        "fields",
    ):
        op.drop_column("contacts", column)
    op.drop_table("contact_consents")
    op.drop_table("contact_field_definitions")
    op.drop_table("contact_tags")
    op.drop_table("tags")
