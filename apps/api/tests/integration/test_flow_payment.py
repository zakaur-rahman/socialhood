"""GR-32 follow-up: the flow step "request payment". It makes an order from the chosen products at
the catalogue's prices (or uses the conversation's latest unpaid order) and sends the payment
message; it needs the plan and the payment method at run time as well as at activation, and fails
with a plain reason otherwise."""

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
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.automations import make_automation
from tests.support.catalogue import make_product
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


async def execute(world: World, sql: str, **params: Any) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(text(sql), params)


async def with_flow(world: World, definition: dict[str, Any]) -> None:
    automation_id = await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, message_text=None
    )
    await execute(
        world,
        "INSERT INTO automation_flows (workspace_id, automation_id, version, definition)"
        " VALUES (:w, :a, 1, CAST(:d AS jsonb))",
        w=world.wid,
        a=automation_id,
        d=json.dumps(definition),
    )
    await execute(world, "UPDATE automations SET flow_version = 1 WHERE id = :a", a=automation_id)


async def upi(world: World) -> None:
    await execute(
        world,
        "INSERT INTO payment_connections (workspace_id, webhook_token, upi_vpa, upi_name)"
        " VALUES (:w, :t, 'shop@okbank', 'Maple')",
        w=world.wid,
        t=f"tok-{uuid.uuid4().hex}",
    )


def pay_flow(**step: Any) -> dict[str, Any]:
    return {
        "start": "pay",
        "steps": [
            {"type": "payment", "id": "pay", "method": "upi", **step},
            {"type": "send", "id": "after", "text": "Thanks!"},
        ],
    }


async def start(world: World) -> dict[str, Any]:
    dm = await world.dm(ref(), "I want the kurta")
    assert dm is not None
    assert await world.run("dm", dm) is Outcome.FIRED
    return await world.run_row()


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


async def test_the_step_orders_the_chosen_products_and_sends_the_upi_request(world: World) -> None:
    await set_plan(world.engine, str(world.wid), "pro")
    await upi(world)
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(
        world,
        pay_flow(
            items=[
                {
                    "product_id": str(kurta.id),
                    "variant_id": str(kurta.variants["Blue / M"]),
                    "quantity": 2,
                }
            ],
            intro="Here is your order:",
        ),
    )

    await start(world)

    [sent] = await outbound(world)
    assert sent["source"] == "automation"
    assert sent["text"].startswith("Here is your order:\n\nOrder #1\n2 x Cotton kurta - Blue / M")
    assert "Total: INR 1598.00" in sent["text"]
    assert "upi://pay?pa=shop%40okbank" in sent["text"]
    [order] = await world.rows("SELECT * FROM orders")
    assert (order["source"], order["status"], order["total_minor"]) == (
        "flow",
        "awaiting_payment",
        159800,
    )
    assert order["created_by_user_id"] is None
    [line] = await world.rows("SELECT name, quantity, unit_price_minor FROM order_items")
    assert (line["quantity"], line["unit_price_minor"]) == (2, 79900)
    audit = await world.rows(
        "SELECT action, actor_label FROM audit_events WHERE target_type = 'order'"
    )
    assert sorted(a["action"] for a in audit) == ["order.created", "order.payment_requested"]
    assert all(a["actor_label"].startswith("Automation: ") for a in audit)
    [step] = await world.rows("SELECT status, detail FROM automation_run_steps")
    assert step["status"] == "sent"
    assert step["detail"]["order_id"] == str(order["id"])


async def test_the_price_is_the_catalogues_when_the_step_runs(world: World) -> None:
    await set_plan(world.engine, str(world.wid), "pro")
    await upi(world)
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(
        world,
        pay_flow(
            items=[{"product_id": str(kurta.id), "variant_id": str(kurta.variants["Blue / M"])}]
        ),
    )
    await execute(
        world,
        "UPDATE product_variants SET price_minor = 99900 WHERE id = :v",
        v=kurta.variants["Blue / M"],
    )
    await start(world)
    [order] = await world.rows("SELECT total_minor FROM orders")
    assert order["total_minor"] == 99900


async def test_draft_mode_asks_for_the_conversations_unpaid_order(world: World) -> None:
    await set_plan(world.engine, str(world.wid), "pro")
    await upi(world)
    await with_flow(world, pay_flow(source="draft"))
    dm = await world.dm(ref(), "I want the kurta")
    assert dm is not None
    [conv] = await world.rows("SELECT id, contact_id FROM conversations")
    await execute(
        world,
        "INSERT INTO orders (workspace_id, number, contact_id, conversation_id, status, source,"
        " currency, total_minor) VALUES (:w, 7, :c, :v, 'draft', 'inbox', 'INR', 79900)",
        w=world.wid,
        c=conv["contact_id"],
        v=conv["id"],
    )
    await execute(
        world,
        "INSERT INTO order_items (workspace_id, order_id, name, quantity, unit_price_minor,"
        " line_total_minor) SELECT :w, id, 'Cotton kurta', 1, 79900, 79900 FROM orders",
        w=world.wid,
    )

    assert await world.run("dm", dm) is Outcome.FIRED

    [sent] = await outbound(world)
    assert "Order #7" in sent["text"]
    assert "Total: INR 799.00" in sent["text"]
    orders = await world.rows("SELECT number, status FROM orders")
    assert [(o["number"], o["status"]) for o in orders] == [(7, "awaiting_payment")]  # no new order


