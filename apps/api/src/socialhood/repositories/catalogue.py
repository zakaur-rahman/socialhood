"""Products, variants and the Shopify store (GR-31). Tenant-scoped like every repository: reads are
filtered by the session's workspace, inserts are stamped with it, and deletes go through
``scoped_delete``."""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.catalogue import Product, ProductSource, ProductVariant, ShopifyConnection
from socialhood.models.media import MediaAsset
from socialhood.repositories.base import scoped_delete


async def count_products(session: AsyncSession) -> int:
    """For the catalogue_products limit (counted live, §5.8)."""
    return int(await session.scalar(select(func.count()).select_from(Product)) or 0)


async def get(session: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await session.get(Product, product_id)


async def list_products(
    session: AsyncSession,
    *,
    q: str | None = None,
    active: bool | None = None,
    source: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    """Newest first. ``q`` matches the name, description, SKUs and variant words (search_text)."""
    where = []
    if q:
        for word in q.casefold().split()[:6]:
            where.append(Product.search_text.contains(word, autoescape=True))
    if active is not None:
        where.append(Product.active.is_(active))
    if source is not None:
        where.append(Product.source == source)
    total = int(await session.scalar(select(func.count()).select_from(Product).where(*where)) or 0)
    rows = await session.scalars(
        select(Product)
        .where(*where)
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), total


async def variants_of(
    session: AsyncSession, product_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, list[ProductVariant]]:
    """Each product's variants in their order (a product without any maps to nothing)."""
    if not product_ids:
        return {}
    rows = await session.scalars(
        select(ProductVariant)
        .where(ProductVariant.product_id.in_(list(product_ids)))
        .order_by(ProductVariant.position, ProductVariant.created_at, ProductVariant.id)
    )
    grouped: dict[uuid.UUID, list[ProductVariant]] = {}
    for variant in rows.all():
        grouped.setdefault(variant.product_id, []).append(variant)
    return grouped


async def get_variant(session: AsyncSession, variant_id: uuid.UUID) -> ProductVariant | None:
    return await session.get(ProductVariant, variant_id)


async def image_urls(
    session: AsyncSession, asset_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """The uploaded pictures' addresses."""
    if not asset_ids:
        return {}
    rows = await session.execute(
        select(MediaAsset.id, MediaAsset.secure_url).where(MediaAsset.id.in_(list(asset_ids)))
    )
    return {asset_id: url for asset_id, url in rows.all() if url}


async def by_sku(session: AsyncSession, skus: Collection[str]) -> dict[str, Product]:
    """Products by their own SKU, or the SKU of one of their variants (SKUs match exactly)."""
    if not skus:
        return {}
    wanted = list(skus)
    found: dict[str, Product] = {}
    own = await session.scalars(select(Product).where(Product.sku.in_(wanted)))
    for product in own.all():
        if product.sku:
            found[product.sku] = product
    pairs = await session.execute(
        select(ProductVariant.sku, Product)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(ProductVariant.sku.in_(wanted))
    )
    for sku, product in pairs.all():
        if sku:
            found.setdefault(sku, product)
    return found


async def by_names(session: AsyncSession, names: Collection[str]) -> dict[str, Product]:
    """Products by name, ignoring case (the first created wins when two share one)."""
    if not names:
        return {}
    lowered = [n.casefold() for n in names]
    rows = await session.scalars(
        select(Product)
        .where(func.lower(Product.name).in_(lowered))
        .order_by(Product.created_at, Product.id)
    )
    found: dict[str, Product] = {}
    for product in rows.all():
        found.setdefault(product.name.casefold(), product)
    return found


async def by_external_id(session: AsyncSession, external_id: str) -> Product | None:
    return await session.scalar(select(Product).where(Product.external_id == external_id))


async def external_ids(session: AsyncSession, source: str) -> dict[str, uuid.UUID]:
    rows = await session.execute(
        select(Product.external_id, Product.id).where(
            Product.source == source, Product.external_id.is_not(None)
        )
    )
    return {external: product_id for external, product_id in rows.all() if external}


async def candidates(session: AsyncSession, words: Sequence[str], *, limit: int) -> list[Product]:
    """Active products whose search text holds any of ``words`` (lower case), newest first. The
    AI's search narrows these in Python (services/catalogue/facts.py)."""
    if not words:
        return []
    rows = await session.scalars(
        select(Product)
        .where(
            Product.active.is_(True),
            or_(*(Product.search_text.contains(w, autoescape=True) for w in words)),
        )
        .order_by(Product.updated_at.desc(), Product.id)
        .limit(limit)
    )
    return list(rows.all())


async def products_by_ids(
    session: AsyncSession, product_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, Product]:
    if not product_ids:
        return {}
    rows = await session.scalars(select(Product).where(Product.id.in_(list(product_ids))))
    return {p.id: p for p in rows.all()}


async def delete_product(session: AsyncSession, product_id: uuid.UUID) -> None:
    await session.execute(scoped_delete(Product, id=product_id))


async def delete_variants(session: AsyncSession, variant_ids: Collection[uuid.UUID]) -> None:
    for variant_id in variant_ids:
        await session.execute(scoped_delete(ProductVariant, id=variant_id))


async def delete_products(session: AsyncSession, product_ids: Collection[uuid.UUID]) -> None:
    for product_id in product_ids:
        await session.execute(scoped_delete(Product, id=product_id))


async def delete_source(session: AsyncSession, source: ProductSource) -> int:
    """Every product a source made (a disconnected store's), with its variants."""
    ids = (await session.scalars(select(Product.id).where(Product.source == source))).all()
    await delete_products(session, ids)
    return len(ids)


# ---------------------------------------------------------------- the Shopify store


async def get_shopify(session: AsyncSession, *, lock: bool = False) -> ShopifyConnection | None:
    query = select(ShopifyConnection)
    if lock:
        query = query.with_for_update()
    return await session.scalar(query)
