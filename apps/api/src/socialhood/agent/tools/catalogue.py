"""The product catalogue tool (GR-31; agent-architecture.html §5): search_products, for "what's
the price of the blue kurta in M?" and "is the linen shirt in stock?". Owners and admins, like
Knowledge and the Products page (``min_role`` admin).

R1 (read): the prices, stock and links come from the catalogue exactly as stored
(services/catalogue/facts), in the product's currency. A stock level that was never recorded is
said as "not recorded", never as in stock or out of stock. Nothing is changed.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.tools.common import clip, limit_field, ref, tool
from socialhood.models.identity import Role
from socialhood.repositories import catalogue as repo
from socialhood.services.catalogue import facts, money

MAX_VARIANTS_SHOWN = 12


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchProductsInput(_Input):
    q: str = Field(
        min_length=1,
        max_length=300,
        description="The product the way a customer would name it, with a size or colour if they "
        "gave one, e.g. “blue kurta M”, “linen shirt”, or a SKU.",
    )
    limit: int = limit_field(default=5, maximum=facts.MAX_PRODUCTS)


class VariantLine(BaseModel):
    title: str
    sku: str | None = None
    price: str  # "INR 799.00"
    stock: str  # "12 in stock", "out of stock" or "stock not recorded"
    matches: bool = False  # named by the question


class ProductLine(BaseModel):
    id: uuid.UUID
    name: str
    price: str | None = None  # a product without variants; "price not recorded" when it has none
    stock: str | None = None
    link: str | None = None
    active: bool = True
    variants: list[VariantLine] = Field(default_factory=list)
    more_variants: int = 0


class SearchProductsResult(ToolResult):
    items: list[ProductLine]


def _line(fact: facts.ProductFact, *, active: bool = True) -> ProductLine:
    variants = [
        VariantLine(
            title=v.title,
            sku=v.sku,
            price=money.label(v.price_minor, fact.currency),
            stock=facts.stock_text(v.stock),
            matches=v.matches,
        )
        for v in fact.variants[:MAX_VARIANTS_SHOWN]
    ]
    return ProductLine(
        id=fact.id,
        name=fact.name,
        price=None if fact.variants else facts.price_text(fact.price_minor, fact.currency),
        stock=None if fact.variants else facts.stock_text(fact.stock),
        link=fact.url,
        active=active,
        variants=variants,
        more_variants=max(len(fact.variants) - len(variants), 0) + fact.hidden_variants,
    )


@tool(
    name="search_products",
    label="Looking in your catalogue",
    description=(
        "The business's products matching the words, with each variant's price, stock and link "
        "as stored (size, colour…). For questions like 'price of the blue kurta in M?' or 'is X "
        "in stock?'. Stock 'not recorded' means it is unknown."
    ),
    input_model=SearchProductsInput,
    result_model=SearchProductsResult,
    min_role=Role.ADMIN,
)
async def search_products(ctx: ToolContext, args: SearchProductsInput) -> SearchProductsResult:
    found = await facts.find(ctx.session, args.q, limit=args.limit)
    items = [_line(fact) for fact in found]
    caveats: list[str] = []
    if not items:
        # Nothing named by the words: fall back to a plain text search, hidden products included,
        # so "do I have a kurta?" still answers.
        rows, _ = await repo.list_products(
            ctx.session, q=args.q, active=None, source=None, limit=args.limit, offset=0
        )
        variants = await repo.variants_of(ctx.session, [p.id for p in rows])
        for product in rows:
            fact = facts.rank_one(product, variants.get(product.id, []))
            items.append(_line(fact, active=product.active))
        if not items:
            caveats.append("No product in the catalogue matches these words.")
    names = ", ".join(item.name for item in items[:3])
    return SearchProductsResult(
        summary=clip(
            f"Found {len(items)} products for “{clip(args.q, 40)}”"
            + (f": {names}" if names else ""),
            300,
        )
        or "Searched the catalogue",
        items=items,
        refs=[ref("product", item.id, item.name) for item in items],
        caveats=caveats,
    )
