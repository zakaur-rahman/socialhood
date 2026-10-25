"""WhatsApp catalogue messages (GR-33).

- catalogue_connections: the Meta commerce catalogue a workspace's products are copied to (one per
  workspace), through a connected WhatsApp number;
- catalogue_items: what has been sent to that catalogue, per variant or product, with a hash so an
  unchanged item is not sent again;
- messages.interactive: a WhatsApp product or product-list message (JSON; null for every other).

Expand-only: new tables and a nullable column; nothing is rewritten.

Revision ID: 0044
Revises: 0043
Create Date: 2026-10-25 16:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    op.add_column(
        "messages", sa.Column("interactive", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    op.create_table(
        "catalogue_connections",
        sa.Column("social_account_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_id", sa.Text(), nullable=False),
        sa.Column("catalog_name", sa.Text(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("connected_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("sync_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "status IN ('active', 'needs_reconnect')", name=op.f("ck_catalogue_connections_status")
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            name=op.f("fk_catalogue_connections_social_account_id_social_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connected_by_user_id"],
            ["users.id"],
            name=op.f("fk_catalogue_connections_connected_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_catalogue_connections_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalogue_connections")),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_catalogue_connections_workspace_id")),
    )
    op.create_index(
        op.f("ix_catalogue_connections_workspace_id"), "catalogue_connections", ["workspace_id"]
    )

    op.create_table(
        "catalogue_items",
        sa.Column("retailer_id", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "state IN ('pending', 'synced', 'error')", name=op.f("ck_catalogue_items_state")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_catalogue_items_product_id_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_catalogue_items_variant_id_product_variants"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_catalogue_items_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalogue_items")),
        sa.UniqueConstraint(
            "workspace_id", "retailer_id", name=op.f("uq_catalogue_items_workspace_id_retailer_id")
        ),
    )
    op.create_index(op.f("ix_catalogue_items_workspace_id"), "catalogue_items", ["workspace_id"])
    op.create_index("ix_catalogue_items_product_id", "catalogue_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("catalogue_items")
    op.drop_table("catalogue_connections")
    op.drop_column("messages", "interactive")
