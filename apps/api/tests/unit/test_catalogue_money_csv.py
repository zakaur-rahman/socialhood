"""GR-31: prices as minor units, and the CSV import's reading (header row, groups, per-line
problems, currency and price settling). The database half (matching, saving) is in
tests/integration/test_catalogue_import.py."""

from __future__ import annotations

import pytest

from socialhood.errors import ApiError
from socialhood.services.catalogue import csv_import, money

HEADER = "name,description,sku,variant,option1_name,option1_value,price,currency,stock,url,active"


def read(*lines: str, header: str = HEADER) -> csv_import.Parsed:
    return csv_import.parse("\n".join([header, *lines]) + "\n")


# ---------------------------------------------------------------- money


@pytest.mark.parametrize(
    ("text", "currency", "minor"),
    [
        ("799", "INR", 79900),
        ("799.5", "INR", 79950),
        ("1,299.00", "INR", 129900),
        ("0", "INR", 0),
        ("1500", "JPY", 1500),
        ("1.250", "KWD", 1250),
        (" 12.34 ", "USD", 1234),
    ],
)
def test_prices_parse_to_minor_units(text: str, currency: str, minor: int) -> None:
    assert money.parse(text, currency) == minor


@pytest.mark.parametrize(
    ("text", "currency"),
    [("", "INR"), ("abc", "INR"), ("-5", "INR"), ("12.345", "INR"), ("1.5", "JPY"), ("1e3", "INR")],
)
def test_bad_prices_are_refused_with_a_reason(text: str, currency: str) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        money.parse(text, currency)


def test_prices_are_shown_without_floats() -> None:
    assert money.plain(79900, "INR") == "799.00"
    assert money.plain(1500, "JPY") == "1500"
    assert money.plain(1250, "KWD") == "1.250"
    assert money.label(79950, "INR") == "INR 799.50"
    assert money.from_decimal("799.00", "INR") == 79900
    assert money.from_decimal("12.5", "USD") == 1250
    assert money.from_decimal("nope", "INR") is None
    assert money.from_decimal("-1", "INR") is None


# ---------------------------------------------------------------- reading the file


def test_the_header_needs_name_and_price() -> None:
    with pytest.raises(ApiError) as missing:
        csv_import.parse("name,sku\nShirt,S1\n")
    assert "price" in missing.value.errors[0].message
    with pytest.raises(ApiError):
        csv_import.parse("")
    with pytest.raises(ApiError) as empty:
        csv_import.parse(HEADER + "\n")
    assert empty.value.errors[0].message == csv_import.COPY["empty"]


def test_unknown_columns_are_listed_and_ignored() -> None:
    parsed = csv_import.parse("Name,Price,Colour\nShirt,499,Blue\n")
    assert parsed.ignored == ["colour"]
    assert parsed.columns == ["name", "price"]
    assert parsed.rows[0].name == "Shirt"


def test_a_semicolon_file_and_a_byte_order_mark_are_read() -> None:
    parsed = csv_import.parse(csv_import.BOM + "name;price\nShirt;499\n")
    assert [(r.name, r.price_text) for r in parsed.rows] == [("Shirt", "499")]


def test_each_line_carries_its_own_problems() -> None:
    parsed = read(
        "Shirt,,S1,,,,499,INR,5,https://shop.test/shirt,yes",
        ",,,,,,499,,,,",  # no name
        "Scarf,,,,,,,,,,",  # no price
        "Hat,,,,,,100,RUPEES,,,",  # bad currency
        "Cap,,,,,,100,INR,lots,,",  # bad stock
        "Belt,,,,,,100,INR,,http://insecure.test,",  # not https
        "Tie,,,,,,100,INR,,,maybe",  # bad active
        "Bag,,,,size,,100,INR,,,",  # half an option
    )
    errors = {row.name or "(blank)": row.errors for row in parsed.rows}
    assert errors["Shirt"] == []
    assert errors["(blank)"] == [csv_import.COPY["name"]]
    assert errors["Scarf"] == [csv_import.COPY["price"]]
    assert csv_import.products.COPY["currency"] in errors["Hat"]
    assert errors["Cap"] == [csv_import.COPY["stock"]]
    assert errors["Belt"]
    assert "https://" in errors["Belt"][0]
    assert errors["Tie"] == [csv_import.COPY["active"]]
    assert errors["Bag"] == [csv_import.COPY["option_half"]]
    shirt = parsed.rows[0]
    assert (shirt.sku, shirt.stock, shirt.active) == ("S1", 5, True)


def test_a_variant_without_a_name_is_called_by_its_options() -> None:
    parsed = read("Kurta,,K1,,Size,M,799,,,,")
    row = parsed.rows[0]
    assert (row.variant, row.options) == ("M", {"Size": "M"})


def test_lines_with_one_name_are_one_product() -> None:
    parsed = read(
        "Kurta,,K-S,S,Size,S,799,,,,",
        "kurta,,K-M,M,Size,M,799,,,,",
        "Scarf,,,,,,499,,,,",
    )
    groups = csv_import._group(parsed.rows)
    assert [(g.key, len(g.rows)) for g in groups] == [("kurta", 2), ("scarf", 1)]


def test_a_product_cannot_mix_plain_and_variant_lines_or_repeat_one() -> None:
    parsed = read(
        "Kurta,,,S,,,799,,,,",
        "Kurta,,,,,,799,,,,",  # no variant, but the product has some
        "Kurta,,,S,,,799,,,,",  # the same variant twice
        "Scarf,,,,,,499,,,,",
        "Scarf,,,,,,599,,,,",  # a second plain line
    )
    for group in csv_import._group(parsed.rows):
        csv_import._check_group_shape(group)
    kurta, scarf = parsed.rows[:3], parsed.rows[3:]
    assert kurta[0].errors == []
    assert kurta[1].errors == [csv_import.COPY["no_variant"]]
    assert kurta[2].errors == [csv_import.COPY["variant_twice"]]
    assert scarf[0].errors == []
    assert scarf[1].errors == [csv_import.COPY["plain_twice"]]


def test_a_sku_may_appear_once_in_a_file() -> None:
    parsed = read("A,,S1,,,,10,,,,", "B,,S1,,,,10,,,,")
    csv_import._check_file_skus(parsed.rows)
    assert parsed.rows[0].errors == []
    assert parsed.rows[1].errors == [csv_import.COPY["sku_twice"]]


def test_prices_are_read_in_the_products_currency() -> None:
    parsed = read(
        "Ring,,,,,,1500,JPY,,,",  # a yen price has no decimals
        "Watch,,,,,,10.5,,,,",  # no currency: the workspace's
        "Tea,,,,,,1.5,JPY,,,",  # too many places for yen
        "Mixed,,,S,,,5,USD,,,",
        "Mixed,,,M,,,5,EUR,,,",
    )
    groups = csv_import._group(parsed.rows)
    csv_import._settle_prices(groups, "INR")
    ring, watch, tea, mixed_s, mixed_m = parsed.rows
    assert (ring.currency, ring.price_minor, ring.errors) == ("JPY", 1500, [])
    assert (watch.currency, watch.price_minor) == ("INR", 1050)
    assert tea.price_minor is None
    assert tea.errors
    assert (
        csv_import.COPY["currency_mixed"] in mixed_m.errors
        or csv_import.COPY["currency_mixed"] in mixed_s.errors
    )
