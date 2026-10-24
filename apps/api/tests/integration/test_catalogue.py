"""GR-31: the product catalogue API. Pro and Max only for writing (PD-8), reading never refused;
money in minor units; variants with their own price, stock and SKU; search; the plan's product cap;
roles; another workspace's picture is a 404 on every plan."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing import plans
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.catalogue import make_product
from tests.support.inbox import make_asset

KURTA: dict[str, Any] = {
    "name": "Cotton kurta",
    "description": "Soft cotton.",
    "url": "https://maple.example/kurta",
    "variants": [
        {
            "title": "Blue / M",
            "options": {"Colour": "Blue", "Size": "M"},
            "price": "799",
            "stock": 12,
        },
        {"title": "Blue / L", "price": "849.50", "sku": "KUR-BL-L", "stock": 0},
    ],
}


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Ws:
    made = await workspace(client, clerk)
    await set_plan(engine, made.wid, "pro")
    return made


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


# ---------------------------------------------------------------- the plan


async def test_free_reads_but_cannot_write(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    free = await workspace(client, clerk)
    listing = await free.ok("GET", "/products")
    assert listing["items"] == []
    assert listing["limits"] == {
        "entitled": False,
        "product_cap": 0,
        "import_row_cap": 0,
        "csv_max_chars": 900_000,
        "default_currency": "INR",
    }
    refused = await free.call("POST", "/products", json={"name": "Shirt", "price": "499"})
    assert refused.status_code == 402
    assert (refused.json()["code"], refused.json()["entitlement"]) == (
        "entitlement_required",
        "commerce",
    )
    assert refused.json()["detail"] == "The product catalogue is part of Pro."
    # What exists is still shown after a downgrade.
    made = await make_product(engine, workspace_id=free.wid)
    assert [p["name"] for p in (await free.ok("GET", "/products"))["items"]] == ["Cotton kurta"]
    assert (await free.call("GET", f"/products/{made.id}")).status_code == 200
    for method, path, body in [
        ("PATCH", f"/products/{made.id}", {"name": "Renamed"}),
        ("DELETE", f"/products/{made.id}", None),
        ("POST", "/products/import/preview", {"csv": "name,price\nShirt,499\n"}),
        ("POST", "/products/import", {"csv": "name,price\nShirt,499\n"}),
    ]:
        response = await free.call(method, path, json=body)
        assert response.status_code == 402, (method, path)


async def test_an_agent_reads_nothing_and_writes_nothing(ws: Ws, engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": ws.wid},
        )
    for method, path in [
        ("GET", "/products"),
        ("POST", "/products"),
        ("POST", "/products/import"),
        ("GET", "/integrations/shopify"),
    ]:
        assert (await ws.call(method, path, json={})).status_code == 403, (method, path)


# ---------------------------------------------------------------- products


async def test_a_product_with_variants_keeps_money_in_minor_units(ws: Ws) -> None:
    created = await ws.ok("POST", "/products", 201, json=KURTA)

    assert (created["currency"], created["source"], created["active"]) == ("INR", "manual", True)
    assert created["price_minor"] is None  # priced per variant
    first, second = created["variants"]
    assert (first["title"], first["price_minor"], first["price"], first["stock"]) == (
        "Blue / M",
        79900,
        "799.00",
        12,
    )
    assert (second["price_minor"], second["price"], second["stock"], second["sku"]) == (
        84950,
        "849.50",
        0,
        "KUR-BL-L",
    )
    assert [v["position"] for v in created["variants"]] == [0, 1]
    assert first["options"] == {"Colour": "Blue", "Size": "M"}
    again = await ws.ok("GET", f"/products/{created['id']}")
    assert again == created


async def test_a_plain_product_and_an_unrecorded_stock(ws: Ws) -> None:
    created = await ws.ok(
        "POST", "/products", 201, json={"name": "Silk scarf", "price": "499", "currency": "usd"}
    )
    assert (created["currency"], created["price_minor"], created["stock"]) == ("USD", 49900, None)
    listing = await ws.ok("GET", "/products")
    assert listing["limits"]["entitled"] is True
    assert listing["limits"]["default_currency"] == "USD"  # the newest product's


async def test_what_is_wrong_is_named_by_field(ws: Ws) -> None:
    async def errors(body: dict[str, Any]) -> dict[str, str]:
        response = await ws.call("POST", "/products", json=body)
        assert response.status_code == 422, response.text
        return {e["field"]: e["message"] for e in response.json()["errors"]}

    assert "price" in await errors({"name": "No price"})
    assert "price" in await errors({"name": "Bad", "price": "12.345"})
    assert "url" in await errors({"name": "Plain http", "price": "1", "url": "http://x.test/a"})
    assert "image_url" in await errors({"name": "Pic", "price": "1", "image_url": "ftp://x"})
    assert (
        "currency"
        in (
            await ws.call("POST", "/products", json={"name": "C", "price": "1", "currency": "RS"})
        ).text
    )
    twice = await errors(
        {
            "name": "Twice",
            "variants": [
                {"title": "M", "price": "1"},
                {"title": "m", "price": "1"},
            ],
        }
    )
    assert "variants.1.title" in twice
    sku = await errors(
        {
            "name": "Skus",
            "variants": [
                {"title": "S", "price": "1", "sku": "A"},
                {"title": "M", "price": "1", "sku": "A"},
            ],
        }
    )
    assert "variants.1.sku" in sku or "sku" in sku
    assert (
        await ws.call("POST", "/products", json={"name": "x" * 201, "price": "1"})
    ).status_code == 422


async def test_a_sku_belongs_to_one_product(ws: Ws) -> None:
    await ws.ok("POST", "/products", 201, json=KURTA)
    clash = await ws.call(
        "POST", "/products", json={"name": "Other", "price": "5", "sku": "KUR-BL-L"}
    )
    assert clash.status_code == 422
    assert clash.json()["errors"][0] == {
        "field": "sku",
        "message": "Another product already uses this SKU.",
    }


async def test_a_change_keeps_variants_by_id_and_drops_the_rest(
    ws: Ws, engine: AsyncEngine
) -> None:
    created = await ws.ok("POST", "/products", 201, json=KURTA)
    medium, large = created["variants"]
    changed = await ws.ok(
        "PATCH",
        f"/products/{created['id']}",
        json={
            "name": "Cotton kurta v2",
            "variants": [
                {"id": medium["id"], "title": "Blue / M", "price": "899", "stock": 3},
                {"title": "Blue / XL", "price": "999"},
            ],
        },
    )
    assert changed["name"] == "Cotton kurta v2"
    kept, new = changed["variants"]
    assert (kept["id"], kept["price_minor"], kept["stock"]) == (medium["id"], 89900, 3)
    assert new["title"] == "Blue / XL"
    assert new["id"] not in (medium["id"], large["id"])
    gone = await rows(engine, "SELECT id FROM product_variants WHERE id = :i", i=large["id"])
    assert gone == []
    # Only what is sent changes.
    untouched = await ws.ok("PATCH", f"/products/{created['id']}", json={"active": False})
    assert untouched["active"] is False
    assert untouched["name"] == "Cotton kurta v2"
    assert len(untouched["variants"]) == 2


async def test_delete_and_search(ws: Ws) -> None:
    kurta = await ws.ok("POST", "/products", 201, json=KURTA)
    scarf = await ws.ok("POST", "/products", 201, json={"name": "Silk scarf", "price": "499"})
    by_variant = await ws.ok("GET", "/products", params={"q": "xl blue"})
    assert by_variant["total"] == 0
    by_variant = await ws.ok("GET", "/products", params={"q": "blue"})
    assert [p["id"] for p in by_variant["items"]] == [kurta["id"]]
    by_sku = await ws.ok("GET", "/products", params={"q": "kur-bl-l"})
    assert by_sku["total"] == 1
    off = await ws.ok("PATCH", f"/products/{scarf['id']}", json={"active": False})
    assert [
        p["id"] for p in (await ws.ok("GET", "/products", params={"active": False}))["items"]
    ] == [off["id"]]
    assert (await ws.call("DELETE", f"/products/{kurta['id']}")).status_code == 204
    assert (await ws.call("GET", f"/products/{kurta['id']}")).status_code == 404
    assert (await ws.ok("GET", "/products"))["total"] == 1


async def test_the_plans_product_cap(
    ws: Ws, monkeypatch: pytest.MonkeyPatch, engine: AsyncEngine
) -> None:
    monkeypatch.setitem(plans.ENTITLEMENTS["catalogue_products"], "pro", 1)
    await ws.ok("POST", "/products", 201, json={"name": "One", "price": "1"})
    over = await ws.call("POST", "/products", json={"name": "Two", "price": "1"})
    assert over.status_code == 402
    assert (over.json()["code"], over.json()["entitlement"], over.json()["limit"]) == (
        "quota_exceeded",
        "catalogue_products",
        1,
    )
    assert over.json()["detail"] == "Your plan includes 1 products."


async def test_another_workspaces_picture_is_a_404_even_on_free(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    mine = await workspace(client, clerk, email="a@example.com")
    theirs = await workspace(client, clerk, email="b@example.com")
    asset = await make_asset(engine, workspace_id=theirs.wid)
    for plan in ("free", "pro"):
        await set_plan(engine, mine.wid, plan)
        refused = await mine.call(
            "POST", "/products", json={"name": "Shirt", "price": "1", "image_asset_id": str(asset)}
        )
        assert (refused.status_code, refused.json()["code"]) == (404, "not_found")
    own = await make_asset(engine, workspace_id=mine.wid)
    made = await mine.ok(
        "POST", "/products", 201, json={"name": "Shirt", "price": "1", "image_asset_id": str(own)}
    )
    assert made["image_asset_id"] == str(own)
    assert made["image_url"].endswith("/sample.jpg")  # the uploaded picture's address


async def test_the_audit_log_records_who_changed_the_catalogue(ws: Ws, engine: AsyncEngine) -> None:
    made = await ws.ok("POST", "/products", 201, json={"name": "Shirt", "price": "1"})
    await ws.ok("PATCH", f"/products/{made['id']}", json={"name": "Shirt 2"})
    await ws.call("DELETE", f"/products/{made['id']}")
    logged = await rows(engine, "SELECT action FROM audit_events ORDER BY created_at, id")
    assert [r["action"] for r in logged] == [
        "product.created",
        "product.updated",
        "product.deleted",
    ]
