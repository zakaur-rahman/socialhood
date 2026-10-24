"""Products as facts the AI retrieves (GR-31): "price of the blue kurta in M?" gets the price, the
stock and the link of that variant, as written in the catalogue.

The catalogue isn't chunked into the knowledge base: a price or a stock level must be exact and
current, so a question is matched to products by words (``find``) and the matches are handed to the
model as structured lines next to the KNOWLEDGE chunks:

    [p1] Cotton kurta | link: https://shop.example/kurta
      - Blue / M | SKU KUR-BL-M | price INR 799.00 | 12 in stock | matches the question
      - Blue / L | price INR 799.00 | out of stock

Rules the text keeps, whatever the model does with it:
- the price is exact (money.label), never rounded, and a variant has its own;
- stock is "N in stock", "out of stock", or "stock not recorded": the last is not "in stock"
  and not "out of stock", and the model is told so;
- a product with no price says "price not recorded";
- an inactive product is never offered.

The same lines are the texts a reply may quote from (the output filter lets a reply mention a link
that is in them), and the ids the model cites (``p1``) become the products' ids in the
suggestion's used ids, which is how Auto mode knows an answer came from the catalogue.

Matching is plain words, no embeddings: lower case, a trailing "s" dropped, stop words (price,
the, kitna…) removed. A product matches when a word of the question is in its name (or is its
SKU); the variants whose title, options or SKU hold the most question words are marked as the
match. The search is a pure function of the question and the rows (``rank``), so it is tested
without a database.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.catalogue import Product, ProductVariant
from socialhood.repositories import catalogue as repo
from socialhood.services.catalogue import money

MAX_PRODUCTS = 3  # offered to the model for one question
MAX_VARIANTS = 20  # variants listed per product
MAX_CANDIDATES = 60  # rows the database narrows to before ranking
MAX_WORDS = 8
NOT_RECORDED = "stock not recorded"
PRICE_NOT_RECORDED = "price not recorded"
HEADER = (
    "PRODUCTS (the business's catalogue; quote prices, stock and links exactly as listed, only for "
    "what is listed; 'stock not recorded' means you do not know the stock, so say so)"
)
NO_MATCH = ""

_WORD = re.compile(r"\w+", re.UNICODE)
_POSSESSIVE = re.compile("['" + chr(0x2019) + "]s\\b")  # "what's" is "what"
# Words that carry no product: English and the Hinglish a customer writes. Sizes and colours are
# not here: "m", "blue" and "xl" are what tell variants apart.
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "buy",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "get",
        "give",
        "go",
        "has",
        "have",
        "hello",
        "hi",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "link",
        "me",
        "much",
        "my",
        "need",
        "of",
        "on",
        "or",
        "order",
        "please",
        "price",
        "prices",
        "rate",
        "rates",
        "send",
        "share",
        "show",
        "size",
        "stock",
        "tell",
        "that",
        "the",
        "there",
        "this",
        "to",
        "u",
        "want",
        "what",
        "which",
        "with",
        "would",
        "you",
        "your",
        "available",
        "availability",
        "cost",
        "costs",
        "kitna",
        "kitne",
        "kitni",
        "ka",
        "ke",
        "ki",
        "ko",
        "hai",
        "hain",
        "mein",
        "mujhe",
        "aap",
        "bhai",
        "bhejo",
        "dikhao",
        "chahiye",
        "btao",
        "batao",
    }
)


def words(text: str) -> list[str]:
    """Lower-case words of ``text`` with a plural "s" dropped from words of four letters or more."""
    out = []
    for word in _WORD.findall(_POSSESSIVE.sub("", text.casefold())):
        out.append(word[:-1] if len(word) > 3 and word.endswith("s") and word[-2] != "s" else word)
    return out


def question_words(question: str) -> list[str]:
    seen: dict[str, None] = {}
    for word in words(question):
        if word not in STOP_WORDS:
            seen.setdefault(word)
    return list(seen)


@dataclass(frozen=True)
class VariantFact:
    id: uuid.UUID
    title: str
    sku: str | None
    price_minor: int
    stock: int | None
    matches: bool = False


@dataclass(frozen=True)
class ProductFact:
    id: uuid.UUID
    name: str
    description: str | None
    currency: str
    url: str | None
    price_minor: int | None
    stock: int | None
    sku: str | None = None
    variants: tuple[VariantFact, ...] = ()
    hidden_variants: int = 0  # variants beyond MAX_VARIANTS
    score: int = 0

    @property
    def matched_variants(self) -> list[VariantFact]:
        return [v for v in self.variants if v.matches]


def stock_text(stock: int | None) -> str:
    if stock is None:
        return NOT_RECORDED
    return "out of stock" if stock <= 0 else f"{stock} in stock"


def price_text(price_minor: int | None, currency: str) -> str:
    return (
        PRICE_NOT_RECORDED if price_minor is None else f"price {money.label(price_minor, currency)}"
    )


def lines(fact: ProductFact, key: str) -> str:
    """The product as the model reads it, ``key`` being its ``p1`` id."""
    head = [f"[{key}] {fact.name}"]
    if fact.sku and not fact.variants:
        head.append(f"SKU {fact.sku}")
    if not fact.variants:
        head += [price_text(fact.price_minor, fact.currency), stock_text(fact.stock)]
    if fact.url:
        head.append(f"link: {fact.url}")
    out = [" | ".join(head)]
    if fact.description:
        out.append(f"  about: {fact.description}")
    for variant in fact.variants:
        parts = [variant.title]
        if variant.sku:
            parts.append(f"SKU {variant.sku}")
        parts += [price_text(variant.price_minor, fact.currency), stock_text(variant.stock)]
        if variant.matches:
            parts.append("matches the question")
        out.append("  - " + " | ".join(parts))
    if fact.hidden_variants:
        out.append(f"  (and {fact.hidden_variants} more variants)")
    return "\n".join(out)


def block(facts: Sequence[ProductFact]) -> str:
    """The PRODUCTS section for the model; empty when nothing matched."""
    if not facts:
        return NO_MATCH
    entries = [lines(fact, f"p{index}") for index, fact in enumerate(facts, start=1)]
    return "\n".join([HEADER, *entries])


def keyed(facts: Sequence[ProductFact]) -> dict[str, ProductFact]:
    return {f"p{index}": fact for index, fact in enumerate(facts, start=1)}


def texts(facts: Sequence[ProductFact]) -> list[str]:
    """What a reply may quote from, for the output filter."""
    return [lines(fact, "p") for fact in facts]


# ---------------------------------------------------------------- ranking (pure)


def _fact(
    product: Product, variants: Sequence[ProductVariant], wanted: set[str], score: int
) -> ProductFact:
    scored = []
    for variant in variants:
        vwords = set(words(" ".join([variant.title, variant.sku or "", *_options(variant)])))
        scored.append((len(wanted & vwords), variant))
    best = max((s for s, _ in scored), default=0)
    ordered = sorted(scored, key=lambda pair: (pair[0] < best or best == 0, pair[1].position))
    shown = ordered[:MAX_VARIANTS]
    return ProductFact(
        id=product.id,
        name=product.name,
        description=_clip(product.description),
        currency=product.currency,
        url=product.url,
        price_minor=product.price_minor,
        stock=product.stock,
        sku=product.sku,
        variants=tuple(
            VariantFact(
                id=v.id,
                title=v.title,
                sku=v.sku,
                price_minor=v.price_minor,
                stock=v.stock,
                matches=best > 0 and s == best,
            )
            for s, v in shown
        ),
        hidden_variants=max(len(ordered) - MAX_VARIANTS, 0),
        score=score,
    )


def _options(variant: ProductVariant) -> list[str]:
    return [str(value) for value in (variant.options or {}).values()]


def _clip(text: str | None, limit: int = 200) -> str | None:
    if not text:
        return None
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "..."


def rank(
    question: str,
    candidates: Sequence[Product],
    variants: dict[uuid.UUID, list[ProductVariant]],
    *,
    limit: int = MAX_PRODUCTS,
) -> list[ProductFact]:
    """The products the question is about, best first. A product needs a question word in its
    name (or its SKU); its score is the name words matched (weighted) plus the best variant's."""
    wanted = set(question_words(question))
    if not wanted:
        return []
    ranked: list[tuple[int, str, Product]] = []
    for product in candidates:
        name_words = set(words(product.name))
        sku_words = set(words(product.sku or ""))
        variant_sku_words = {w for v in variants.get(product.id, []) for w in words(v.sku or "")}
        in_name = len(wanted & name_words)
        by_sku = bool(wanted & (sku_words | variant_sku_words))
        if not in_name and not by_sku:
            continue
        best = 0
        for variant in variants.get(product.id, []):
            vwords = set(words(" ".join([variant.title, *_options(variant)])))
            best = max(best, len(wanted & vwords))
        description_words = set(words(product.description or ""))
        score = 3 * in_name + (4 if by_sku else 0) + best + (1 if wanted & description_words else 0)
        ranked.append((score, product.name.casefold(), product))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        _fact(product, variants.get(product.id, []), wanted, score)
        for score, _, product in ranked[:limit]
    ]


