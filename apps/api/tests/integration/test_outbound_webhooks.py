"""GR-04: outbound webhooks. Done when a test endpoint receives a signed lead.captured, and a
failing endpoint shows its retries in the log. Plus the endpoints API, the events ingest and the
contacts service raise, replays, and turning off an endpoint that keeps failing."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.schemas.integrations import WebhookEndpointCreate
from socialhood.security import ssrf
from socialhood.security.signatures import verify_standard_webhook
from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.services.webhooks import delivery, endpoints
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.automations import make_automation
from tests.support.ingest import jobs
from tests.support.notify_team import make_user
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

HOOK = "https://hooks.example.com/in"


# ---------------------------------------------------------------- the API


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def test_endpoints_over_the_api(ws: Ws, engine: AsyncEngine, queue: None) -> None:
    catalogue = await ws.ok("GET", "/webhook-events")
    assert "lead.captured" in [e["type"] for e in catalogue["items"]]

    made = await ws.ok(
        "POST",
        "/webhook-endpoints",
        201,
        json={"url": HOOK, "description": "Zapier", "events": ["lead.captured"]},
    )
    assert made["signing_secret"].startswith("whsec_")
    assert made["status"] == "active"
    listed = await ws.ok("GET", "/webhook-endpoints")
    assert [e["id"] for e in listed["items"]] == [made["id"]]
    assert "signing_secret" not in listed["items"][0]  # shown once
    assert listed["limit"] == 1  # Free (C-080)

    over = await ws.call(
        "POST", "/webhook-endpoints", json={"url": HOOK, "events": ["lead.captured"]}
    )
    assert (over.status_code, over.json()["entitlement"]) == (402, "webhook_endpoints")
    await set_plan(engine, ws.wid, "pro")
    plain = await ws.call(
        "POST",
        "/webhook-endpoints",
        json={"url": "http://hooks.example.com", "events": ["lead.captured"]},
    )
    assert plain.status_code == 422
    assert plain.json()["errors"][0]["field"] == "url"

    paused = await ws.ok(
        "PATCH",
        f"/webhook-endpoints/{made['id']}",
        json={"status": "paused", "events": ["lead.captured", "contact.tagged"]},
    )
    assert (paused["status"], paused["events"]) == ("paused", ["lead.captured", "contact.tagged"])
    refused = await ws.call("POST", f"/webhook-endpoints/{made['id']}/test")
    assert refused.status_code == 409  # turn it on first
    await ws.ok("PATCH", f"/webhook-endpoints/{made['id']}", json={"status": "active"})
    test = await ws.ok("POST", f"/webhook-endpoints/{made['id']}/test", 202)
    assert (test["event_type"], test["status"]) == ("webhook.test", "pending")
    assert [j["args"]["delivery_id"] for j in await jobs("deliver_webhook")] == [test["id"]]
    log = await ws.ok("GET", f"/webhook-endpoints/{made['id']}/deliveries")
    assert [d["id"] for d in log["items"]] == [test["id"]]

    rotated = await ws.ok("POST", f"/webhook-endpoints/{made['id']}/rotate-secret")
    assert rotated["signing_secret"] not in (made["signing_secret"], None)
    await ws.ok("DELETE", f"/webhook-endpoints/{made['id']}", 204)
    assert (await ws.call("GET", f"/webhook-endpoints/{made['id']}")).status_code == 404


# ---------------------------------------------------------------- events and deliveries


@pytest.fixture(autouse=False)
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
    _outbox: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


class Receiver:
    """Stands in for ssrf.post_json: records each request and answers ``status``."""

    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.requests: list[tuple[str, bytes, dict[str, str]]] = []

    async def __call__(
        self, url: str, body: bytes, headers: dict[str, str], **kw: Any
    ) -> ssrf.Posted:
        self.requests.append((url, body, headers))
        if self.status == 0:
            raise ssrf.FetchError("connect", "Couldn't connect to the endpoint.")
        return ssrf.Posted(self.status, 12)


async def add_endpoint(world: World, events: list[str]) -> tuple[uuid.UUID, str]:
    with workspace_scope(world.wid):
        async with world.maker() as session:
            made, secret = await endpoints.create(
                session,
                WebhookEndpointCreate(url=HOOK, events=events),  # type: ignore[arg-type]
                cipher=world.deps.cipher,
                user_id=None,
                allow_private=False,
            )
            await session.commit()
            return made.id, secret


async def pending(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM webhook_deliveries WHERE status = 'pending' ORDER BY created_at, event_type"
    )


async def deliver(
    world: World, delivery_id: uuid.UUID, post: Receiver, *, now: datetime | None = None
) -> str:
    with workspace_scope(world.wid):
        return await delivery.deliver(
            world.maker,
            world.deps.cipher,
            delivery_id=delivery_id,
            now=now or datetime.now(UTC),
            post=post,
        )


def ref() -> str:
    return f"99{uuid.uuid4().int % 10**13:013d}"


async def test_no_endpoint_no_deliveries(world: World) -> None:
    assert await world.dm(ref(), "hello") is not None
    assert await world.rows("SELECT id FROM webhook_deliveries") == []


async def test_a_new_dm_raises_contact_created_and_message_received(world: World) -> None:
    _, secret = await add_endpoint(world, ["contact.created", "message.received"])
    author = ref()
    assert await world.dm(author, "Is the hamper available?") is not None
    found = await pending(world)
    assert [d["event_type"] for d in found] == ["contact.created", "message.received"]
    received = next(d for d in found if d["event_type"] == "message.received")
    data = received["payload"]["data"]
    assert data["message"]["text"] == "Is the hamper available?"
    assert data["contact"]["platform"] == "instagram"
    assert "email" not in data["contact"]

    receiver = Receiver(204)
    assert await deliver(world, received["id"], receiver) == "delivered"
    [(url, body, headers)] = receiver.requests
    assert url == HOOK
    assert json.loads(body)["id"] == headers["webhook-id"] == str(received["event_id"])
    assert verify_standard_webhook(body, headers, secret)
    [row] = await world.rows("SELECT * FROM webhook_deliveries WHERE id = :d", d=received["id"])
    assert (row["status"], row["attempts"], row["response_code"], row["duration_ms"]) == (
        "succeeded",
        1,
        204,
        12,
    )
    # A second message from them: no second contact.created.
    assert await world.dm(author, "And the price?") is not None
    assert [d["event_type"] for d in await pending(world)] == [
        "contact.created",
        "message.received",
    ]


async def test_a_failing_endpoint_shows_its_retries_then_is_turned_off(world: World) -> None:
    await add_endpoint(world, ["message.received"])
    owner = await make_user(world.engine)  # someone to tell
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'owner')"
            ),
            {"w": world.wid, "u": owner},
        )
    failing = Receiver(500)
    now = datetime.now(UTC)
    for n in range(delivery.DISABLE_AFTER):
        assert await world.dm(ref(), f"hello {n}") is not None
        [row] = await pending(world)
        at = now
        for attempt in range(1, delivery.MAX_ATTEMPTS + 1):
            outcome = await deliver(world, row["id"], failing, now=at)
            [state] = await world.rows(
                "SELECT * FROM webhook_deliveries WHERE id = :d", d=row["id"]
            )
            assert state["attempts"] == attempt
            assert (state["response_code"], state["error"]) == (500, "The endpoint answered 500.")
            if attempt < delivery.MAX_ATTEMPTS:
                assert outcome == "retrying"
                wait = delivery.backoff(attempt)
                assert wait is not None
                assert state["next_attempt_at"] == at + wait
                at += wait
            else:
                assert outcome == "failed"
                assert state["status"] == "failed"
        [endpoint] = await world.rows("SELECT * FROM webhook_endpoints")
        assert endpoint["failing_deliveries"] == n + 1
    assert endpoint["status"] == "disabled"
    [note] = await world.rows("SELECT type, title FROM notifications")
    assert note == {"type": "webhook_disabled", "title": "A webhook endpoint was turned off"}
    # Retries are deferred jobs.
    deferred = [j for j in await jobs("deliver_webhook") if j["deferred"]]
    assert deferred

    # Turned off: new events aren't queued, and a pending one fails without a request.
    assert await world.dm(ref(), "anyone?") is not None
    assert await pending(world) == []


async def test_a_replay_sends_the_same_event_again(world: World) -> None:
    await add_endpoint(world, ["message.received"])
    assert await world.dm(ref(), "hello") is not None
    [first] = await pending(world)
    assert await deliver(world, first["id"], Receiver(0)) == "retrying"  # no connection
    [row] = await world.rows("SELECT error FROM webhook_deliveries")
    assert row["error"] == "Couldn't connect to the endpoint."
    with workspace_scope(world.wid):
        async with world.maker() as session:
            replayed = await endpoints.replay(session, first["id"], now=datetime.now(UTC))
            await session.commit()
    assert (replayed.event_id, replayed.replay_of_id) == (first["event_id"], first["id"])
    receiver = Receiver(200)
    assert await deliver(world, replayed.id, receiver) == "delivered"
    assert receiver.requests[0][2]["webhook-id"] == str(first["event_id"])


async def save_flow(world: World, definition: dict[str, Any]) -> uuid.UUID:
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


async def test_a_captured_email_is_a_signed_lead_captured(world: World) -> None:
    _, secret = await add_endpoint(world, ["lead.captured", "automation.run.completed"])
    await save_flow(
        world,
        {
            "start": "q",
            "steps": [{"type": "ask", "id": "q", "text": "Your email?", "expect": "email"}],
        },
    )
    author = ref()
    dm = await world.dm(author, "link please")
    assert dm is not None
    assert await world.run("dm", dm) is Outcome.FIRED
    [question] = await world.rows("SELECT id FROM messages WHERE direction = 'outbound'")
    assert await world.send(question["id"]) is Delivery.SENT
    answer = await world.dm(author, "Priya@Example.com")
    assert answer is not None
    assert await world.run("dm", answer) is Outcome.ANSWERED

    found = await pending(world)
    assert [d["event_type"] for d in found] == ["automation.run.completed", "lead.captured"]
    lead = next(d for d in found if d["event_type"] == "lead.captured")
    assert lead["payload"]["data"]["captured"] == {
        "kind": "email",
        "field_key": None,
        "value": "priya@example.com",
    }
    receiver = Receiver(200)
    assert await deliver(world, lead["id"], receiver) == "delivered"
    [(_, body, headers)] = receiver.requests
    assert verify_standard_webhook(body, headers, secret)
    assert json.loads(body)["type"] == "lead.captured"
    completed = next(d for d in found if d["event_type"] == "automation.run.completed")
    assert completed["payload"]["data"]["run"]["result"] == "sent"


async def test_a_run_on_its_settings_completes_once(world: World) -> None:
    await add_endpoint(world, ["automation.run.completed"])
    await make_automation(world.engine, workspace_id=world.wid, account_id=world.account_id)
    dm = await world.dm(ref(), "link please")
    assert dm is not None
    assert await world.run("dm", dm) is Outcome.FIRED
    [reply] = await world.rows("SELECT id FROM messages WHERE direction = 'outbound'")
    assert await world.send(reply["id"]) is Delivery.SENT
    [event] = await pending(world)
    assert event["payload"]["data"]["run"] == {
        "id": event["payload"]["data"]["run"]["id"],
        "result": "sent",
        "trigger": "dm",
    }


async def test_tagging_raises_contact_tagged_for_real_changes(world: World) -> None:
    from socialhood.services.contacts import change_tags

    await add_endpoint(world, ["contact.tagged", "contact.updated"])
    assert await world.dm(ref(), "hi") is not None
    [contact] = await world.rows("SELECT id FROM contacts")
    async with world.engine.begin() as conn:
        tag = (
            await conn.execute(
                text("INSERT INTO tags (workspace_id, name) VALUES (:w, 'VIP') RETURNING id"),
                {"w": world.wid},
            )
        ).scalar_one()
    with workspace_scope(world.wid):
        async with world.maker() as session:
            await change_tags(session, [contact["id"]], add=[tag], remove=[], user_id=None)
            await change_tags(session, [contact["id"]], add=[tag], remove=[], user_id=None)  # no-op
            await change_tags(session, [contact["id"]], add=[], remove=[tag], user_id=None)
            await session.commit()
    found = await pending(world)
    assert [
        (d["payload"]["data"]["action"], d["payload"]["data"]["tag"]["name"]) for d in found
    ] == [
        ("added", "VIP"),
        ("removed", "VIP"),
    ]
