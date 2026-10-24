"""GR-31: CSV import. The preview says line by line what would be created, updated or left out;
the import saves the same reading. Upsert by SKU, else by name and variant; a blank cell never
clears a value; the plan's rows and products; the header row's documentation."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing import plans
from socialhood.services.catalogue import csv_import
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.catalogue import make_product

HEADER = "name,description,sku,variant,option1_name,option1_value,price,currency,stock,url,active"
FILE = "\n".join(
    [
        HEADER,
        "Cotton kurta,Soft cotton,,Blue / M,Colour,Blue,799,INR,12,https://maple.example/kurta,yes",
        "Cotton kurta,,KUR-BL-L,Blue / L,Colour,Blue,849.50,,0,,",
        "Silk scarf,Hand dyed,SCARF-1,,,,499,INR,,https://maple.example/scarf,",
        ",,,,,,10,,,,",  # no name
        "Hat,,,,,,lots,INR,,,",  # a bad price
    ]
)


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Ws:
    made = await workspace(client, clerk)
    await set_plan(engine, made.wid, "pro")
    return made


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def test_the_preview_lists_every_line_and_saves_nothing(ws: Ws, engine: AsyncEngine) -> None:
    preview = await ws.ok("POST", "/products/import/preview", json={"csv": FILE})

    assert (preview["total_rows"], preview["create"], preview["update"], preview["errors"]) == (
        5,
        3,
        0,
        2,
    )
    assert preview["products"] == 2
    assert preview["row_cap"] == plans.ENTITLEMENTS["catalogue_import_rows"]["pro"]
    assert preview["columns"] == list(csv_import.COLUMNS)
    assert preview["ignored_columns"] == []
    by_line = {r["line"]: r for r in preview["rows"]}
    assert [by_line[n]["action"] for n in (2, 3, 4, 5, 6)] == [
        "create",
        "create",
        "create",
        "error",
        "error",
    ]
    assert by_line[2]["variant"] == "Blue / M"
    assert by_line[5]["errors"] == [csv_import.COPY["name"]]
    assert "number" in by_line[6]["errors"][0]
    assert await rows(engine, "SELECT id FROM products") == []


async def test_the_import_saves_the_valid_lines_and_skips_the_rest(
    ws: Ws, engine: AsyncEngine
) -> None:
    result = await ws.ok("POST", "/products/import", json={"csv": FILE})
    assert result == {"created": 3, "updated": 0, "skipped": 2, "products": 2}

    products = await ws.ok("GET", "/products")
    by_name = {p["name"]: p for p in products["items"]}
    kurta, scarf = by_name["Cotton kurta"], by_name["Silk scarf"]
    assert kurta["source"] == scarf["source"] == "csv"
    assert kurta["url"] == "https://maple.example/kurta"
    assert kurta["description"] == "Soft cotton"
    assert [(v["title"], v["price_minor"], v["stock"], v["sku"]) for v in kurta["variants"]] == [
        ("Blue / M", 79900, 12, None),
        ("Blue / L", 84950, 0, "KUR-BL-L"),
    ]
    assert (scarf["price_minor"], scarf["stock"], scarf["sku"]) == (49900, None, "SCARF-1")
    assert scarf["variants"] == []


async def test_a_second_import_updates_by_sku_and_by_name_and_variant(ws: Ws) -> None:
    await ws.ok("POST", "/products/import", json={"csv": FILE})
    again = "\n".join(
        [
            HEADER,
            # by name + variant: the price changes, and a new variant is added
            "cotton kurta,,,Blue / M,,,899,,,,",
            "Cotton kurta,,,Red / M,Colour,Red,799,,,,",
            # by SKU: a renamed variant is still the same variant
            "Cotton kurta,,KUR-BL-L,Blue / Large,,,849.50,,5,,",
            # a plain product by SKU, stock filled in, nothing else touched
            "Silk scarf,,SCARF-1,,,,549,,7,,",
        ]
    )
    preview = await ws.ok("POST", "/products/import/preview", json={"csv": again})
    assert [r["action"] for r in preview["rows"]] == ["update", "create", "update", "update"]
    result = await ws.ok("POST", "/products/import", json={"csv": again})
    assert result == {"created": 1, "updated": 3, "skipped": 0, "products": 2}

    items = {p["name"]: p for p in (await ws.ok("GET", "/products"))["items"]}
    kurta, scarf = items["Cotton kurta"], items["Silk scarf"]
    assert len(items) == 2  # nothing was duplicated
    assert [(v["title"], v["price_minor"], v["stock"]) for v in kurta["variants"]] == [
        ("Blue / M", 89900, 12),  # a blank stock keeps 12
        ("Blue / Large", 84950, 5),
        ("Red / M", 79900, None),
    ]
    # A blank cell never clears: the description, url and picture stay.
    assert kurta["description"] == "Soft cotton"
    assert kurta["url"] == "https://maple.example/kurta"
    assert (scarf["price_minor"], scarf["stock"], scarf["description"]) == (54900, 7, "Hand dyed")


async def test_a_product_saved_in_one_currency_is_not_repriced_in_another(ws: Ws) -> None:
    await ws.ok("POST", "/products/import", json={"csv": "name,price\nShirt,499\n"})
    again = await ws.ok(
        "POST", "/products/import/preview", json={"csv": "name,price,currency\nShirt,5,USD\n"}
    )
    assert again["errors"] == 1
    assert "saved in INR" in again["rows"][0]["errors"][0]


async def test_two_products_cannot_share_a_sku(ws: Ws, engine: AsyncEngine) -> None:
    await make_product(engine, workspace_id=ws.wid)
    file = "name,sku,price\nShirt,KUR-BL-M,10\nKurta again,KUR-BL-M,10\n"
    preview = await ws.ok("POST", "/products/import/preview", json={"csv": file})
    first, second = preview["rows"]
    assert first["errors"] == [csv_import.COPY["sku_of_variant"]]
    assert csv_import.COPY["sku_twice"] in second["errors"]


async def test_a_bad_file_and_the_plans_limits(ws: Ws, monkeypatch: pytest.MonkeyPatch) -> None:
    no_header = await ws.call("POST", "/products/import/preview", json={"csv": "Shirt,499\n"})
    assert no_header.status_code == 422
    assert no_header.json()["errors"][0]["field"] == "csv"
    too_big = await ws.call("POST", "/products/import/preview", json={"csv": "x" * 900_001})
    assert too_big.status_code == 422

    monkeypatch.setitem(plans.ENTITLEMENTS["catalogue_import_rows"], "pro", 2)
    over = await ws.call(
        "POST", "/products/import/preview", json={"csv": "name,price\nA,1\nB,1\nC,1\n"}
    )
    assert over.status_code == 402
    assert (over.json()["code"], over.json()["entitlement"], over.json()["limit"]) == (
        "quota_exceeded",
        "catalogue_import_rows",
        2,
    )

    monkeypatch.setitem(plans.ENTITLEMENTS["catalogue_products"], "pro", 1)
    capped = await ws.ok("POST", "/products/import/preview", json={"csv": "name,price\nA,1\nB,1\n"})
    assert [r["action"] for r in capped["rows"]] == ["create", "error"]
    assert capped["rows"][1]["errors"] == ["Your plan includes 1 products."]
    result = await ws.ok("POST", "/products/import", json={"csv": "name,price\nA,1\nB,1\n"})
    assert (result["created"], result["skipped"]) == (1, 1)