async def test_draft_mode_with_nothing_to_ask_for_fails_with_a_reason(world: World) -> None:
    await set_plan(world.engine, str(world.wid), "pro")
    await upi(world)
    await with_flow(world, pay_flow(source="draft"))
    dm = await world.dm(ref(), "I want the kurta")
    assert dm is not None
    await world.run("dm", dm)
    [step] = await world.rows("SELECT status, detail FROM automation_run_steps")
    assert step["status"] == "failed"
    assert step["detail"]["error_code"] == "no_order"
    assert step["detail"]["error"] == "There is no unpaid order in this conversation to ask for."
    assert await outbound(world) == []


async def test_a_workspace_that_left_pro_fails_the_step_at_run_time(world: World) -> None:
    await upi(world)  # the plan is Free
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(
        world,
        pay_flow(
            items=[{"product_id": str(kurta.id), "variant_id": str(kurta.variants["Blue / M"])}]
        ),
    )
    dm = await world.dm(ref(), "I want the kurta")
    assert dm is not None
    await world.run("dm", dm)
    [step] = await world.rows("SELECT status, detail FROM automation_run_steps")
    assert (step["status"], step["detail"]["error_code"]) == ("failed", "entitlement_required")
    assert step["detail"]["error"] == "Orders are part of Pro."
    assert await world.rows("SELECT id FROM orders") == []


async def test_a_method_that_is_not_set_up_fails_the_step_with_the_reason(world: World) -> None:
    await set_plan(world.engine, str(world.wid), "pro")  # no UPI address saved
    kurta = await make_product(world.engine, workspace_id=world.wid)
    await with_flow(
        world,
        pay_flow(
            items=[{"product_id": str(kurta.id), "variant_id": str(kurta.variants["Blue / M"])}]
        ),
    )
    dm = await world.dm(ref(), "I want the kurta")
    assert dm is not None
    await world.run("dm", dm)
    [step] = await world.rows("SELECT status, detail FROM automation_run_steps")
    assert step["status"] == "failed"
    assert "UPI address isn't set up" in step["detail"]["error"]


# ---------------------------------------------------------------- saving and activating


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def test_saving_a_payment_step_needs_the_plan(ws: Ws, engine: AsyncEngine) -> None:
    draft = await ws.ok("POST", "/automations", 201, json={"name": "Pay"})
    free = await ws.call("PUT", f"/automations/{draft['id']}/flow", json=pay_flow(source="draft"))
    assert free.status_code == 402
    assert (free.json()["code"], free.json()["entitlement"]) == ("entitlement_required", "commerce")
    assert free.json()["detail"] == "Asking for payment is part of Pro."


async def test_activation_checks_the_method_and_the_lines(ws: Ws, engine: AsyncEngine) -> None:
    await set_plan(engine, ws.wid, "pro")
    kurta = await make_product(engine, workspace_id=ws.wid)
    draft = await ws.draft(message_text=None)

    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=pay_flow())
    assert set(saved["missing_for_activation"]) >= {"flow.steps.0.method"}  # UPI isn't set up

    await ws.ok("PUT", "/integrations/payments/upi", json={"vpa": "shop@okbank", "name": "Maple"})
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=pay_flow())
    assert saved["missing_for_activation"] == ["flow.steps.0.items"]  # nothing to sell

    no_variant = pay_flow(items=[{"product_id": str(kurta.id)}])
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=no_variant)
    assert saved["missing_for_activation"] == ["flow.steps.0.items.0.variant_id"]

    gone = pay_flow(items=[{"product_id": str(uuid.uuid4())}])
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=gone)
    assert saved["missing_for_activation"] == ["flow.steps.0.items.0.product_id"]

    good = pay_flow(
        items=[{"product_id": str(kurta.id), "variant_id": str(kurta.variants["Blue / M"])}]
    )
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=good)
    assert saved["missing_for_activation"] == []
    assert (await ws.ok("POST", f"/automations/{draft['id']}/activate"))["status"] == "active"

    draft_mode = await ws.draft(message_text=None)
    saved = await ws.ok(
        "PUT", f"/automations/{draft_mode['id']}/flow", json=pay_flow(source="draft")
    )
    assert saved["missing_for_activation"] == []  # an order from the conversation needs no lines
