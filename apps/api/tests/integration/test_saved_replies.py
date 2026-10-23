"""GR-21: saved replies. The routes and who may use them, filling a reply for a conversation's
contact, and a flow step that sends a saved reply (filled when it runs; a deleted reply fails the
step with a plain reason)."""

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
from tests.support.automation_api import Ws, workspace
from tests.support.automations import make_automation
from tests.support.inbox import make_thread
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


def fields_of(response: httpx.Response) -> list[str]:
    return [e["field"] for e in response.json().get("errors", [])]


async def become_agent(engine: AsyncEngine, ws: Ws) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": ws.wid},
        )


async def create(ws: Ws, shortcut: str = "price", **values: Any) -> dict[str, Any]:
    body = {"title": "Prices", "shortcut": shortcut, "body": "Hi {first_name}, from 499."}
    return await ws.ok("POST", "/saved-replies", 201, json={**body, **values})


# ---------------------------------------------------------------- the routes


async def test_a_reply_is_created_listed_changed_and_deleted(ws: Ws) -> None:
    empty = await ws.ok("GET", "/saved-replies")
    assert empty["items"] == []
    assert empty["max_items"] == 200

    made = await create(ws, "/Price")  # typed with a slash and a capital: stored as "price"
    assert (made["shortcut"], made["title"]) == ("price", "Prices")
    await create(ws, "faq", title="FAQ", body="Read our FAQ.")
    listed = await ws.ok("GET", "/saved-replies")
    assert [r["shortcut"] for r in listed["items"]] == ["faq", "price"]

    changed = await ws.ok(
        "PATCH", f"/saved-replies/{made['id']}", json={"shortcut": "prices", "body": "From 499."}
    )
    assert (changed["shortcut"], changed["body"], changed["title"]) == (
        "prices",
        "From 499.",
        "Prices",
    )

    await ws.ok("DELETE", f"/saved-replies/{made['id']}", 204)
    assert (
        await ws.call("PATCH", f"/saved-replies/{made['id']}", json={"title": "x"})
    ).status_code == 404
    assert [r["shortcut"] for r in (await ws.ok("GET", "/saved-replies"))["items"]] == ["faq"]


async def test_a_shortcut_is_unique_and_checked(ws: Ws) -> None:
    first = await create(ws, "price")
    taken = await ws.call(
        "POST", "/saved-replies", json={"title": "Again", "shortcut": "PRICE", "body": "x"}
    )
    assert taken.status_code == 409
    other = await create(ws, "hours", title="Hours", body="9 to 5.")
    clash = await ws.call("PATCH", f"/saved-replies/{other['id']}", json={"shortcut": "price"})
    assert clash.status_code == 409
    same = await ws.ok("PATCH", f"/saved-replies/{first['id']}", json={"shortcut": "price"})
    assert same["shortcut"] == "price"  # keeping its own shortcut is fine

    for bad in ("has space", "", "-lead", "x" * 31, "pr!ce"):
        response = await ws.call(
            "POST", "/saved-replies", json={"title": "Bad", "shortcut": bad, "body": "x"}
        )
        assert response.status_code == 422, bad
    empty_body = await ws.call(
        "POST", "/saved-replies", json={"title": "Empty", "shortcut": "empty", "body": ""}
    )
    assert empty_body.status_code == 422


async def test_agents_read_and_fill_but_do_not_manage(engine: AsyncEngine, ws: Ws) -> None:
    made = await create(ws)
    await become_agent(engine, ws)

    listed = await ws.ok("GET", "/saved-replies")
    assert [r["id"] for r in listed["items"]] == [made["id"]]
    for method, path, body in (
        ("POST", "/saved-replies", {"title": "T", "shortcut": "t", "body": "b"}),
        ("PATCH", f"/saved-replies/{made['id']}", {"title": "Changed"}),
        ("DELETE", f"/saved-replies/{made['id']}", None),
    ):
        response = await ws.call(method, path, json=body) if body else await ws.call(method, path)
        assert response.status_code == 403, (method, path)
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    filled = await ws.ok(
        "POST",
        f"/saved-replies/{made['id']}/fill",
        json={"conversation_id": str(thread.conversation_id)},
    )
    assert filled["text"].endswith("from 499.")


# ---------------------------------------------------------------- filling for a contact


async def test_a_reply_is_filled_for_the_conversations_contact(engine: AsyncEngine, ws: Ws) -> None:
    thread = await make_thread(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        contact_ref="priya.bakes",
        username="priya.bakes",
        display_name="Priya Shah",
    )
    await ws.ok("POST", "/contact-fields", 201, json={"key": "city", "label": "City"})
    await ws.ok("PATCH", f"/contacts/{thread.contact_id}", json={"fields": {"city": "Pune"}})
    reply = await create(
        ws,
        "price",
        body="Hi {first_name} (@{username}) in {city}! Order #{order_id|none}. {missing}Bye.",
    )

    filled = await ws.ok(
        "POST",
        f"/saved-replies/{reply['id']}/fill",
        json={"conversation_id": str(thread.conversation_id)},
    )
    assert filled == {"text": "Hi Priya (@priya.bakes) in Pune! Order #none. Bye."}


