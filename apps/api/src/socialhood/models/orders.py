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
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"  # the payment link ran out before it was paid


class PaymentMethod(StrEnum):
    RAZORPAY = "razorpay"
    UPI = "upi"


class OrderSource(StrEnum):
    INBOX = "inbox"  # a member made it from a conversation
    WHATSAPP = "whatsapp"  # the customer's cart (GR-33)


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
