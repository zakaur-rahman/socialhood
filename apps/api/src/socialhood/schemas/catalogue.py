"""The product catalogue (GR-31): products with variants, CSV import and the Shopify store.

Prices go in as text ("799" or "799.50", checked against the product's currency) and come out as
integer minor units plus the same text, so the web formats them with Intl and the form fills in
the number the person typed. A variant is matched by its id on a change; a variant without an id
is new, and one left out of the list is removed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator

from socialhood.schemas.common import RequestModel, ResponseModel

MAX_VARIANTS = 100
MAX_OPTIONS = 3
CSV_MAX_CHARS = 900_000  # under the API's 1 MB body limit

ProductSourceName = Literal["manual", "csv", "shopify"]
ImportAction = Literal["create", "update", "error"]
ShopifyStatusName = Literal["active", "needs_reconnect"]

Price = Annotated[str, StringConstraints(max_length=24)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", max_length=3)]
OptionText = Annotated[str, StringConstraints(max_length=80)]


class VariantIn(RequestModel):
    id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=120)
    options: dict[OptionText, OptionText] = Field(default_factory=dict, max_length=MAX_OPTIONS)
    sku: str | None = Field(default=None, max_length=80)
    price: Price
    stock: int | None = Field(default=None, ge=0, le=10_000_000)

    @field_validator("options")
    @classmethod
    def _options(cls, value: dict[str, str]) -> dict[str, str]:
        for name, option in value.items():
            if not 1 <= len(name) <= 40 or not 1 <= len(option) <= 80:
                raise ValueError("Each option needs a name and a value of a few words.")
        return value


class ProductCreate(RequestModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sku: str | None = Field(default=None, max_length=80)
    currency: Currency | None = None  # the workspace's, else INR
    price: Price | None = None
    stock: int | None = Field(default=None, ge=0, le=10_000_000)
    url: str | None = Field(default=None, max_length=2000)
    image_asset_id: uuid.UUID | None = None
    image_url: str | None = Field(default=None, max_length=2000)
    active: bool = True
    variants: list[VariantIn] = Field(default_factory=list, max_length=MAX_VARIANTS)


class ProductPatch(RequestModel):
    """Only the fields sent change. ``variants`` replaces the whole list (see the module doc)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sku: str | None = Field(default=None, max_length=80)
    currency: Currency | None = None
    price: Price | None = None
    stock: int | None = Field(default=None, ge=0, le=10_000_000)
    url: str | None = Field(default=None, max_length=2000)
    image_asset_id: uuid.UUID | None = None
    image_url: str | None = Field(default=None, max_length=2000)
    active: bool | None = None
    variants: list[VariantIn] | None = Field(default=None, max_length=MAX_VARIANTS)


class VariantOut(ResponseModel):
    id: uuid.UUID
    title: str
    options: dict[str, str]
    sku: str | None = None
    price_minor: int
    price: str  # "799.00", for the form
    stock: int | None = None  # null: not recorded
    position: int


class ProductOut(ResponseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    sku: str | None = None
    currency: str
    price_minor: int | None = None
    price: str | None = None
    stock: int | None = None
    url: str | None = None
    image_asset_id: uuid.UUID | None = None
    image_url: str | None = None  # the uploaded picture's address, else the one given
    active: bool
    source: ProductSourceName
    variants: list[VariantOut]
    created_at: datetime
    updated_at: datetime


class CatalogueLimits(ResponseModel):
    entitled: bool  # the plan includes the catalogue (PD-8: Pro and Max)
    product_cap: int  # products the plan holds
    import_row_cap: int  # rows one CSV import may carry
    csv_max_chars: int
    default_currency: str


class ProductList(ResponseModel):
    items: list[ProductOut]
    total: int
    limits: CatalogueLimits


class CsvImport(RequestModel):
    csv: str = Field(min_length=1, max_length=CSV_MAX_CHARS)


class ImportRowOut(ResponseModel):
    line: int  # the CSV line, the header being 1
    action: ImportAction
    name: str
    variant: str | None = None
    errors: list[str] = Field(default_factory=list)


class ImportPreview(ResponseModel):
    rows: list[ImportRowOut]
    total_rows: int
    create: int
    update: int
    errors: int
    products: int  # distinct products the valid rows touch
    row_cap: int
    columns: list[str]  # the header row this import understands
    ignored_columns: list[str]  # columns in the file that it doesn't use


class ImportResult(ResponseModel):
    created: int
    updated: int
    skipped: int  # rows with errors, left out
    products: int


# ---------------------------------------------------------------- Shopify


class ShopifyConnectRequest(RequestModel):
    shop: str = Field(min_length=3, max_length=100)  # "my-store" or "my-store.myshopify.com"


class ShopifyConnectStart(ResponseModel):
    authorize_url: str


class ShopifyConnectComplete(RequestModel):
    """The nonce the OAuth callback put in the Products page's URL (?shopify=…)."""

    nonce: str = Field(min_length=8, max_length=128)


class ShopifyStatus(ResponseModel):
    available: bool  # the Shopify app is set up on this server
    entitled: bool  # the plan includes the catalogue
    connected: bool
    status: ShopifyStatusName | None = None
    shop_domain: str | None = None
    shop_name: str | None = None
    currency: str | None = None
    syncing: bool = False
    synced_at: datetime | None = None
    sync_error: str | None = None
    products_synced: int = 0
    products_skipped: int = 0
    last_error: str | None = None
