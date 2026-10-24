"""GR-31: products as facts for the AI. The search is a pure function of the question and the rows
(`facts.rank`), the prompt text keeps its rules (exact price, stock recorded or not, the link), and
the drafting prompt carries the PRODUCTS section. "Price of the blue kurta in M?" gets the M
variant's price and the link."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from socialhood.ai import output_filter
from socialhood.models.catalogue import Product, ProductVariant
from socialhood.services.catalogue import facts, message
from socialhood.services.suggestions import drafting

NOW = datetime(2026, 10, 25, tzinfo=UTC)
WS = uuid.uuid4()


def product(
    name: str,
    *,
    price: int | None = None,
    stock: int | None = None,
    url: str | None = None,
    description: str | None = None,
    sku: str | None = None,
    active: bool = True,
) -> Product:
    return Product(
        id=uuid.uuid4(),
        workspace_id=WS,
        name=name,
        description=description,
        sku=sku,
        currency="INR",
        price_minor=price,
        stock=stock,
        url=url,
        active=active,
        source="manual",
        created_at=NOW,
        updated_at=NOW,
    )


def variant(
    parent: Product,
    title: str,
    price: int,
    stock: int | None,
    *,
    position: int,
    sku: str | None = None,
    **options: str,
) -> ProductVariant:
    return ProductVariant(
        id=uuid.uuid4(),
        workspace_id=WS,
        product_id=parent.id,
        title=title,
        options=options,
        sku=sku,
        price_minor=price,
        stock=stock,
        position=position,
    )


def shop() -> tuple[list[Product], dict[uuid.UUID, list[ProductVariant]]]:
    kurta = product("Cotton kurta", url="https://shop.test/kurta", description="Soft cotton.")
    scarf = product("Silk scarf", price=49900, stock=None, url="https://shop.test/scarf")
    jacket = product("Denim jacket", price=299900, stock=0)
    variants = {
        kurta.id: [
            variant(kurta, "Blue / S", 79900, 4, position=0, Colour="Blue", Size="S"),
            variant(kurta, "Blue / M", 79900, 12, position=1, Colour="Blue", Size="M"),
            variant(kurta, "Blue / L", 84900, 0, position=2, Colour="Blue", Size="L"),
            variant(kurta, "Red / M", 79900, None, position=3, Colour="Red", Size="M"),
        ]
    }
    return [kurta, scarf, jacket], variants


# ---------------------------------------------------------------- words


def test_words_drop_filler_and_plurals_but_keep_sizes_and_colours() -> None:
    assert facts.question_words("What's the price of the blue kurtas in M?") == [
        "blue",
        "kurta",
        "m",
    ]
    assert facts.question_words("kitna hai blue kurta M mein") == ["blue", "kurta", "m"]
    assert facts.question_words("price?") == []
    assert facts.words("Dress glass") == ["dress", "glass"]  # "ss" is not a plural


# ---------------------------------------------------------------- ranking


def test_the_blue_kurta_in_m_is_found_with_its_variant_marked() -> None:
    products, variants = shop()
    [found] = facts.rank("price of the blue kurta in M?", products, variants)
    assert found.name == "Cotton kurta"
    [matched] = found.matched_variants
    assert matched.title == "Blue / M"
    assert (matched.price_minor, matched.stock) == (79900, 12)
    assert found.url == "https://shop.test/kurta"
    assert found.variants[0].title == "Blue / M"  # the match is listed first


def test_without_a_size_every_blue_variant_is_marked() -> None:
    products, variants = shop()
    [found] = facts.rank("blue kurta price", products, variants)
    assert [v.title for v in found.matched_variants] == ["Blue / S", "Blue / M", "Blue / L"]


def test_a_question_with_no_product_word_finds_nothing() -> None:
    products, variants = shop()
    assert facts.rank("price?", products, variants) == []
    assert facts.rank("do you ship to Dubai", products, variants) == []
    assert facts.rank("blue", products, variants) == []  # a colour alone names no product


def test_a_sku_finds_its_product() -> None:
    products, variants = shop()
    variants[products[0].id][1].sku = "KUR-BL-M"
    [found] = facts.rank("do you have KUR-BL-M", products, variants)
    assert found.name == "Cotton kurta"


def test_the_best_name_match_comes_first_and_the_list_is_capped() -> None:
    rows = [product(f"Silk scarf {n}") for n in range(5)] + [product("Silk shirt")]
    found = facts.rank("silk scarf", rows, {})
    assert len(found) == facts.MAX_PRODUCTS
    assert all("scarf" in f.name.lower() for f in found)


# ---------------------------------------------------------------- the text the model reads


def test_the_prompt_text_states_price_stock_and_link_exactly() -> None:
    products, variants = shop()
    [kurta] = facts.rank("blue kurta M", products, variants)
    text = facts.block([kurta])
    assert text.startswith("PRODUCTS (")
    assert "[p1] Cotton kurta | link: https://shop.test/kurta" in text
    assert "  - Blue / M | price INR 799.00 | 12 in stock | matches the question" in text
    assert "  - Blue / L | price INR 849.00 | out of stock" in text
    assert "  - Red / M | price INR 799.00 | stock not recorded" in text


def test_a_simple_product_has_its_own_price_and_unknown_stock_is_not_in_stock() -> None:
    products, variants = shop()
    [scarf] = facts.rank("silk scarf", products, variants)
    assert (
        "[p1] Silk scarf | price INR 499.00 | stock not recorded | link: https://shop.test/scarf"
        in (facts.block([scarf]))
    )
    [jacket] = facts.rank("denim jacket", products, variants)
    assert "price INR 2999.00 | out of stock" in facts.block([jacket])


def test_a_missing_price_is_said_not_invented() -> None:
    [bare] = facts.rank("plain tote", [product("Plain tote")], {})
    assert facts.PRICE_NOT_RECORDED in facts.block([bare])


def test_no_match_gives_no_section() -> None:
    assert facts.block([]) == ""


def test_a_reply_may_quote_a_product_link_but_not_an_invented_one() -> None:
    products, variants = shop()
    [kurta] = facts.rank("blue kurta M", products, variants)
    allowed = facts.texts([kurta])
    assert output_filter.check("It is INR 799. https://shop.test/kurta", allowed) is None
    assert output_filter.check("Order at https://other.test/kurta", allowed) is not None


def test_the_drafting_prompt_carries_the_products_next_to_knowledge() -> None:
    products, variants = shop()
    offered = facts.rank("blue kurta M", products, variants)
    lines = [drafting.Line("customer", "price of the blue kurta in M?", target=True)]
    out = drafting.render_contents(lines, [], ["shipping to uae"], offered)
    assert "KNOWLEDGE\n(none)" in out
    assert "[p1] Cotton kurta" in out
    assert out.index("PRODUCTS (") < out.index("KNOWN GAPS")
    # With none found the prompt is what it always was.
    assert "PRODUCTS" not in drafting.render_contents(lines, [], [], [])


# ---------------------------------------------------------------- the flow step's message


def test_a_named_variant_is_sent_with_its_price_stock_and_link() -> None:
    products, variants = shop()
    kurta = products[0]
    body = message._one(kurta, variants[kurta.id][1])
    assert body == ["Cotton kurta - Blue / M", "INR 799.00", "In stock"]
    text = message._fit("Here's the one you asked about:", body, "https://shop.test/kurta")
    assert text == (
        "Here's the one you asked about:\n\nCotton kurta - Blue / M\nINR 799.00\nIn stock\n"
        "https://shop.test/kurta"
    )


def test_stock_is_said_only_when_recorded() -> None:
    assert message.stock_line(None) is None
    assert message.stock_line(0) == "Out of stock"
    assert message.stock_line(3) == "In stock"


def test_a_product_without_a_variant_lists_its_variants() -> None:
    products, variants = shop()
    kurta = products[0]
    lines = message._listed(kurta, variants[kurta.id])
    assert lines[0] == "Cotton kurta"
    assert "Blue / L: INR 849.00, out of stock" in lines
    assert "Red / M: INR 799.00" in lines  # unknown stock adds nothing


def test_the_message_is_cut_to_fit_instagram() -> None:
    many = [f"Variant {n}: INR {n}.00" for n in range(80)]
    text = message._fit("Look:", ["Big product", *many], "https://shop.test/p")
    assert len(text.encode()) <= message.MAX_BYTES
    assert text.startswith("Look:")
    assert text.endswith("https://shop.test/p")
