"""GR-26: Zapier triggers over REST hooks. A subscription is a GR-04 webhook endpoint made on behalf
of an API key, so delivery, signing, retries and the delivery log are shared. Done when a captured
lead is delivered, signed, to the address a key subscribed (the private Zap that moves leads to a
Google Sheet is the owner's manual test, integrations/zapier/README.md)."""

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

from socialhood.db.tenancy import workspace_scope
from socialhood.schemas.public_hooks import HookSubscribe
from socialhood.security.signatures import verify_standard_webhook
from socialhood.services import api_hooks
from socialhood.settings import Settings
from tests.integration.test_outbound_webhooks import Receiver, deliver, pending, ref
from tests.support.api import Clerk
from tests.support.automation_api import set_plan
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import Setup, clean_outbox, workspace_with_thread

TARGET = "https://hooks.zapier.com/hooks/standard/1/abc/"
TRIGGERS = {
    "new_contact": "contact.created",
    "lead_captured": "lead.captured",
    "tag_added": "contact.tagged",
    "new_message": "message.received",
    "run_completed": "automation.run.completed",
}


@pytest.fixture
async def setup(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    made = await workspace_with_thread(client, clerk, engine)
    await set_plan(engine, made.wid, "pro")
    return made


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def make_key(client: httpx.AsyncClient, setup: Setup, *scopes: str) -> tuple[str, str]:
    response = await client.post(
        f"/v1/w/{setup.wid}/api-keys",
        json={"name": "Zapier", "scopes": list(scopes) or ["webhooks:subscribe"]},
        headers=setup.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["key"], response.json()["id"]


async def subscribe(
    client: httpx.AsyncClient, key: str, trigger: str = "new_contact", url: str = TARGET
) -> dict[str, Any]:
    response = await client.post(
        "/public/v1/hooks", json={"trigger": trigger, "target_url": url}, headers=bearer(key)
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


# ---------------------------------------------------------------- subscribe and unsubscribe


async def test_a_trigger_is_subscribed_and_unsubscribed(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    key, key_id = await make_key(client, setup, "webhooks:subscribe")
    for trigger, event in TRIGGERS.items():
        made = await subscribe(client, key, trigger)
        assert made["trigger"] == trigger
        assert made["status"] == "active"
        assert made["signing_secret"].startswith("whsec_")  # shown once
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT events, api_key_id, url FROM webhook_endpoints WHERE id = :i"),
                    {"i": made["id"]},
                )
            ).one()
        assert row.events == [event]
        assert str(row.api_key_id) == key_id
        assert row.url == TARGET

    listed = await client.get("/public/v1/hooks", headers=bearer(key))
    assert [h["trigger"] for h in listed.json()["items"]] == list(TRIGGERS)
    assert "signing_secret" not in listed.text

    first = listed.json()["items"][0]["id"]
    gone = await client.delete(f"/public/v1/hooks/{first}", headers=bearer(key))
    assert gone.status_code == 204
    again = await client.delete(f"/public/v1/hooks/{first}", headers=bearer(key))
    assert again.status_code == 404
    assert len((await client.get("/public/v1/hooks", headers=bearer(key))).json()["items"]) == 4


async def test_a_hook_address_follows_the_endpoint_rules(
    client: httpx.AsyncClient, setup: Setup
) -> None:
    key, _ = await make_key(client, setup, "webhooks:subscribe")
    for url in (
        "http://hooks.zapier.com/x",
        "https://user:pass@hooks.zapier.com/x",
        "ftp://x.test",
    ):
        response = await client.post(
            "/public/v1/hooks",
            json={"trigger": "new_contact", "target_url": url},
            headers=bearer(key),
        )
        assert response.status_code == 422, url
        assert response.json()["errors"][0]["field"] == "url"
    unknown = await client.post(
        "/public/v1/hooks",
        json={"trigger": "contact.created", "target_url": TARGET},
        headers=bearer(key),
    )
    assert unknown.status_code == 422


async def test_subscribing_needs_the_scope(client: httpx.AsyncClient, setup: Setup) -> None:
    key, _ = await make_key(client, setup, "contacts:read")
    refused = await client.post(
        "/public/v1/hooks",
        json={"trigger": "new_contact", "target_url": TARGET},
        headers=bearer(key),
    )
    assert refused.status_code == 403
    assert "webhooks:subscribe" in refused.json()["detail"]
    assert (await client.get("/public/v1/hooks", headers=bearer(key))).status_code == 403
    gone = await client.delete(f"/public/v1/hooks/{uuid.uuid4()}", headers=bearer(key))
    assert gone.status_code == 403


async def test_hooks_take_no_slot_from_the_plans_endpoints(
    client: httpx.AsyncClient, setup: Setup
) -> None:
    key, _ = await make_key(client, setup, "webhooks:subscribe")
    for _ in range(6):  # Pro has 5 endpoints
        await subscribe(client, key)
    own = await client.post(
        f"/v1/w/{setup.wid}/webhook-endpoints",
        json={"url": TARGET, "events": ["lead.captured"]},
        headers=setup.headers,
    )
    assert own.status_code == 201, own.text
    listed = (
        await client.get(f"/v1/w/{setup.wid}/webhook-endpoints", headers=setup.headers)
    ).json()
    assert listed["limit"] == 5
    assert len(listed["items"]) == 7  # the hooks show beside it, named for their trigger
    named = {i["description"] for i in listed["items"] if i["id"] != own.json()["id"]}
    assert named == {"Zapier: new contact"}


async def test_a_hook_belongs_to_its_workspace(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, setup: Setup
) -> None:
    other = await workspace_with_thread(client, clerk, engine, email="other@example.com")
    await set_plan(engine, other.wid, "pro")
    key_a, _ = await make_key(client, setup, "webhooks:subscribe")
    key_b, _ = await make_key(client, other, "webhooks:subscribe")
    mine = await subscribe(client, key_a)
    theirs = await subscribe(client, key_b)
    seen_a = (await client.get("/public/v1/hooks", headers=bearer(key_a))).json()["items"]
    assert [h["id"] for h in seen_a] == [mine["id"]]
    refused = await client.delete(f"/public/v1/hooks/{theirs['id']}", headers=bearer(key_a))
    assert refused.status_code == 404
    assert len((await client.get("/public/v1/hooks", headers=bearer(key_b))).json()["items"]) == 1


async def test_unsubscribing_never_removes_a_members_own_endpoint(
    client: httpx.AsyncClient, setup: Setup
) -> None:
    key, _ = await make_key(client, setup, "webhooks:subscribe")
    own = await client.post(
        f"/v1/w/{setup.wid}/webhook-endpoints",
        json={"url": TARGET, "events": ["lead.captured"]},
        headers=setup.headers,
    )
    assert own.status_code == 201
    gone = await client.delete(f"/public/v1/hooks/{own.json()['id']}", headers=bearer(key))
    assert gone.status_code == 404
    still = await client.get(
        f"/v1/w/{setup.wid}/webhook-endpoints/{own.json()['id']}", headers=setup.headers
    )
    assert still.status_code == 200


async def test_revoking_a_key_removes_its_hooks_and_only_its_hooks(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    key, key_id = await make_key(client, setup, "webhooks:subscribe")
    other_key, _ = await make_key(client, setup, "webhooks:subscribe")
    await subscribe(client, key)
    await subscribe(client, other_key, "tag_added")
    revoked = await client.delete(f"/v1/w/{setup.wid}/api-keys/{key_id}", headers=setup.headers)
    assert revoked.status_code == 200
    async with engine.connect() as conn:
        left = (await conn.execute(text("SELECT events FROM webhook_endpoints"))).all()
    assert [r.events for r in left] == [["contact.tagged"]]


# ---------------------------------------------------------------- delivery (GR-04's machinery)


async def on_plan(world: World, plan: str) -> None:
    """The bare test workspace has no subscription row until it is given one."""
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO subscriptions (workspace_id, plan, status, billing_anchor_day)"
                " VALUES (:w, :p, 'active', 5)"
                " ON CONFLICT (workspace_id) DO UPDATE SET plan = :p"
            ),
            {"w": world.wid, "p": plan},
        )


@pytest.fixture
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


async def hook_for(world: World, trigger: str) -> tuple[uuid.UUID, str]:
    """A key (a row) and a hook it subscribed, as the public route does; returns (hook, secret)."""
    async with world.engine.begin() as conn:
        key_id = (
            await conn.execute(
                text(
                    "INSERT INTO api_keys (workspace_id, name, key_prefix, key_hash, scopes)"
                    " VALUES (:w, 'Zapier', 'shk_zzzzzzzz', :h, ARRAY['webhooks:subscribe'])"
                    " RETURNING id"
                ),
                {"w": world.wid, "h": uuid.uuid4().hex * 2},
            )
        ).scalar_one()
    with workspace_scope(world.wid):
        async with world.maker() as session:
            made = await api_hooks.subscribe(
                session,
                HookSubscribe(trigger=trigger, target_url=TARGET),  # type: ignore[arg-type]
                key_id=key_id,
                cipher=world.deps.cipher,
                allow_private=False,
            )
            await session.commit()
    return made.id, made.signing_secret


async def test_a_new_message_reaches_the_hook_signed_with_its_secret(world: World) -> None:
    await on_plan(world, "pro")
    _, secret = await hook_for(world, "new_message")
    assert await world.dm(ref(), "Is the hamper available?") is not None
    [message] = await pending(world)
    assert message["event_type"] == "message.received"

    receiver = Receiver(200)
    assert await deliver(world, message["id"], receiver) == "delivered"
    [(url, body, headers)] = receiver.requests
    assert url == TARGET
    assert verify_standard_webhook(body, headers, secret)
    event = json.loads(body)
    assert event["type"] == "message.received"
    assert event["data"]["message"]["text"] == "Is the hamper available?"
    # The delivery shows in the same log as any endpoint's.
    [row] = await world.rows("SELECT status, attempts FROM webhook_deliveries")
    assert (row["status"], row["attempts"]) == ("succeeded", 1)


async def test_hooks_get_only_the_events_of_their_trigger(world: World) -> None:
    await on_plan(world, "pro")
    await hook_for(world, "new_contact")
    assert await world.dm(ref(), "hello") is not None
    assert [d["event_type"] for d in await pending(world)] == ["contact.created"]


async def test_a_failing_hook_retries_like_any_endpoint(world: World) -> None:
    await on_plan(world, "pro")
    await hook_for(world, "new_contact")
    assert await world.dm(ref(), "hello") is not None
    [created] = await pending(world)
    assert await deliver(world, created["id"], Receiver(500)) == "retrying"
    [row] = await world.rows("SELECT status, attempts, error FROM webhook_deliveries")
    assert (row["status"], row["attempts"], row["error"]) == (
        "pending",
        1,
        "The endpoint answered 500.",
    )


async def test_hooks_stop_with_the_plan_and_come_back_with_it(world: World) -> None:
    await on_plan(world, "pro")
    await hook_for(world, "new_contact")

    await on_plan(world, "free")
    assert await world.dm(ref(), "first") is not None
    assert await pending(world) == []  # Free: no public API, so no hook deliveries

    await on_plan(world, "max")
    assert await world.dm(ref(), "second") is not None
    assert [d["event_type"] for d in await pending(world)] == ["contact.created"]


async def test_a_members_endpoint_still_gets_events_on_free(world: World) -> None:
    """PD-6: outbound webhooks stay on every plan; only the key's hooks need Pro or Max."""
    await on_plan(world, "pro")
    await hook_for(world, "new_contact")
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO webhook_endpoints (workspace_id, url, events, status, secret_enc,"
                " failing_deliveries) VALUES (:w, 'https://hooks.example.com/own',"
                " ARRAY['contact.created'], 'active', '\\x00'::bytea, 0)"
            ),
            {"w": world.wid},
        )
    await on_plan(world, "free")
    assert await world.dm(ref(), "hello") is not None
    [only] = await pending(world)
    [endpoint] = await world.rows(
        "SELECT url FROM webhook_endpoints WHERE id = :i", i=only["endpoint_id"]
    )
    assert endpoint["url"] == "https://hooks.example.com/own"


async def test_polling_lists_back_the_triggers(client: httpx.AsyncClient, setup: Setup) -> None:
    """Zapier tests a trigger by polling a list: each trigger has one (newest first)."""
    key, _ = await make_key(
        client,
        setup,
        "contacts:read",
        "conversations:read",
        "automations:read",
        "tags:read",
    )
    for path in (
        "/contacts?sort=created",  # new contact, and a lead captured with has_email=true
        "/contacts?sort=created&has_email=true",
        "/contacts?sort=created&tag_id=" + str(uuid.uuid4()),  # tag added (a tag's contacts)
        "/conversations",  # new message
        "/automation-runs",  # run completed
    ):
        response = await client.get("/public/v1" + path, headers=bearer(key))
        assert response.status_code == 200, f"{path}: {response.text}"
        assert "items" in response.json()
