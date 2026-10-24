"""The Shopify interface the catalogue uses (GR-31), and the shapes it speaks in.

Errors are ``ShopifyError`` with a ``kind`` that decides what a sync does:

- ``auth``: the access token no longer works (app uninstalled, scopes changed): the store needs
  reconnecting;
- ``not_found``: the store is gone;
- ``rate_limited`` and ``unavailable``: try again later;
- ``rejected``: Shopify refused what was sent and sending it again won't help.

A product is read into ``ShopifyProduct`` whatever its source (the GraphQL list, or a product
webhook's JSON), so the sync and the webhook handler share one mapping (services/catalogue/
shopify.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

ErrorKind = Literal["auth", "not_found", "rate_limited", "unavailable", "rejected"]
RETRYABLE: frozenset[ErrorKind] = frozenset({"rate_limited", "unavailable"})

# The topics we ask Shopify to send, and the mandatory privacy ones a listed app must answer.
PRODUCT_TOPICS = ("products/create", "products/update", "products/delete", "app/uninstalled")
PRIVACY_TOPICS = ("customers/data_request", "customers/redact", "shop/redact")

_SHOP = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}\.myshopify\.com$")
_ID = re.compile(r"(\d+)$")


class ShopifyError(Exception):
    def __init__(self, kind: ErrorKind, message: str = "", *, status: int | None = None) -> None:
        super().__init__(message or kind)
        self.kind: ErrorKind = kind
        self.status = status

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


def normalize_shop(text: str) -> str | None:
    """ "My-Store", "my-store.myshopify.com" or "https://my-store.myshopify.com/admin" as
    "my-store.myshopify.com"; None for anything that isn't a myshopify.com store. Only this
    domain is ever called: the person's text can't point a request elsewhere."""
    value = text.strip().casefold()
    value = re.sub(r"^https?://", "", value).split("/")[0].split("?")[0]
    if value and "." not in value:
        value = f"{value}.myshopify.com"
    return value if _SHOP.match(value) else None


def numeric_id(value: object) -> str | None:
    """ "gid://shopify/Product/123" and 123 as "123"."""
    found = _ID.search(str(value))
    return found.group(1) if found else None


@dataclass(frozen=True)
class Grant:
    access_token: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ShopInfo:
    name: str | None
    domain: str  # the myshopify.com domain
    storefront_domain: str | None  # the store's own domain, when it has one
    currency: str | None


@dataclass(frozen=True)
class ShopifyVariant:
    id: str
    title: str
    sku: str | None
    price: str | None  # a decimal in the store's currency, "799.00"
    inventory: int | None  # None: not tracked or not readable
    options: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ShopifyProduct:
    id: str
    title: str
    description: str | None  # plain text
    handle: str | None
    url: str | None  # the storefront page, when Shopify says it is published
    status: str  # "active", "draft" or "archived"
    image_url: str | None
    variants: tuple[ShopifyVariant, ...]


@dataclass(frozen=True)
class ProductPage:
    products: list[ShopifyProduct]
    next_cursor: str | None


class ShopifyClient(Protocol):
    def authorize_url(self, shop: str, state: str) -> str: ...

    async def exchange_code(self, shop: str, code: str) -> Grant: ...

    async def shop_info(self, shop: str, token: str) -> ShopInfo: ...

    async def list_products(self, shop: str, token: str, cursor: str | None) -> ProductPage: ...

    async def register_webhooks(
        self, shop: str, token: str, topics: tuple[str, ...], address: str
    ) -> list[str]:
        """Subscribe to ``topics``; returns the ones Shopify accepted (or already had)."""
        ...

    async def revoke(self, shop: str, token: str) -> None: ...
