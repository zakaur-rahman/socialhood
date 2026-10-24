"""The product catalogue (GR-31): products with variants, and the workspace's Shopify store.

Money is an integer in the currency's minor units (paise, cents) with its ISO 4217 code on the
product, so nothing is ever a float. A product with variants (size, colour…) answers per variant:
each variant has its own price, stock and optional SKU, and the product's own price and stock are
then only the form's defaults. ``stock`` null means "not recorded", which is different from 0
(out of stock): the AI says it doesn't know the first and never makes up a number.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class ProductSource(StrEnum):
    MANUAL = "manual"  # added by hand
    CSV = "csv"  # created by a CSV import
    SHOPIFY = "shopify"  # created by the Shopify sync or a Shopify webhook


class ShopifyStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_RECONNECT = "needs_reconnect"  # Shopify no longer accepts the saved access


class Product(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    sku: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, server_default=sql("'INR'"))
    # The price and stock of a product without variants (and the form's defaults otherwise).
    price_minor: Mapped[int | None] = mapped_column(BigInteger)
    stock: Mapped[int | None] = mapped_column(Integer)
    # The product page. https only (checked in the service); null when it has none.
    url: Mapped[str | None] = mapped_column(Text)
    # An uploaded picture (sent in chats) and/or the address of one elsewhere (Shopify, CSV).
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    image_url: Mapped[str | None] = mapped_column(Text)
    # Off: kept in the list, never offered to customers or in flows.
    active: Mapped[bool] = mapped_column(Boolean, server_default=sql("true"))
    source: Mapped[str] = mapped_column(Text, server_default=sql("'manual'"))
    # The Shopify product id, so a webhook or the next sync finds it again.
    external_id: Mapped[str | None] = mapped_column(Text)
    # The words the AI search matches on, lower case (name, description, SKU): set by the service.
    search_text: Mapped[str] = mapped_column(Text, server_default=sql("''"))

    __table_args__ = (
        UniqueConstraint("workspace_id", "sku"),
        UniqueConstraint("workspace_id", "external_id"),
        Index("ix_products_listing", "workspace_id", sql("created_at DESC"), "id"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("price_minor IS NULL OR price_minor >= 0", name="price_minor"),
        CheckConstraint("stock IS NULL OR stock >= 0", name="stock"),
        CheckConstraint(_in("source", ProductSource), name="source"),
    )


class ProductVariant(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    # What the customer calls it: "M", "Blue / M". Unique within the product.
    title: Mapped[str] = mapped_column(Text)
    # {"Size": "M", "Colour": "Blue"}: at most three options, matched by the AI search.
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql("'{}'::jsonb"))
    sku: Mapped[str | None] = mapped_column(Text)
    price_minor: Mapped[int] = mapped_column(BigInteger)
    stock: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    external_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("product_id", "title"),
        UniqueConstraint("workspace_id", "sku"),
        Index("ix_product_variants_product_id_position", "product_id", "position"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="title_length"),
        CheckConstraint("price_minor >= 0", name="price_minor"),
        CheckConstraint("stock IS NULL OR stock >= 0", name="stock"),
        CheckConstraint("jsonb_typeof(options) = 'object'", name="options_object"),
    )


class ShopifyConnection(IdMixin, TimestampMixin, TenantScoped, Base):
    """A workspace's Shopify store (GR-31). One per workspace, and a store belongs to one
    workspace at a time. ``token_enc`` is Shopify's offline access token, encrypted like platform
    tokens (SEC-03); it never leaves the server."""

    __tablename__ = "shopify_connections"

    shop_domain: Mapped[str] = mapped_column(Text)  # "my-store.myshopify.com"
    shop_name: Mapped[str | None] = mapped_column(Text)
    # What product links use: the store's own domain when it has one, else shop_domain.
    storefront_domain: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(Text)  # the store's currency, ISO 4217
    token_enc: Mapped[bytes] = mapped_column(LargeBinary)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'"))
    status: Mapped[str] = mapped_column(Text, server_default=sql("'active'"))
    last_error: Mapped[str | None] = mapped_column(Text)
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The webhook topics Shopify confirmed, so a reconnect doesn't register them twice.
    webhook_topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'"))
    sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[str | None] = mapped_column(Text)
    products_synced: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    products_skipped: Mapped[int] = mapped_column(Integer, server_default=sql("0"))

    __table_args__ = (
        UniqueConstraint("workspace_id"),
        UniqueConstraint("shop_domain"),
        CheckConstraint(_in("status", ShopifyStatus), name="status"),
    )
