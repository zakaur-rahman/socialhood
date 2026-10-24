"""Products and their variants (GR-31): the rules every way of adding them shares.

By hand (the routes in api/v1/catalogue.py), by CSV (csv_import.py) and from Shopify
(services/catalogue/shopify.py) all end in ``save``, so a product looks the same however it got
here:

- **Money** is integer minor units with an ISO 4217 code on the product (money.py). A product
  with variants is priced per variant; its own price and stock are then only defaults.
- **Stock** null means "not recorded", which is not the same as 0 (out of stock). Nothing here,
  and nothing the AI is told, turns one into the other.
- **Links** are https. A picture is an uploaded asset (what a flow sends in chat) and/or an
  address elsewhere (what Shopify and CSV give).
- **Search text.** ``products.search_text`` holds the lower-case words the list and the AI search
  match on (name, description, SKUs, variant titles and options); ``refresh_search_text`` keeps
  it right on every change.
- **Plan.** Writing needs the catalogue on the plan (PD-8: ``commerce``) and room under
  ``catalogue_products``. Reading what exists is never refused. The routes resolve the rows a
  request names first, so another workspace's id is a 404 on every plan.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import check_capacity, check_entitlement
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.catalogue import Product, ProductSource, ProductVariant
from socialhood.models.media import MediaAsset
from socialhood.repositories import catalogue as repo
from socialhood.schemas.catalogue import (
    CSV_MAX_CHARS,
    CatalogueLimits,
    ProductCreate,
    ProductList,
    ProductOut,
    ProductPatch,
    VariantIn,
    VariantOut,
)
from socialhood.services.catalogue import money

KEY = "commerce"
MAX_URL = 2000
SEARCH_WORDS = 6

COPY = {
    "url": "Enter a link that starts with https://.",
    "image_url": "Enter a picture address that starts with https://.",
    "currency": "Use a three-letter currency code, like INR or USD.",
    "variant_title_twice": "Two variants have the same name. Give each its own.",
    "variant_sku_twice": "Two variants have the same SKU. Give each its own.",
    "sku_in_use": "Another product already uses this SKU.",
    "price_needed": "Add a price, or add variants that each have one.",
    "image_asset": "That picture isn't in your library.",
}


@dataclass
class VariantData:
    title: str
    price_minor: int
    options: dict[str, str] = field(default_factory=dict)
    sku: str | None = None
    stock: int | None = None
    external_id: str | None = None
    id: uuid.UUID | None = None  # an existing variant to keep (a change from the form)


@dataclass
class ProductData:
    name: str
    currency: str = money.DEFAULT_CURRENCY
    description: str | None = None
    sku: str | None = None
    price_minor: int | None = None
    stock: int | None = None
    url: str | None = None
    image_url: str | None = None
    image_asset_id: uuid.UUID | None = None
    active: bool = True
    external_id: str | None = None
    variants: list[VariantData] = field(default_factory=list)


def invalid(path: str, message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError(path, message)])


# ---------------------------------------------------------------- small checks


def clean_text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def https_url(value: str | None, path: str) -> str | None:
    """A trimmed https address, None for blank; 422 on ``path`` for anything else."""
    value = clean_text(value)
    if value is None:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or len(value) > MAX_URL:
        raise invalid(path, COPY["url"] if path == "url" else COPY["image_url"])
    return value


def quiet_https(value: str | None) -> str | None:
    """The same for data from elsewhere: an address that isn't https is dropped, not an error."""
    try:
        return https_url(value, "url")
    except ApiError:
        return None


def currency_code(value: str | None, default: str) -> str:
    code = (value or default).strip().upper()
    if not money.valid_currency(code):
        raise invalid("currency", COPY["currency"])
    return code


def parse_price(value: str | None, currency: str, path: str) -> int | None:
    value = clean_text(value)
    if value is None:
        return None
    try:
        return money.parse(value, currency)
    except ValueError as error:
        raise invalid(path, str(error)) from error


