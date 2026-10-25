"""Orders and how they are paid (GR-32): the workspace's payment settings, an order for a contact
and its lines.

Money is an integer in the currency's minor units with its ISO 4217 code, like the catalogue
(GR-31); the lines are a **snapshot** of the product's name, variant and price when the order was
made, so a later price change never alters an order. The total is computed on the server from the
catalogue and never taken from a request.

Payments go to the business's own account: Razorpay with its own keys (``payment_connections``,
the secrets encrypted like platform tokens, SEC-03, and never returned) or a UPI address a
customer pays by hand. A Razorpay payment arrives as a signed webhook; a UPI payment has no
webhook, so a member marks the order paid and the audit trail says who and when.

Follow-ups (C-125): an order can be paid in parts (``order_payments``, one row per payment, so
``amount_paid_minor`` is their sum), refunded in full or in part (``order_refunds``, one row per
refund, through Razorpay with the business's own keys or recorded by hand), shipped (``fulfilled``)
and edited while nobody has paid.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class OrderStatus(StrEnum):
    DRAFT = "draft"  # made, no payment asked for yet
    AWAITING_PAYMENT = "awaiting_payment"  # a payment link or UPI request is out
    PARTIALLY_PAID = "partially_paid"  # some of the total has been paid
    PAID = "paid"
    FULFILLED = "fulfilled"  # paid and shipped (or handed over)
    REFUNDED = "refunded"  # everything paid has been given back
    CANCELLED = "cancelled"
    EXPIRED = "expired"  # the payment link ran out before it was paid


class PaymentMethod(StrEnum):
    RAZORPAY = "razorpay"
    UPI = "upi"


class OrderSource(StrEnum):
    INBOX = "inbox"  # a member made it from a conversation
    WHATSAPP = "whatsapp"  # the customer's cart (GR-33)
    FLOW = "flow"  # a "request payment" step in a flow


class RefundStatus(StrEnum):
    PENDING = "pending"  # Razorpay has it and has not finished
    PROCESSED = "processed"
    FAILED = "failed"


class RefundMethod(StrEnum):
    RAZORPAY = "razorpay"  # returned through the business's Razorpay account
    MANUAL = "manual"  # the business gave the money back itself and recorded it here


class PaymentConnection(IdMixin, TimestampMixin, TenantScoped, Base):
    """The workspace's payment settings (one row): Razorpay keys and/or a UPI address. The
    webhook token is the secret part of the address Razorpay posts to; the webhook secret signs
    what it posts (razorpay/signatures.py)."""

    __tablename__ = "payment_connections"

    razorpay_key_id: Mapped[str | None] = mapped_column(Text)
    razorpay_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    razorpay_webhook_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    razorpay_last_error: Mapped[str | None] = mapped_column(Text)
    webhook_token: Mapped[str] = mapped_column(Text)
    webhook_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upi_vpa: Mapped[str | None] = mapped_column(Text)
    upi_name: Mapped[str | None] = mapped_column(Text)
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("workspace_id"),
        UniqueConstraint("webhook_token"),
    )


class Order(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "orders"

    # 1, 2, 3... per workspace, shown as "#12".
    number: Mapped[int] = mapped_column(Integer)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, server_default=sql("'draft'"))
    source: Mapped[str] = mapped_column(Text, server_default=sql("'inbox'"))
    currency: Mapped[str] = mapped_column(Text)
    total_minor: Mapped[int] = mapped_column(BigInteger)
    # {name, phone, line1, line2, city, state, pincode, country}: what the customer gave.
    address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    payment_method: Mapped[str | None] = mapped_column(Text)
    # Razorpay's payment link id and address; Razorpay's payment id (or a member's note for UPI).
    payment_link_id: Mapped[str | None] = mapped_column(Text)
    payment_link_url: Mapped[str | None] = mapped_column(Text)
    payment_reference: Mapped[str | None] = mapped_column(Text)
    link_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Who marked a UPI order paid (null for a Razorpay payment, which Razorpay confirmed).
    paid_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # C-125: the sum of ``order_payments``, the sum of processed ``order_refunds``, whether the
    # Razorpay link takes part payments, and when and how the order was shipped.
    amount_paid_minor: Mapped[int] = mapped_column(BigInteger, server_default=sql("0"))
    amount_refunded_minor: Mapped[int] = mapped_column(BigInteger, server_default=sql("0"))
    accept_partial: Mapped[bool] = mapped_column(server_default=sql("false"))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilment_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("workspace_id", "number"),
        Index("ix_orders_listing", "workspace_id", sql("created_at DESC"), "id"),
        Index("ix_orders_contact_id", "contact_id"),
        Index("ix_orders_payment_link_id", "payment_link_id"),
        CheckConstraint(_in("status", OrderStatus), name="status"),
        CheckConstraint(_in("source", OrderSource), name="source"),
        CheckConstraint(
            f"payment_method IS NULL OR {_in('payment_method', PaymentMethod)}",
            name="payment_method",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("total_minor >= 0", name="total_minor"),
        CheckConstraint("amount_paid_minor >= 0", name="amount_paid_minor"),
        CheckConstraint(
            "amount_refunded_minor >= 0 AND amount_refunded_minor <= amount_paid_minor",
            name="amount_refunded_minor",
        ),
    )


class OrderItem(IdMixin, TimestampMixin, TenantScoped, Base):
    """One line, as it was priced when the order was made. The product and variant are kept as
    links only while they exist."""

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text)
    variant_title: Mapped[str | None] = mapped_column(Text)
    sku: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger)
    line_total_minor: Mapped[int] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))

    __table_args__ = (
        Index("ix_order_items_order_id_position", "order_id", "position"),
        CheckConstraint("quantity BETWEEN 1 AND 999", name="quantity"),
        CheckConstraint("unit_price_minor >= 0", name="unit_price_minor"),
        CheckConstraint("line_total_minor >= 0", name="line_total_minor"),
    )


class OrderPayment(IdMixin, TimestampMixin, TenantScoped, Base):
    """One payment toward an order: a Razorpay payment (its id keeps a re-delivered webhook from
    counting twice) or a member's record of a UPI or other payment."""

    __tablename__ = "order_payments"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    razorpay_payment_id: Mapped[str | None] = mapped_column(Text)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("order_id", "razorpay_payment_id"),
        Index("ix_order_payments_order_id", "order_id"),
        Index("ix_order_payments_razorpay_payment_id", "razorpay_payment_id"),
        CheckConstraint("amount_minor > 0", name="amount_minor"),
        CheckConstraint(_in("method", PaymentMethod), name="method"),
    )


class OrderRefund(IdMixin, TimestampMixin, TenantScoped, Base):
    """One refund of (part of) a payment. A Razorpay refund is ``pending`` until Razorpay says
    it is processed (or failed); a refund the business made itself is recorded as processed.
    Only processed refunds count in ``orders.amount_refunded_minor``."""

    __tablename__ = "order_refunds"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_payments.id", ondelete="SET NULL")
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    razorpay_refund_id: Mapped[str | None] = mapped_column(Text)
    failure: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("order_id", "razorpay_refund_id"),
        Index("ix_order_refunds_order_id", "order_id"),
        Index("ix_order_refunds_razorpay_refund_id", "razorpay_refund_id"),
        CheckConstraint("amount_minor > 0", name="amount_minor"),
        CheckConstraint(_in("method", RefundMethod), name="method"),
        CheckConstraint(_in("status", RefundStatus), name="status"),
    )