def rank_one(product: Product, variants: Sequence[ProductVariant]) -> ProductFact:
    """One product as a fact, with none of its variants marked (no question to match)."""
    return _fact(product, variants, set(), 0)


# ---------------------------------------------------------------- the database


async def find(
    session: AsyncSession, question: str, *, limit: int = MAX_PRODUCTS
) -> list[ProductFact]:
    """Active products the question names. [] for a question with no product words."""
    wanted = [w for w in question_words(question) if len(w) >= 3][:MAX_WORDS]
    short = [w for w in question_words(question) if len(w) < 3]
    if not wanted and not short:
        return []
    # A product is a candidate when its search text holds a word (variant words included), and
    # short words ("m", "xl") only tell variants apart, so they never make a candidate alone.
    candidates = await repo.candidates(session, wanted, limit=MAX_CANDIDATES)
    if not candidates:
        return []
    variants = await repo.variants_of(session, [p.id for p in candidates])
    return rank(question, candidates, variants, limit=limit)


async def facts_for(session: AsyncSession, product_ids: Collection[uuid.UUID]) -> list[ProductFact]:
    """The given products as facts (no question: every variant listed, none marked)."""
    found = await repo.products_by_ids(session, product_ids)
    active = [p for p in found.values() if p.active]
    variants = await repo.variants_of(session, [p.id for p in active])
    return [_fact(p, variants.get(p.id, []), set(), 0) for p in active]
