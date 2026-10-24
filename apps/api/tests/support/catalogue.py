"""Catalogue test support (GR-31): products and variants written through the same service the app
uses (services/catalogue/products.save), in the workspace's scope, committed, returned as ids."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.catalogue import ProductSource
from socialhood.repositories import catalogue as repo
from socialhood.services.catalogue.products import ProductData, VariantData, save

KURTA_URL = "https://maple.example/kurta"


@dataclass
class Made:
    id: uuid.UUID
    variants: dict[str, uuid.UUID] = field(default_factory=dict)  # title -> id


def kurta_data() -> ProductData:
    """The cotton kurta of the done-when: blue and red, sizes S, M and L."""
    return ProductData(
        name="Cotton kurta",
        description="Soft cotton, straight cut.",
        url=KURTA_URL,
        variants=[
            VariantData("Blue / S", 79900, {"Colour": "Blue", "Size": "S"}, "KUR-BL-S", 4),
            VariantData("Blue / M", 79900, {"Colour": "Blue", "Size": "M"}, "KUR-BL-M", 12),
            VariantData("Blue / L", 84900, {"Colour": "Blue", "Size": "L"}, "KUR-BL-L", 0),
            VariantData("Red / M", 79900, {"Colour": "Red", "Size": "M"}, "KUR-RD-M", None),
        ],
    )


async def make_product(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    data: ProductData | None = None,
    source: ProductSource = ProductSource.MANUAL,
    **values: Any,
) -> Made:
    """A product (the cotton kurta unless ``data`` is given; ``values`` change its fields)."""
    data = data or kurta_data()
    for name, value in values.items():
        setattr(data, name, value)
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            product = await save(session, data, source=source)
            await session.commit()
            variants = await repo.variants_of(session, [product.id])
            return Made(product.id, {v.title: v.id for v in variants.get(product.id, [])})
