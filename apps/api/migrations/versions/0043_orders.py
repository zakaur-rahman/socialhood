"""Orders and payment requests (GR-32).

- payment_connections: the workspace's Razorpay keys (encrypted) and/or UPI address;
- orders: an order for a contact, with its status, total, address and how it was paid;
- order_items: the lines, a snapshot of the catalogue's name and price when the order was made;
- webhook_events.provider accepts ``razorpay`` (the check is re-created).

Expand-only: new tables and a wider check; nothing is rewritten.

Revision ID: 0043
Revises: 0042
Create Date: 2026-10-25 15:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROVIDER_CHECK = "ck_webhook_events_provider"
OLD_PROVIDERS = ("instagram", "whatsapp", "facebook", "shopify", "dodo", "clerk")
NEW_PROVIDERS = ("instagram", "whatsapp", "facebook", "shopify", "razorpay", "dodo", "clerk")


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
        "payment_connections",
        sa.Column("razorpay_key_id", sa.Text(), nullable=True),
        sa.Column("razorpay_secret_enc", sa.LargeBinary(), nullable=True),
        sa.Column("razorpay_webhook_secret_enc", sa.LargeBinary(), nullable=True),
        sa.Column("razorpay_last_error", sa.Text(), nullable=True),
        sa.Column("webhook_token", sa.Text(), nullable=False),
        sa.Column("webhook_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upi_vpa", sa.Text(), nullable=True),
        sa.Column("upi_name", sa.Text(), nullable=True),
        sa.Column("connected_by_user_id", sa.Uuid(), nullable=True),
        *_id_and_times(),
        sa.ForeignKeyConstraint(
            ["connected_by_user_id"],
            ["users.id"],
            name=op.f("fk_payment_connections_connected_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_payment_connections_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_connections")),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_payment_connections_workspace_id")),
        sa.UniqueConstraint("webhook_token", name=op.f("uq_payment_connections_webhook_token")),
    )
    op.create_index(
        op.f("ix_payment_connections_workspace_id"), "payment_connections", ["workspace_id"]
    )

    op.create_table(
        "orders",
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'inbox'"), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("payment_link_id", sa.Text(), nullable=True),
        sa.Column("payment_link_url", sa.Text(), nullable=True),
        sa.Column("payment_reference", sa.Text(), nullable=True),
        sa.Column("link_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint(
            "status IN ('draft', 'awaiting_payment', 'paid', 'cancelled', 'expired')",
            name=op.f("ck_orders_status"),
        ),
        sa.CheckConstraint("source IN ('inbox', 'whatsapp')", name=op.f("ck_orders_source")),
        sa.CheckConstraint(
            "payment_method IS NULL OR payment_method IN ('razorpay', 'upi')",
            name=op.f("ck_orders_payment_method"),
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_orders_currency_format")),
        sa.CheckConstraint("total_minor >= 0", name=op.f("ck_orders_total_minor")),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_orders_contact_id_contacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_orders_conversation_id_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["paid_by_user_id"],
            ["users.id"],
            name=op.f("fk_orders_paid_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_orders_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_orders_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("workspace_id", "number", name=op.f("uq_orders_workspace_id_number")),
    )
    op.create_index(op.f("ix_orders_workspace_id"), "orders", ["workspace_id"])
    op.create_index(
        "ix_orders_listing", "orders", ["workspace_id", sa.text("created_at DESC"), "id"]
    )
    op.create_index("ix_orders_contact_id", "orders", ["contact_id"])
    op.create_index("ix_orders_payment_link_id", "orders", ["payment_link_id"])

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("variant_title", sa.Text(), nullable=True),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        *_id_and_times(),
        sa.CheckConstraint("quantity BETWEEN 1 AND 999", name=op.f("ck_order_items_quantity")),
        sa.CheckConstraint("unit_price_minor >= 0", name=op.f("ck_order_items_unit_price_minor")),
        sa.CheckConstraint("line_total_minor >= 0", name=op.f("ck_order_items_line_total_minor")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_order_items_product_id_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_order_items_variant_id_product_variants"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_order_items_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
    )
    op.create_index(op.f("ix_order_items_workspace_id"), "order_items", ["workspace_id"])
    op.create_index("ix_order_items_order_id_position", "order_items", ["order_id", "position"])


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("payment_connections")
    op.execute("DELETE FROM webhook_events WHERE provider = 'razorpay'")
    op.drop_constraint(op.f(PROVIDER_CHECK), "webhook_events", type_="check")
    op.create_check_constraint(
        op.f(PROVIDER_CHECK), "webhook_events", _provider_condition(OLD_PROVIDERS)
    )
