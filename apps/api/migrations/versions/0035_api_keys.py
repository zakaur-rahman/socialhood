"""Workspace API keys and the webhook endpoints a key subscribed (GR-25, GR-26).

- api_keys: one row per key (name, a visible prefix, the SHA-256 of the key, scopes, last used,
  revoked); the key itself is never stored;
- webhook_endpoints.api_key_id: the key that subscribed a Zapier REST hook; the endpoint goes
  with the key.

Expand-only: a new table and a nullable column.

Revision ID: 0035
Revises: 0030
Create Date: 2026-10-24 16:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 80", name=op.f("ck_api_keys_name_length")
        ),
        sa.CheckConstraint("cardinality(scopes) BETWEEN 1 AND 20", name=op.f("ck_api_keys_scopes")),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_api_keys_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_api_keys_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_api_keys_key_hash")),
    )
    op.create_index(op.f("ix_api_keys_workspace_id"), "api_keys", ["workspace_id"])

    op.add_column("webhook_endpoints", sa.Column("api_key_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_webhook_endpoints_api_key_id_api_keys"),
        "webhook_endpoints",
        "api_keys",
        ["api_key_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_webhook_endpoints_api_key_id",
        "webhook_endpoints",
        ["api_key_id"],
        postgresql_where=sa.text("api_key_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_endpoints_api_key_id", table_name="webhook_endpoints")
    op.drop_constraint(
        op.f("fk_webhook_endpoints_api_key_id_api_keys"), "webhook_endpoints", type_="foreignkey"
    )
    op.drop_column("webhook_endpoints", "api_key_id")
    op.drop_table("api_keys")