async def test_a_contact_without_a_name_gets_the_fallback_not_braces(
    engine: AsyncEngine, ws: Ws
) -> None:
    thread = await make_thread(
        engine, workspace_id=ws.wid, account_id=ws.account_id, display_name=None, username=None
    )
    reply = await create(ws, "hello", body="Hi {first_name}, {city} {email}.")
    filled = await ws.ok(
        "POST",
        f"/saved-replies/{reply['id']}/fill",
        json={"conversation_id": str(thread.conversation_id)},
    )
    assert filled["text"] == "Hi there,  ."


async def test_filling_for_a_conversation_that_is_not_here_is_not_found(ws: Ws) -> None:
    reply = await create(ws)
    response = await ws.call(
        "POST", f"/saved-replies/{reply['id']}/fill", json={"conversation_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# ---------------------------------------------------------------- a flow sends a saved reply


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


async def reply_row(world: World, body: str) -> uuid.UUID:
    reply_id = uuid.uuid4()
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO saved_replies (id, workspace_id, title, shortcut, body)"
                " VALUES (:i, :w, 'Prices', 'price', :b)"
            ),
            {"i": reply_id, "w": world.wid, "b": body},
        )
    return reply_id


async def flow_with(world: World, reply_id: uuid.UUID) -> uuid.UUID:
    """An active "link" automation whose flow sends the saved reply, then a thank-you."""
    automation_id = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        message_text=None,
    )
    definition = {
        "start": "prices",
        "steps": [
            {"type": "send", "id": "prices", "saved_reply_id": str(reply_id), "next": "thanks"},
            {"type": "send", "id": "thanks", "text": "Anything else?"},
        ],
    }
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


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


async def test_a_flow_step_sends_the_saved_reply_filled_when_it_runs(world: World) -> None:
    reply_id = await reply_row(world, "Hi {first_name|friend}, prices start at 499.")
    await flow_with(world, reply_id)
    dm = await world.dm("igsid_saved", "link please")
    assert dm is not None
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE contacts SET display_name = 'Priya Shah'"))
    # The reply is edited after the flow was saved: the run sends what it says now.
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE saved_replies SET body = 'Hi {first_name}, prices start at 399.'")
        )

    assert await world.run("dm", dm) is Outcome.FIRED

    [message] = await outbound(world)
    assert message["text"] == "Hi Priya, prices start at 399."
    run = await world.run_row()
    assert (run["result"], run["step_id"]) == ("sent", "prices")


async def test_a_deleted_saved_reply_fails_the_step_with_a_plain_reason(world: World) -> None:
    reply_id = await reply_row(world, "Prices start at 499.")
    await flow_with(world, reply_id)
    async with world.engine.begin() as conn:
        await conn.execute(text("DELETE FROM saved_replies"))
    dm = await world.dm("igsid_gone", "link please")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.FIRED

    assert await outbound(world) == []  # nothing went to the customer
    run = await world.run_row()
    assert run["result"] == "failed"
    assert run["error_code"] == "saved_reply_missing"
    assert run["error_message"] == "The saved reply this step sends was deleted. Choose another."
    [step] = await world.rows(
        "SELECT step_id, status, detail FROM automation_run_steps WHERE run_id = :r", r=run["id"]
    )
    assert (step["step_id"], step["status"]) == ("prices", "failed")
    assert step["detail"]["error_code"] == "saved_reply_missing"


async def test_the_flow_api_accepts_a_saved_reply_step_and_flags_a_deleted_one(ws: Ws) -> None:
    reply = await create(ws, "price", body="Prices start at 499.")
    created = await ws.ok("POST", "/automations", 201, json={"name": "Prices"})
    path = f"/automations/{created['id']}/flow"
    body = {
        "start": "prices",
        "steps": [{"type": "send", "id": "prices", "saved_reply_id": reply["id"]}],
    }
    saved = await ws.ok("PUT", path, json=body)
    assert saved["definition"]["steps"][0]["saved_reply_id"] == reply["id"]
    assert not any(field.startswith("flow.") for field in saved["missing_for_activation"])

    await ws.ok("DELETE", f"/saved-replies/{reply['id']}", 204)
    flagged = await ws.ok("GET", path)
    assert "flow.steps.0.saved_reply_id" in flagged["missing_for_activation"]