def refresh_search_text(product: Product, variants: Sequence[ProductVariant]) -> None:
    parts = [product.name, product.description or "", product.sku or ""]
    for variant in variants:
        parts += [variant.title, variant.sku or "", *map(str, (variant.options or {}).values())]
    product.search_text = " ".join(p for p in parts if p).casefold()[:6000]


def in_stock(stock: int | None) -> bool | None:
    """True/False when stock is recorded, None when it isn't."""
    return None if stock is None else stock > 0


# ---------------------------------------------------------------- the plan


async def limits(session: AsyncSession) -> CatalogueLimits:
    plan = await current_plan(session)
    return CatalogueLimits(
        entitled=bool(entitlement(plan, KEY)),
        product_cap=int(entitlement(plan, "catalogue_products")),
        import_row_cap=int(entitlement(plan, "catalogue_import_rows")),
        csv_max_chars=CSV_MAX_CHARS,
        default_currency=await default_currency(session),
    )


async def default_currency(session: AsyncSession) -> str:
    """The connected Shopify store's currency, else the newest product's, else INR."""
    store = await repo.get_shopify(session)
    if store is not None and store.currency:
        return store.currency
    newest = await session.scalar(
        select(Product.currency).order_by(Product.created_at.desc(), Product.id.desc()).limit(1)
    )
    return newest or money.DEFAULT_CURRENCY


# ---------------------------------------------------------------- reading


def variant_out(variant: ProductVariant, currency: str) -> VariantOut:
    return VariantOut(
        id=variant.id,
        title=variant.title,
        options={str(k): str(v) for k, v in (variant.options or {}).items()},
        sku=variant.sku,
        price_minor=variant.price_minor,
        price=money.plain(variant.price_minor, currency),
        stock=variant.stock,
        position=variant.position,
    )


