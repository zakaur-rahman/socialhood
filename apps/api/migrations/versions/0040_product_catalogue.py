"""Product catalogue (GR-31): products, their variants and the workspace's Shopify store.

- products: name, price, stock, image, link; money is integer minor units with an ISO 4217 code;
- product_variants: size, colour…, each with its own price, stock and optional SKU;
- shopify_connections: one per workspace, with Shopify's access token encrypted;
- webhook_events.provider accepts ``shopify`` (the check is re-created).

Expand-only: new tables and a wider check; nothing is rewritten.

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-25 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_CHECK = "ck_webhook_events_provider"
OLD_PROVIDERS = ("instagram", "whatsapp", "facebook", "dodo", "clerk")
NEW_PROVIDERS = ("instagram", "whatsapp", "facebook", "shopify", "dodo", "clerk")


def _provider_condition(values: Sequence[str]) -> str:
    return f"provider IN ({', '.join(repr(v) for v in values)})"


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
    op.drop_constraint(op.f(PROVIDER_CHECK), "webhook_events", type_="check")
    op.create_check_constraint(
        op.f(PROVIDER_CHECK), "webhook_events", _provider_condition(NEW_PROVIDERS)
    )

    op.create_table(
        "products",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), server_default=sa.text("'INR'"), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("image_asset_id", sa.Uuid(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        *_id_and_times(),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_products_name_length")
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_products_currency_format")),
        sa.CheckConstraint(
            "price_minor IS NULL OR price_minor >= 0", name=op.f("ck_products_price_minor")
        ),
        sa.CheckConstraint("stock IS NULL OR stock >= 0", name=op.f("ck_products_stock")),
        sa.CheckConstraint(
            "source IN ('manual', 'csv', 'shopify')", name=op.f("ck_products_source")
        ),
        sa.ForeignKeyConstraint(
            ["image_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_products_image_asset_id_media_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_products_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("workspace_id", "sku", name=op.f("uq_products_workspace_id_sku")),
        sa.UniqueConstraint(
            "workspace_id", "external_id", name=op.f("uq_products_workspace_id_external_id")
        ),
    )
    op.create_index(op.f("ix_products_workspace_id"), "products", ["workspace_id"])
    op.create_index(
        "ix_products_listing", "products", ["workspace_id", sa.text("created_at DESC"), "id"]
    )

    op.create_table(
        "product_variants",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("position", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120", name=op.f("ck_product_variants_title_length")
        ),
        sa.CheckConstraint("price_minor >= 0", name=op.f("ck_product_variants_price_minor")),
        sa.CheckConstraint("stock IS NULL OR stock >= 0", name=op.f("ck_product_variants_stock")),
        sa.CheckConstraint(
            "jsonb_typeof(options) = 'object'", name=op.f("ck_product_variants_options_object")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_variants_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_product_variants_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_variants")),
        sa.UniqueConstraint(
            "product_id", "title", name=op.f("uq_product_variants_product_id_title")
        ),
        sa.UniqueConstraint(
            "workspace_id", "sku", name=op.f("uq_product_variants_workspace_id_sku")
        ),
    )
    op.create_index(op.f("ix_product_variants_workspace_id"), "product_variants", ["workspace_id"])
    op.create_index(
        "ix_product_variants_product_id_position", "product_variants", ["product_id", "position"]
    )

    op.create_table(
        "shopify_connections",
        sa.Column("shop_domain", sa.Text(), nullable=False),
        sa.Column("shop_name", sa.Text(), nullable=True),
        sa.Column("storefront_domain", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("token_enc", sa.LargeBinary(), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("connected_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "webhook_topics",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("sync_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("products_synced", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("products_skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
        *_id_and_times(),
        sa.CheckConstraint(
            "status IN ('active', 'needs_reconnect')", name=op.f("ck_shopify_connections_status")
        ),
        sa.ForeignKeyConstraint(
            ["connected_by_user_id"],
            ["users.id"],
            name=op.f("fk_shopify_connections_connected_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_shopify_connections_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopify_connections")),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_shopify_connections_workspace_id")),
        sa.UniqueConstraint("shop_domain", name=op.f("uq_shopify_connections_shop_domain")),
    )
    op.create_index(
        op.f("ix_shopify_connections_workspace_id"), "shopify_connections", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_table("shopify_connections")
    op.drop_table("product_variants")
    op.drop_table("products")
    op.execute("DELETE FROM webhook_events WHERE provider = 'shopify'")
    op.drop_constraint(op.f(PROVIDER_CHECK), "webhook_events", type_="check")
    op.create_check_constraint(
        op.f(PROVIDER_CHECK), "webhook_events", _provider_condition(OLD_PROVIDERS)
    )
