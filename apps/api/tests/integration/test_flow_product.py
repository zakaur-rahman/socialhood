"""GR-31: the flow step "send product". It reads the catalogue when it runs (a price changed since
the flow was saved is what goes out), sends name, price, stock when recorded, the picture and the
link, names a variant or lists them, and fails with a plain reason when the product is gone. Saving
needs the plan; activation checks the product exists."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.automations import make_automation
from tests.support.catalogue import KURTA_URL, make_product
from tests.support.inbox import make_asset
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


def ref() -> str:
    return f"99{uuid.uuid4().int % 10**13:013d}"


async def with_flow(world: World, definition: dict[str, Any]) -> uuid.UUID:
    automation_id = await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, message_text=None
    )
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO automation_flows (workspace_id, automation_id, version, definition)"
                " VALUES (:w, :a, 1, CAST(:d AS jsonb))"
            ),
            {"w": world.wid, "a": automation_id, "d": json.dumps(definition)},
        )
        await conn.execute(
            text("UPDATE automations SET flow_version = 1 WHERE id = :a"), {"a": automation_id}
        )
    return automation_id


async def execute(world: World, sql: str, **params: Any) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(text(sql), params)


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


async def start(world: World) -> dict[str, Any]:
    """A "link" DM fires the flow; its first message is delivered. The run row."""
    dm = await world.dm(ref(), "link please")
    assert dm is not None
    assert await world.run("dm", dm) is Outcome.FIRED
    return await world.run_row()


async def deliver_last(world: World) -> dict[str, Any]:
    message = (await outbound(world))[-1]
    assert await world.send(message["id"]) is Delivery.SENT
    return message


def product_flow(product_id: uuid.UUID, **step: Any) -> dict[str, Any]:
    return {
        "start": "p",
        "steps": [
            {"type": "product", "id": "p", "product_id": str(product_id), "next": "after", **step},
            {"type": "send", "id": "after", "text": "Want to order?"},
        ],
    }


# ---------------------------------------------------------------- running the step


async def test_a_named_variant_goes_out_with_price_stock_and_link(world: World) -> None:
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(
        world,
        product_flow(
            kurta.id,
            variant_id=str(kurta.variants["Blue / M"]),
            intro="Here's the one you asked about:",
        ),
    )

    run = await start(world)

    [first] = await outbound(world)
    assert first["text"] == (
        "Here's the one you asked about:\n\nCotton kurta - Blue / M\nINR 799.00\nIn stock\n"
        + KURTA_URL
    )
    assert first["source"] == "automation"
    await deliver_last(world)
    assert await world.run("flow", run["id"]) is Outcome.FIRED  # the step after it
    assert (await outbound(world))[-1]["text"] == "Want to order?"


async def test_the_price_is_read_when_the_step_runs(world: World) -> None:
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(world, product_flow(kurta.id, variant_id=str(kurta.variants["Blue / L"])))
    await execute(
        world,
        "UPDATE product_variants SET price_minor = 99900, stock = 3 WHERE id = :v",
        v=kurta.variants["Blue / L"],
    )

    await start(world)

    assert "Cotton kurta - Blue / L\nINR 999.00\nIn stock" in (await outbound(world))[0]["text"]


async def test_unrecorded_stock_is_not_mentioned_and_zero_is_out_of_stock(world: World) -> None:
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(world, product_flow(kurta.id, variant_id=str(kurta.variants["Red / M"])))
    await start(world)
    text_ = (await outbound(world))[0]["text"]
    assert text_ == f"Cotton kurta - Red / M\nINR 799.00\n{KURTA_URL}"  # no stock line at all


async def test_a_product_without_a_variant_lists_them(world: World) -> None:
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(world, product_flow(kurta.id))
    await start(world)
    sent = (await outbound(world))[0]["text"]
    assert sent.startswith("Cotton kurta\nBlue / S: INR 799.00\nBlue / M: INR 799.00\n")
    assert "Blue / L: INR 849.00, out of stock" in sent
    assert sent.endswith(KURTA_URL)


async def test_the_picture_goes_with_it(world: World) -> None:
    asset = await make_asset(world.engine, workspace_id=world.wid)
    kurta = await make_product(world.engine, workspace_id=world.wid, image_asset_id=asset)
    await with_flow(world, product_flow(kurta.id, variant_id=str(kurta.variants["Blue / M"])))
    await start(world)
    [first] = await outbound(world)
    assert [a["asset_id"] for a in first["attachments"]] == [str(asset)]


async def test_a_deleted_product_fails_the_step_with_a_plain_reason(world: World) -> None:
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(world, product_flow(kurta.id))
    await execute(world, "DELETE FROM products WHERE id = :p", p=kurta.id)

    dm = await world.dm(ref(), "link please")
    assert dm is not None
    await world.run("dm", dm)

    run = await world.run_row()
    assert run["result"] == "failed"
    assert run["error_code"] == "product_gone"
    assert "deleted or switched off" in run["error_message"]
    assert await outbound(world) == []
    [step] = await world.rows("SELECT status, detail FROM automation_run_steps")
    assert step["status"] == "failed"
    assert step["detail"]["error_code"] == "product_gone"


async def test_a_product_switched_off_is_not_sent(world: World) -> None:
    kurta = await make_product(world.engine, workspace_id=world.wid, active=False)
    await with_flow(world, product_flow(kurta.id))
    dm = await world.dm(ref(), "link please")
    assert dm is not None
    await world.run("dm", dm)
    assert (await world.run_row())["error_code"] == "product_gone"


# ---------------------------------------------------------------- saving and activating


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


def one_step(product_id: Any, **step: Any) -> dict[str, Any]:
    return {
        "start": "p",
        "steps": [{"type": "product", "id": "p", "product_id": str(product_id), **step}],
    }


async def test_saving_a_product_step_needs_the_plan(ws: Ws, engine: AsyncEngine) -> None:
    kurta = await make_product(engine, workspace_id=ws.wid)
    draft = await ws.ok("POST", "/automations", 201, json={"name": "Product"})
    free = await ws.call("PUT", f"/automations/{draft['id']}/flow", json=one_step(kurta.id))
    assert free.status_code == 402
    assert (free.json()["code"], free.json()["entitlement"]) == ("entitlement_required", "commerce")
    assert free.json()["detail"] == "Sending products is part of Pro."

    await set_plan(engine, ws.wid, "pro")
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=one_step(kurta.id))
    assert saved["source"] == "flow"
    assert saved["definition"]["steps"][0]["product_id"] == str(kurta.id)


async def test_activation_checks_the_product_and_its_variant(ws: Ws, engine: AsyncEngine) -> None:
    await set_plan(engine, ws.wid, "pro")
    kurta = await make_product(engine, workspace_id=ws.wid)
    draft = await ws.draft(message_text=None)
    gone = uuid.uuid4()
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=one_step(gone))
    assert "flow.steps.0.product_id" in saved["missing_for_activation"]
    refused = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert refused.status_code == 422
    assert [e["field"] for e in refused.json()["errors"]] == ["flow.steps.0.product_id"]

    bad_variant = one_step(kurta.id, variant_id=str(uuid.uuid4()))
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=bad_variant)
    assert "flow.steps.0.variant_id" in saved["missing_for_activation"]

    good = one_step(kurta.id, variant_id=str(kurta.variants["Blue / M"]))
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=good)
    assert saved["missing_for_activation"] == []
    assert (await ws.ok("POST", f"/automations/{draft['id']}/activate"))["status"] == "active"
