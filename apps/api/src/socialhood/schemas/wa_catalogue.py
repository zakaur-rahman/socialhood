"""The WhatsApp catalogue (GR-33): the connection to a Meta commerce catalogue, and product and
product-list messages sent in a conversation.

Limits follow Meta's documentation for these messages (a product list shows up to 30 products in
up to 10 sections; the body is up to 1,024 characters, the header and footer up to 60 and a
section title up to 24); the header and section-title limits are unverified (C-121).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

MAX_ITEMS = 30
MAX_SECTIONS = 10


class WaCatalogueConnect(RequestModel):
    social_account_id: uuid.UUID  # the WhatsApp number whose business account owns the catalogue
    # Meta's catalogue id (Commerce Manager, Catalogue, Settings): digits only.
    catalog_id: str = Field(min_length=5, max_length=30, pattern=r"^[0-9]+$")
    brand: str | None = Field(default=None, min_length=1, max_length=100)  # default: the workspace


class WaCatalogueProblem(ResponseModel):
    name: str
    message: str


class WaCatalogueStatus(ResponseModel):
    """C-215: Meta fetches the products from ``feed_url`` (a scheduled data feed in Commerce
    Manager). ``items_synced``: items Meta got in its last fetch; ``items_pending``: items added or
    changed since; ``items_error``: products that can't be in the feed (``problems`` says why)."""

    entitled: bool  # the plan includes commerce (PD-8)
    connected: bool
    social_account_id: uuid.UUID | None = None
    account_label: str | None = None
    catalog_id: str | None = None
    brand: str | None = None
    feed_url: str | None = None  # owners and admins only; null for other members
    feed_fetched_at: datetime | None = None  # Meta's last fetch of the feed
    last_error: str | None = None  # why the feed is stopped (the plan), if it is
    items_synced: int = 0
    items_pending: int = 0
    items_error: int = 0
    problems: list[WaCatalogueProblem] = Field(default_factory=list)  # the first few, with why


class ItemRef(RequestModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None  # required when the product has variants


class SectionIn(RequestModel):
    title: str = Field(min_length=1, max_length=24)
    items: list[ItemRef] = Field(min_length=1, max_length=MAX_ITEMS)


class ProductMessageSend(RequestModel):
    """``product``: one item (``item``). ``product_list``: ``sections`` of items (up to 30 in all,
    in up to 10 sections) under a ``header``, which Meta requires for a list."""

    kind: Literal["product", "product_list"]
    body: str = Field(min_length=1, max_length=1024)
    header: str | None = Field(default=None, max_length=60)
    footer: str | None = Field(default=None, max_length=60)
    item: ItemRef | None = None
    sections: list[SectionIn] = Field(default_factory=list, max_length=MAX_SECTIONS)
