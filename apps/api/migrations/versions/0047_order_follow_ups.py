"""Order follow-ups (GR-32): part payments, refunds, shipping and flow-made orders.

- orders: amount_paid_minor and amount_refunded_minor, accept_partial, fulfilled_at and
  fulfilment_note; the status check gains partially_paid, fulfilled and refunded; the source
  check gains ``flow`` (an order made by a "request payment" step);
- order_payments: one row per payment toward an order (a Razorpay payment id keeps a re-delivered
  webhook from counting twice);
- order_refunds: one row per refund of (part of) a payment, through Razorpay or recorded by hand.

Expand-only: new columns with defaults, two new tables and wider checks; nothing is rewritten.
Existing paid orders are backfilled so the new totals agree with their status.

Revision ID: 0047
Revises: 0046
Create Date: 2026-10-26 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUS_OLD = "status IN ('draft', 'awaiting_payment', 'paid', 'cancelled', 'expired')"
STATUS_NEW = (
    "status IN ('draft', 'awaiting_payment', 'partially_paid', 'paid', 'fulfilled', "
    "'refunded', 'cancelled', 'expired')"
)
SOURCE_OLD = "source IN ('inbox', 'whatsapp')"
SOURCE_NEW = "source IN ('inbox', 'whatsapp', 'flow')"


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


def _swap(name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_orders_{name}"), "orders", type_="check")
    op.create_check_constraint(op.f(f"ck_orders_{name}"), "orders", condition)


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "amount_paid_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "amount_refunded_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.add_column(
        "orders",
        sa.Column("accept_partial", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("orders", sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("fulfilment_note", sa.Text(), nullable=True))
    # An order that was paid before this change was paid in full.
    op.execute("UPDATE orders SET amount_paid_minor = total_minor WHERE status = 'paid'")
    op.create_check_constraint(
        op.f("ck_orders_amount_paid_minor"), "orders", "amount_paid_minor >= 0"
    )
    op.create_check_constraint(
        op.f("ck_orders_amount_refunded_minor"),
        "orders",
        "amount_refunded_minor >= 0 AND amount_refunded_minor <= amount_paid_minor",
    )
    _swap("status", STATUS_NEW)
    _swap("source", SOURCE_NEW)

    op.create_table(
        "order_payments",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("razorpay_payment_id", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        *_id_and_times(),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_order_payments_amount_minor")),
        sa.CheckConstraint("method IN ('razorpay', 'upi')", name=op.f("ck_order_payments_method")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_payments_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_order_payments_recorded_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_order_payments_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_payments")),
        sa.UniqueConstraint(
            "order_id",
            "razorpay_payment_id",
            name=op.f("uq_order_payments_order_id_razorpay_payment_id"),
        ),
    )
    op.create_index(op.f("ix_order_payments_workspace_id"), "order_payments", ["workspace_id"])
    op.create_index("ix_order_payments_order_id", "order_payments", ["order_id"])
    op.create_index(
        "ix_order_payments_razorpay_payment_id", "order_payments", ["razorpay_payment_id"]
    )
    # Orders paid before this change get the one payment they had, so a refund can find it.
    op.execute(
        "INSERT INTO order_payments (workspace_id, order_id, amount_minor, method, reference,"
        " razorpay_payment_id, recorded_by_user_id, paid_at)"
        " SELECT workspace_id, id, total_minor, COALESCE(payment_method, 'upi'),"
        " CASE WHEN payment_method = 'upi' THEN payment_reference END,"
        " CASE WHEN payment_method = 'razorpay' THEN payment_reference END,"
        " paid_by_user_id, COALESCE(paid_at, updated_at)"
        " FROM orders WHERE status = 'paid' AND total_minor > 0"
    )

    op.create_table(
        "order_refunds",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("razorpay_refund_id", sa.Text(), nullable=True),
        sa.Column("failure", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        *_id_and_times(),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_order_refunds_amount_minor")),
        sa.CheckConstraint(
            "method IN ('razorpay', 'manual')", name=op.f("ck_order_refunds_method")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processed', 'failed')", name=op.f("ck_order_refunds_status")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_refunds_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["order_payments.id"],
            name=op.f("fk_order_refunds_payment_id_order_payments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_order_refunds_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_order_refunds_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_refunds")),
        sa.UniqueConstraint(
            "order_id",
            "razorpay_refund_id",
            name=op.f("uq_order_refunds_order_id_razorpay_refund_id"),
        ),
    )
    op.create_index(op.f("ix_order_refunds_workspace_id"), "order_refunds", ["workspace_id"])
    op.create_index("ix_order_refunds_order_id", "order_refunds", ["order_id"])
    op.create_index("ix_order_refunds_razorpay_refund_id", "order_refunds", ["razorpay_refund_id"])


def downgrade() -> None:
    op.drop_table("order_refunds")
    op.drop_table("order_payments")
    op.execute("UPDATE orders SET status = 'paid' WHERE status IN ('fulfilled', 'refunded')")
    op.execute("UPDATE orders SET status = 'awaiting_payment' WHERE status = 'partially_paid'")
    op.execute("UPDATE orders SET source = 'inbox' WHERE source = 'flow'")
    _swap("source", SOURCE_OLD)
    _swap("status", STATUS_OLD)
    op.drop_constraint(op.f("ck_orders_amount_refunded_minor"), "orders", type_="check")
    op.drop_constraint(op.f("ck_orders_amount_paid_minor"), "orders", type_="check")
    op.drop_column("orders", "fulfilment_note")
    op.drop_column("orders", "fulfilled_at")
    op.drop_column("orders", "accept_partial")
    op.drop_column("orders", "amount_refunded_minor")
    op.drop_column("orders", "amount_paid_minor")