async def outs(session: AsyncSession, products: Sequence[Product]) -> list[ProductOut]:
    ids = [p.id for p in products]
    variants = await repo.variants_of(session, ids)
    assets = await repo.image_urls(
        session, [p.image_asset_id for p in products if p.image_asset_id]
    )
    return [
        ProductOut(
            id=p.id,
            name=p.name,
            description=p.description,
            sku=p.sku,
            currency=p.currency,
            price_minor=p.price_minor,
            price=money.plain(p.price_minor, p.currency) if p.price_minor is not None else None,
            stock=p.stock,
            url=p.url,
            image_asset_id=p.image_asset_id,
            image_url=(assets.get(p.image_asset_id) if p.image_asset_id else None) or p.image_url,
            active=p.active,
            source=p.source,
            variants=[variant_out(v, p.currency) for v in variants.get(p.id, [])],
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in products
    ]


async def view(session: AsyncSession, product: Product) -> ProductOut:
    return (await outs(session, [product]))[0]


async def list_products(
    session: AsyncSession,
    *,
    q: str | None,
    active: bool | None,
    source: str | None,
    limit: int,
    offset: int,
) -> ProductList:
    rows, total = await repo.list_products(
        session, q=q, active=active, source=source, limit=limit, offset=offset
    )
    return ProductList(items=await outs(session, rows), total=total, limits=await limits(session))


async def get(session: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await repo.get(session, product_id)
    if product is None:
        raise ApiError("not_found")
    return product


# ---------------------------------------------------------------- writing


async def check_asset(session: AsyncSession, asset_id: uuid.UUID | None) -> None:
    """404 for a picture that isn't this workspace's (the session filters by workspace)."""
    if asset_id is not None and await session.get(MediaAsset, asset_id) is None:
        raise ApiError("not_found")


async def sku_conflicts(
    session: AsyncSession, skus: Sequence[str], *, product_id: uuid.UUID | None
) -> set[str]:
    """SKUs among ``skus`` that belong to another product or one of its variants."""
    if not skus:
        return set()
    taken = await repo.by_sku(session, skus)
    return {sku for sku, owner in taken.items() if owner.id != product_id}


def variants_from(body: Sequence[VariantIn], currency: str) -> list[VariantData]:
    out: list[VariantData] = []
    titles: set[str] = set()
    skus: set[str] = set()
    for index, item in enumerate(body):
        base = f"variants.{index}"
        title = item.title.strip()
        if not title:
            raise invalid(f"{base}.title", "Name the variant, like M or Blue / M.")
        if title.casefold() in titles:
            raise invalid(f"{base}.title", COPY["variant_title_twice"])
        titles.add(title.casefold())
        sku = clean_text(item.sku)
        if sku:
            if sku in skus:
                raise invalid(f"{base}.sku", COPY["variant_sku_twice"])
            skus.add(sku)
        price = parse_price(item.price, currency, f"{base}.price")
        if price is None:
            raise invalid(f"{base}.price", "Enter a price.")
        out.append(
            VariantData(
                title=title,
                price_minor=price,
                options={k.strip(): v.strip() for k, v in item.options.items()},
                sku=sku,
                stock=item.stock,
                id=item.id,
            )
        )
    return out


async def sync_variants(
    session: AsyncSession, product: Product, wanted: Sequence[VariantData]
) -> list[ProductVariant]:
    """Make the product's variants ``wanted``: a variant is kept by id, then Shopify id, then
    title; the rest are new, and the ones left over are removed. Returns them in order."""
    existing = list((await repo.variants_of(session, [product.id])).get(product.id, []))
    by_id = {v.id: v for v in existing}
    by_external = {v.external_id: v for v in existing if v.external_id}
    by_title = {v.title.casefold(): v for v in existing}
    kept: set[uuid.UUID] = set()
    matched: list[tuple[VariantData, ProductVariant | None]] = []
    for data in wanted:
        row = by_id.get(data.id) if data.id else None
        if row is None and data.external_id:
            row = by_external.get(data.external_id)
        if row is None:
            row = by_title.get(data.title.casefold())
        if row is not None and row.id in kept:
            row = None
        if row is not None:
            kept.add(row.id)
        matched.append((data, row))
    await repo.delete_variants(session, [v.id for v in existing if v.id not in kept])
    for gone in existing:
        if gone.id not in kept:
            session.expunge(gone)
    result: list[ProductVariant] = []
    for position, (data, row) in enumerate(matched):
        if row is None:
            row = ProductVariant(product_id=product.id, workspace_id=product.workspace_id)
            session.add(row)
        row.title = data.title
        row.options = dict(data.options)
        row.sku = data.sku
        row.price_minor = data.price_minor
        row.stock = data.stock
        row.position = position
        row.external_id = data.external_id or row.external_id
        result.append(row)
    await session.flush()
    return result


async def save(
    session: AsyncSession,
    data: ProductData,
    *,
    source: ProductSource,
    product: Product | None = None,
) -> Product:
    """Create the product, or make the existing one ``data`` (variants included). The caller has
    checked the plan and that ``data`` is valid; the database's unique SKU is the last word."""
    creating = product is None
    if product is None:
        product = Product(source=source)
        session.add(product)
    product.name = data.name
    product.currency = data.currency
    product.description = data.description
    product.sku = data.sku
    product.price_minor = data.price_minor
    product.stock = data.stock
    product.url = data.url
    product.image_url = data.image_url
    product.image_asset_id = data.image_asset_id
    product.active = data.active
    if data.external_id:
        product.external_id = data.external_id
    await session.flush()
    variants = await sync_variants(session, product, data.variants)
    refresh_search_text(product, variants)
    await session.flush()
    if creating:
        await session.refresh(product)
    return product


def data_of(product: Product, variants: Sequence[ProductVariant]) -> ProductData:
    return ProductData(
        name=product.name,
        currency=product.currency,
        description=product.description,
        sku=product.sku,
        price_minor=product.price_minor,
        stock=product.stock,
        url=product.url,
        image_url=product.image_url,
        image_asset_id=product.image_asset_id,
        active=product.active,
        external_id=product.external_id,
        variants=[
            VariantData(
                title=v.title,
                price_minor=v.price_minor,
                options={str(k): str(x) for k, x in (v.options or {}).items()},
                sku=v.sku,
                stock=v.stock,
                external_id=v.external_id,
                id=v.id,
            )
            for v in variants
        ],
    )


async def create(session: AsyncSession, body: ProductCreate) -> Product:
    await check_asset(session, body.image_asset_id)
    await check_entitlement(session, KEY)
    await check_capacity(session, "catalogue_products")
    currency = currency_code(body.currency, await default_currency(session))
    variants = variants_from(body.variants, currency)
    price = parse_price(body.price, currency, "price")
    if price is None and not variants:
        raise invalid("price", COPY["price_needed"])
    sku = clean_text(body.sku)
    await _check_skus(session, [sku, *(v.sku for v in variants)], product_id=None, paths=body)
    data = ProductData(
        name=body.name.strip(),
        currency=currency,
        description=clean_text(body.description),
        sku=sku,
        price_minor=price,
        stock=body.stock,
        url=https_url(body.url, "url"),
        image_url=https_url(body.image_url, "image_url"),
        image_asset_id=body.image_asset_id,
        active=body.active,
        variants=variants,
    )
    return await save(session, data, source=ProductSource.MANUAL)


async def update(session: AsyncSession, product_id: uuid.UUID, body: ProductPatch) -> Product:
    product = await get(session, product_id)
    await check_asset(session, body.image_asset_id)
    await check_entitlement(session, KEY)
    current = list((await repo.variants_of(session, [product.id])).get(product.id, []))
    data = data_of(product, current)
    sent = body.model_fields_set
    if "currency" in sent and body.currency:
        data.currency = currency_code(body.currency, product.currency)
    if body.name is not None:
        data.name = body.name.strip()
    if "description" in sent:
        data.description = clean_text(body.description)
    if "sku" in sent:
        data.sku = clean_text(body.sku)
    if "price" in sent:
        data.price_minor = parse_price(body.price, data.currency, "price")
    elif "currency" in sent and data.price_minor is not None:
        data.price_minor = None  # a price in the old currency means nothing in the new one
    if "stock" in sent:
        data.stock = body.stock
    if "url" in sent:
        data.url = https_url(body.url, "url")
    if "image_url" in sent:
        data.image_url = https_url(body.image_url, "image_url")
    if "image_asset_id" in sent:
        data.image_asset_id = body.image_asset_id
    if body.active is not None:
        data.active = body.active
    if body.variants is not None:
        data.variants = variants_from(body.variants, data.currency)
    elif data.currency != product.currency and current:
        raise invalid("currency", "Send the variants' prices again when the currency changes.")
    if data.price_minor is None and not data.variants:
        raise invalid("price", COPY["price_needed"])
    await _check_skus(
        session, [data.sku, *(v.sku for v in data.variants)], product_id=product.id, paths=body
    )
    return await save(session, data, source=ProductSource(product.source), product=product)


async def _check_skus(
    session: AsyncSession,
    skus: Sequence[str | None],
    *,
    product_id: uuid.UUID | None,
    paths: ProductCreate | ProductPatch,
) -> None:
    named = [s for s in skus if s]
    if len(named) != len(set(named)):
        raise invalid("sku", COPY["variant_sku_twice"])
    clash = await sku_conflicts(session, named, product_id=product_id)
    if not clash:
        return
    if skus and skus[0] in clash:
        raise invalid("sku", COPY["sku_in_use"])
    variants = paths.variants or []
    for index, item in enumerate(variants):
        if clean_text(item.sku) in clash:
            raise invalid(f"variants.{index}.sku", COPY["sku_in_use"])
    raise invalid("sku", COPY["sku_in_use"])


async def delete(session: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await get(session, product_id)
    await check_entitlement(session, KEY)
    await repo.delete_product(session, product.id)
    return product
