"""GR-25: workspace API keys and the public API. Done when a key with read scope lists contacts
and gets 403 on a write. Plus key management and roles, authentication, the per-key rate limit,
plan gating (PD-6), each public endpoint, and that a key never reaches another workspace."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.api.public_openapi import public_openapi
from socialhood.security.ratelimit import LIMITS, window_key
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import make_run, set_plan
from tests.support.automations import make_automation
from tests.support.inbox import make_account, make_thread
from tests.support.sending import (
    Setup,
    clean_outbox,
    outbound_rows,
    send_jobs,
    workspace_with_thread,
)

ALL_SCOPES = [
    "contacts:read",
    "contacts:write",
    "tags:read",
    "tags:write",
    "conversations:read",
    "messages:send",
    "automations:read",
    "webhooks:subscribe",
]


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
async def setup(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    """A Pro workspace (the public API is Pro and Max, PD-6) with one conversation."""
    made = await workspace_with_thread(client, clerk, engine)
    await set_plan(engine, made.wid, "pro")
    return made


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def make_key(
    client: httpx.AsyncClient,
    setup: Setup,
    *scopes: str,
    name: str = "Zapier",
) -> tuple[str, dict[str, Any]]:
    """Make a key through the app's API; returns the key and the create response."""
    response = await client.post(
        f"/v1/w/{setup.wid}/api-keys",
        json={"name": name, "scopes": list(scopes) or ["contacts:read"]},
        headers=setup.headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["key"], body


async def second_workspace(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    other = await workspace_with_thread(client, clerk, engine, email="other@example.com")
    await set_plan(engine, other.wid, "pro")
    return other


# ---------------------------------------------------------------- managing keys


async def test_a_key_is_shown_once_and_only_its_hash_is_kept(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    key, made = await make_key(client, setup, "contacts:read", name="Sheets sync")
    assert key.startswith("shk_")
    assert made["key_prefix"] == key[:12]
    assert made["scopes"] == ["contacts:read"]
    assert made["last_used_at"] is None
    assert made["revoked_at"] is None

    listed = (await client.get(f"/v1/w/{setup.wid}/api-keys", headers=setup.headers)).json()
    assert [k["id"] for k in listed["items"]] == [made["id"]]
    assert "key" not in listed["items"][0]  # shown once
    assert key not in str(listed)
    assert {s["scope"] for s in listed["scopes"]} == set(ALL_SCOPES)
    assert listed["active_limit"] == 20

    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT key_hash, key_prefix FROM api_keys"))).one()
    assert row.key_hash == hashlib.sha256(key.encode()).hexdigest()
    assert key not in (row.key_hash, row.key_prefix)


async def test_the_public_api_is_pro_and_max_only(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    await set_plan(engine, setup.wid, "free")
    refused = await client.post(
        f"/v1/w/{setup.wid}/api-keys",
        json={"name": "Zapier", "scopes": ["contacts:read"]},
        headers=setup.headers,
    )
    assert refused.status_code == 402, refused.text
    assert refused.json()["code"] == "entitlement_required"
    assert refused.json()["entitlement"] == "public_api"
    # Listing stays open, so a workspace that downgraded can still see and revoke its keys.
    assert (
        await client.get(f"/v1/w/{setup.wid}/api-keys", headers=setup.headers)
    ).status_code == 200
    # Outbound webhooks stay on every plan (PD-6).
    hook = await client.post(
        f"/v1/w/{setup.wid}/webhook-endpoints",
        json={"url": "https://hooks.example.com/in", "events": ["lead.captured"]},
        headers=setup.headers,
    )
    assert hook.status_code == 201, hook.text

    await set_plan(engine, setup.wid, "max")
    assert (
        await client.post(
            f"/v1/w/{setup.wid}/api-keys",
            json={"name": "Zapier", "scopes": ["contacts:read"]},
            headers=setup.headers,
        )
    ).status_code == 201


async def test_a_key_needs_a_name_and_known_scopes(client: httpx.AsyncClient, setup: Setup) -> None:
    for body in (
        {"name": "", "scopes": ["contacts:read"]},
        {"name": "Zapier", "scopes": []},
        {"name": "Zapier", "scopes": ["contacts:delete"]},
        {"name": "x" * 81, "scopes": ["contacts:read"]},
    ):
        response = await client.post(
            f"/v1/w/{setup.wid}/api-keys", json=body, headers=setup.headers
        )
        assert response.status_code == 422, body


async def test_only_owners_and_admins_manage_keys(
    client: httpx.AsyncClient, clerk: Clerk, setup: Setup, engine: AsyncEngine
) -> None:
    _, key = await make_key(client, setup, "contacts:read")
    member_id, member = await sign_in(client, clerk, email="agent@example.com")
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (:w, :u, :r)"),
            {"w": setup.wid, "u": member["id"], "r": "agent"},
        )
    headers = clerk.headers(member_id)
    base = f"/v1/w/{setup.wid}/api-keys"
    assert (await client.get(base, headers=headers)).status_code == 403
    assert (
        await client.post(base, json={"name": "A", "scopes": ["contacts:read"]}, headers=headers)
    ).status_code == 403
    assert (await client.delete(f"{base}/{key['id']}", headers=headers)).status_code == 403


async def test_at_most_twenty_active_keys(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    for i in range(20):
        await make_key(client, setup, "contacts:read", name=f"Key {i}")
    over = await client.post(
        f"/v1/w/{setup.wid}/api-keys",
        json={"name": "One more", "scopes": ["contacts:read"]},
        headers=setup.headers,
    )
    assert over.status_code == 409, over.text
    # A revoked key frees its place.
    first = (await client.get(f"/v1/w/{setup.wid}/api-keys", headers=setup.headers)).json()
    await client.delete(
        f"/v1/w/{setup.wid}/api-keys/{first['items'][0]['id']}", headers=setup.headers
    )
    again = await client.post(
        f"/v1/w/{setup.wid}/api-keys",
        json={"name": "One more", "scopes": ["contacts:read"]},
        headers=setup.headers,
    )
    assert again.status_code == 201, again.text


async def test_revoking_stops_the_key_at_once(client: httpx.AsyncClient, setup: Setup) -> None:
    key, made = await make_key(client, setup, "contacts:read")
    assert (await client.get("/public/v1/contacts", headers=bearer(key))).status_code == 200

    revoked = await client.delete(f"/v1/w/{setup.wid}/api-keys/{made['id']}", headers=setup.headers)
    assert revoked.status_code == 200, revoked.text
    stamp = revoked.json()["revoked_at"]
    assert stamp is not None

    refused = await client.get("/public/v1/contacts", headers=bearer(key))
    assert refused.status_code == 401
    assert refused.json()["code"] == "unauthorized"
    # Again: nothing changes.
    again = await client.delete(f"/v1/w/{setup.wid}/api-keys/{made['id']}", headers=setup.headers)
    assert again.json()["revoked_at"] == stamp
    missing = await client.delete(
        f"/v1/w/{setup.wid}/api-keys/{uuid.uuid4()}", headers=setup.headers
    )
    assert missing.status_code == 404


# ---------------------------------------------------------------- authentication


async def test_a_missing_or_wrong_key_is_401(client: httpx.AsyncClient, setup: Setup) -> None:
    for headers in (
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer "},
        bearer("not-a-key"),
        bearer("shk_" + "a" * 43),
    ):
        response = await client.get("/public/v1/contacts", headers=headers)
        assert response.status_code == 401, headers
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "unauthorized"


async def test_a_session_token_is_not_an_api_key(client: httpx.AsyncClient, setup: Setup) -> None:
    response = await client.get("/public/v1/contacts", headers=setup.headers)
    assert response.status_code == 401


async def test_every_public_route_needs_a_key(app: FastAPI, client: httpx.AsyncClient) -> None:
    schema = public_openapi(app)
    calls = 0
    for path, operations in schema["paths"].items():
        url = path
        for name in ("contact_id", "conversation_id", "hook_id"):
            url = url.replace("{" + name + "}", str(uuid.uuid4()))
        for method in operations:
            response = await client.request(method, url, json={})
            assert response.status_code == 401, f"{method.upper()} {path}"
            calls += 1
    assert calls >= 13


async def test_the_document_is_public_and_lists_only_the_public_api(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/public/v1/openapi.json")
    assert response.status_code == 200, response.text
    document = response.json()
    assert document["info"]["title"] == "Social Hood public API"
    assert "/public/v1/contacts" in document["paths"]
    assert not [p for p in document["paths"] if p.startswith("/v1/")]
    assert document["components"]["securitySchemes"]["ApiKey"]["scheme"] == "bearer"


async def test_any_valid_key_says_whose_it_is(client: httpx.AsyncClient, setup: Setup) -> None:
    key, made = await make_key(client, setup, "tags:read", name="Zapier")
    me = await client.get("/public/v1/me", headers=bearer(key))
    assert me.status_code == 200, me.text
    assert me.json()["key_id"] == made["id"]
    assert me.json()["workspace_id"] == setup.wid
    assert me.json()["scopes"] == ["tags:read"]
    assert key not in me.text
    assert (await client.get("/public/v1/me")).status_code == 401


async def test_a_key_records_when_it_was_last_used(client: httpx.AsyncClient, setup: Setup) -> None:
    key, made = await make_key(client, setup, "contacts:read")
    assert (await client.get("/public/v1/contacts", headers=bearer(key))).status_code == 200
    listed = (await client.get(f"/v1/w/{setup.wid}/api-keys", headers=setup.headers)).json()
    stamp = next(k for k in listed["items"] if k["id"] == made["id"])["last_used_at"]
    assert stamp is not None
    assert datetime.fromisoformat(stamp) > datetime.now(UTC) - timedelta(minutes=1)


async def test_a_workspace_that_leaves_the_plan_stops_the_key(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    key, _ = await make_key(client, setup, "contacts:read")
    await set_plan(engine, setup.wid, "free")
    refused = await client.get("/public/v1/contacts", headers=bearer(key))
    assert refused.status_code == 402, refused.text
    assert refused.json()["entitlement"] == "public_api"
    await set_plan(engine, setup.wid, "pro")
    assert (await client.get("/public/v1/contacts", headers=bearer(key))).status_code == 200


# ---------------------------------------------------------------- the rate limit


async def test_each_key_has_its_own_rate_limit(
    client: httpx.AsyncClient, setup: Setup, redis: Redis
) -> None:
    key, made = await make_key(client, setup, "contacts:read", name="Busy")
    other, _ = await make_key(client, setup, "contacts:read", name="Quiet")
    limit = LIMITS["api_key"]
    now_ms = int(time.time() * 1000)
    await redis.zadd(
        window_key(limit, made["id"]), {f"fill-{i}": now_ms for i in range(limit.max_requests)}
    )
    await redis.expire(window_key(limit, made["id"]), limit.window_s)

    limited = await client.get("/public/v1/contacts", headers=bearer(key))
    assert limited.status_code == 429, limited.text
    assert limited.json()["code"] == "rate_limited"
    assert 1 <= int(limited.headers["retry-after"]) <= 60
    assert (await client.get("/public/v1/contacts", headers=bearer(other))).status_code == 200


# ---------------------------------------------------------------- scopes: the done-when


async def test_a_read_key_lists_contacts_and_is_forbidden_to_write(
    client: httpx.AsyncClient, setup: Setup
) -> None:
    key, _ = await make_key(client, setup, "contacts:read")
    listed = await client.get("/public/v1/contacts", headers=bearer(key))
    assert listed.status_code == 200, listed.text
    [contact] = listed.json()["items"]
    assert contact["id"] == str(setup.thread.contact_id)

    write = await client.patch(
        f"/public/v1/contacts/{contact['id']}",
        json={"email": "priya@example.com"},
        headers=bearer(key),
    )
    assert write.status_code == 403, write.text
    assert write.json()["code"] == "forbidden"
    assert "contacts:write" in write.json()["detail"]
    created = await client.post(
        "/public/v1/contacts",
        json={"account_id": setup.account_id, "phone": "+919876543210"},
        headers=bearer(key),
    )
    assert created.status_code == 403
    tagged = await client.post(
        f"/public/v1/contacts/{contact['id']}/tags", json={"add": []}, headers=bearer(key)
    )
    assert tagged.status_code == 403
    assert "tags:write" in tagged.json()["detail"]


async def test_each_scope_opens_only_its_routes(
    client: httpx.AsyncClient, setup: Setup, queue: None
) -> None:
    conversation = f"/public/v1/conversations/{setup.conversation_id}"
    checks = [
        ("conversations:read", "GET", "/public/v1/conversations", None),
        ("conversations:read", "GET", conversation, None),
        ("conversations:read", "GET", f"{conversation}/messages", None),
        ("messages:send", "POST", f"{conversation}/messages", {"text": "Hello"}),
        ("automations:read", "GET", "/public/v1/automation-runs", None),
        ("tags:read", "GET", "/public/v1/tags", None),
        ("contacts:read", "GET", "/public/v1/accounts", None),
        ("contacts:read", "GET", "/public/v1/contact-fields", None),
    ]
    keys = {scope: (await make_key(client, setup, scope, name=scope))[0] for scope in ALL_SCOPES}
    for needed, method, path, body in checks:
        for scope, key in keys.items():
            response = await client.request(method, path, json=body, headers=bearer(key))
            if scope == needed:
                assert response.status_code in (200, 202), f"{scope} {method} {path}"
            else:
                assert response.status_code == 403, f"{scope} {method} {path}: {response.text}"


# ---------------------------------------------------------------- contacts and tags


async def test_contacts_list_filters_and_sorts_by_created(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    second = await make_thread(
        engine,
        workspace_id=setup.wid,
        account_id=setup.account_id,
        display_name="Meera Rao",
        username="meera.rao",
    )
    key, _ = await make_key(client, setup, "contacts:read")
    newest = await client.get("/public/v1/contacts?sort=created&limit=1", headers=bearer(key))
    assert [c["id"] for c in newest.json()["items"]] == [str(second.contact_id)]
    assert newest.json()["next_cursor"]
    older = await client.get(
        f"/public/v1/contacts?sort=created&limit=1&cursor={newest.json()['next_cursor']}",
        headers=bearer(key),
    )
    assert [c["id"] for c in older.json()["items"]] == [str(setup.thread.contact_id)]
    assert older.json()["next_cursor"] is None

    found = await client.get("/public/v1/contacts?q=meera", headers=bearer(key))
    assert [c["id"] for c in found.json()["items"]] == [str(second.contact_id)]
    assert (
        await client.get("/public/v1/contacts?limit=1000", headers=bearer(key))
    ).status_code == 422


async def test_get_and_update_a_contact_including_custom_fields(
    client: httpx.AsyncClient, setup: Setup
) -> None:
    field = await client.post(
        f"/v1/w/{setup.wid}/contact-fields",
        json={"key": "city", "label": "City"},
        headers=setup.headers,
    )
    assert field.status_code == 201, field.text
    key, _ = await make_key(client, setup, "contacts:read", "contacts:write")
    contact_id = setup.thread.contact_id

    fields = await client.get("/public/v1/contact-fields", headers=bearer(key))
    assert [f["key"] for f in fields.json()["items"]] == ["city"]
    updated = await client.patch(
        f"/public/v1/contacts/{contact_id}",
        json={"email": "Priya@Example.com", "fields": {"city": "Pune"}},
        headers=bearer(key),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["email"] == "priya@example.com"
    assert updated.json()["fields"] == {"city": "Pune"}
    again = await client.get(f"/public/v1/contacts/{contact_id}", headers=bearer(key))
    assert again.json()["fields"]["city"] == "Pune"

    bad = await client.patch(
        f"/public/v1/contacts/{contact_id}",
        json={"email": "nope", "fields": {"colour": "red"}},
        headers=bearer(key),
    )
    assert bad.status_code == 422
    assert {e["field"] for e in bad.json()["errors"]} == {"email", "fields.colour"}
    assert (
        await client.get(f"/public/v1/contacts/{uuid.uuid4()}", headers=bearer(key))
    ).status_code == 404


async def test_create_a_contact_on_a_whatsapp_account(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    whatsapp = await make_account(engine, setup.wid, platform="whatsapp", username="shop")
    key, _ = await make_key(client, setup, "contacts:read", "contacts:write")
    body = {"account_id": str(whatsapp), "phone": "+91 98765 43210", "name": "Asha Nair"}
    made = await client.post("/public/v1/contacts", json=body, headers=bearer(key))
    assert made.status_code == 201, made.text
    assert made.json()["phone"] == "+919876543210"
    assert made.json()["platform"] == "whatsapp"
    assert made.json()["name"] == "Asha Nair"

    duplicate = await client.post("/public/v1/contacts", json=body, headers=bearer(key))
    assert duplicate.status_code == 409
    instagram = await client.post(
        "/public/v1/contacts",
        json={"account_id": setup.account_id, "phone": "+919876543211"},
        headers=bearer(key),
    )
    assert instagram.status_code == 422
    assert instagram.json()["errors"][0]["field"] == "account_id"
    no_country = await client.post(
        "/public/v1/contacts",
        json={"account_id": str(whatsapp), "phone": "12345678"},
        headers=bearer(key),
    )
    assert no_country.status_code == 422
    assert no_country.json()["errors"][0]["field"] == "phone"
    unknown = await client.post(
        "/public/v1/contacts",
        json={"account_id": str(uuid.uuid4()), "phone": "+919876543212"},
        headers=bearer(key),
    )
    assert unknown.status_code == 404
    accounts = await client.get("/public/v1/accounts", headers=bearer(key))
    assert {a["id"] for a in accounts.json()["items"]} == {setup.account_id, str(whatsapp)}


async def test_add_and_remove_tags(client: httpx.AsyncClient, setup: Setup) -> None:
    tag = (
        await client.post(f"/v1/w/{setup.wid}/tags", json={"name": "VIP"}, headers=setup.headers)
    ).json()
    key, _ = await make_key(client, setup, "tags:read", "tags:write", "contacts:read")
    tags = await client.get("/public/v1/tags", headers=bearer(key))
    assert [t["name"] for t in tags.json()["items"]] == ["VIP"]

    contact = f"/public/v1/contacts/{setup.thread.contact_id}"
    added = await client.post(f"{contact}/tags", json={"add": [tag["id"]]}, headers=bearer(key))
    assert added.status_code == 200, added.text
    assert [t["name"] for t in added.json()["tags"]] == ["VIP"]
    filtered = await client.get(f"/public/v1/contacts?tag_id={tag['id']}", headers=bearer(key))
    assert [c["id"] for c in filtered.json()["items"]] == [str(setup.thread.contact_id)]
    removed = await client.post(
        f"{contact}/tags", json={"remove": [tag["id"]]}, headers=bearer(key)
    )
    assert removed.json()["tags"] == []
    unknown = await client.post(
        f"{contact}/tags", json={"add": [str(uuid.uuid4())]}, headers=bearer(key)
    )
    assert unknown.status_code == 404


# ---------------------------------------------------------------- conversations and messages


async def test_conversations_and_messages_are_readable(
    client: httpx.AsyncClient, setup: Setup
) -> None:
    key, _ = await make_key(client, setup, "conversations:read")
    listed = await client.get("/public/v1/conversations", headers=bearer(key))
    assert [c["id"] for c in listed.json()["items"]] == [setup.conversation_id]

    one = await client.get(f"/public/v1/conversations/{setup.conversation_id}", headers=bearer(key))
    assert one.status_code == 200, one.text
    assert one.json()["reply_window"]["state"] == "open"
    assert one.json()["contact"]["id"] == str(setup.thread.contact_id)
    assert "latest_analysis" not in one.json()  # the app's AI detail stays in the app

    messages = await client.get(
        f"/public/v1/conversations/{setup.conversation_id}/messages", headers=bearer(key)
    )
    assert [m["id"] for m in messages.json()["items"]] == [str(setup.thread.message_ids[0])]
    missing = await client.get(f"/public/v1/conversations/{uuid.uuid4()}", headers=bearer(key))
    assert missing.status_code == 404


async def test_a_message_is_sent_inside_the_window(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    key, _ = await make_key(client, setup, "messages:send")
    url = f"/public/v1/conversations/{setup.conversation_id}/messages"
    sent = await client.post(url, json={"text": "Yes, we ship to Pune"}, headers=bearer(key))
    assert sent.status_code == 202, sent.text
    message = sent.json()
    assert (message["status"], message["direction"], message["source"]) == (
        "queued",
        "outbound",
        "human",
    )
    assert message["sent_by"] is None  # sent by a key, not a member

    [row] = await outbound_rows(engine, setup)
    assert row["sent_by_user_id"] is None
    assert row["text"] == "Yes, we ship to Pune"
    assert len(await send_jobs()) == 1


async def test_the_same_idempotency_key_sends_once(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    key, _ = await make_key(client, setup, "messages:send")
    url = f"/public/v1/conversations/{setup.conversation_id}/messages"
    headers = {**bearer(key), "Idempotency-Key": "zap-run-0001"}
    first = await client.post(url, json={"text": "Hello"}, headers=headers)
    second = await client.post(url, json={"text": "Hello"}, headers=headers)
    assert first.status_code == second.status_code == 202
    assert second.json() == first.json()
    assert len(await outbound_rows(engine, setup)) == 1
    different = await client.post(url, json={"text": "Another"}, headers=headers)
    assert different.status_code == 409
    assert different.json()["code"] == "idempotency_conflict"


async def test_a_message_outside_the_window_is_refused_like_the_app_does(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    old = await make_thread(
        engine,
        workspace_id=setup.wid,
        account_id=setup.account_id,
        display_name="Late Lata",
        last_inbound_at=datetime.now(UTC) - timedelta(hours=30),
    )
    key, _ = await make_key(client, setup, "messages:send")
    url = f"/public/v1/conversations/{old.conversation_id}/messages"
    refused = await client.post(url, json={"text": "Still there?"}, headers=bearer(key))
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "reply_window_closed"
    assert await send_jobs() == []
    empty = await client.post(url, json={"text": ""}, headers=bearer(key))
    assert empty.status_code == 422


async def test_sending_counts_against_the_workspaces_send_limit(
    client: httpx.AsyncClient, setup: Setup, redis: Redis, queue: None
) -> None:
    key, _ = await make_key(client, setup, "messages:send")
    limit = LIMITS["sends"]
    now_ms = int(time.time() * 1000)
    await redis.zadd(
        window_key(limit, setup.wid), {f"fill-{i}": now_ms for i in range(limit.max_requests)}
    )
    await redis.expire(window_key(limit, setup.wid), limit.window_s)
    limited = await client.post(
        f"/public/v1/conversations/{setup.conversation_id}/messages",
        json={"text": "Hello"},
        headers=bearer(key),
    )
    assert limited.status_code == 429


# ---------------------------------------------------------------- automation runs


async def test_automation_runs_are_listed_newest_first(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    first = await make_automation(engine, workspace_id=setup.wid, account_id=setup.account_id)
    second = await make_automation(
        engine, workspace_id=setup.wid, account_id=setup.account_id, name="Another"
    )
    now = datetime.now(UTC)
    old = await make_run(
        engine, workspace_id=setup.wid, automation_id=first, created_at=now - timedelta(hours=2)
    )
    new = await make_run(
        engine,
        workspace_id=setup.wid,
        automation_id=second,
        created_at=now - timedelta(hours=1),
        result="failed",
    )
    key, _ = await make_key(client, setup, "automations:read")
    runs = await client.get("/public/v1/automation-runs", headers=bearer(key))
    assert [r["id"] for r in runs.json()["items"]] == [str(new), str(old)]
    one = await client.get(f"/public/v1/automation-runs?automation_id={first}", headers=bearer(key))
    assert [r["id"] for r in one.json()["items"]] == [str(old)]
    failed = await client.get("/public/v1/automation-runs?result=failed", headers=bearer(key))
    assert [r["id"] for r in failed.json()["items"]] == [str(new)]


# ---------------------------------------------------------------- tenancy


async def test_a_key_never_reaches_another_workspace(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, setup: Setup
) -> None:
    other = await second_workspace(client, clerk, engine)
    tag_b = (
        await client.post(f"/v1/w/{other.wid}/tags", json={"name": "B only"}, headers=other.headers)
    ).json()
    automation_b = await make_automation(
        engine, workspace_id=other.wid, account_id=other.account_id
    )
    run_b = await make_run(
        engine, workspace_id=other.wid, automation_id=automation_b, created_at=datetime.now(UTC)
    )
    key_a, _ = await make_key(client, setup, *ALL_SCOPES)
    auth = bearer(key_a)

    contacts = await client.get("/public/v1/contacts", headers=auth)
    assert [c["id"] for c in contacts.json()["items"]] == [str(setup.thread.contact_id)]
    conversations = await client.get("/public/v1/conversations", headers=auth)
    assert [c["id"] for c in conversations.json()["items"]] == [setup.conversation_id]
    assert (await client.get("/public/v1/tags", headers=auth)).json()["items"] == []
    runs = await client.get("/public/v1/automation-runs", headers=auth)
    assert runs.json()["items"] == []
    accounts = await client.get("/public/v1/accounts", headers=auth)
    assert [a["id"] for a in accounts.json()["items"]] == [setup.account_id]

    b_contact, b_conversation = other.thread.contact_id, other.conversation_id
    for method, path, body in (
        ("GET", f"/public/v1/contacts/{b_contact}", None),
        ("PATCH", f"/public/v1/contacts/{b_contact}", {"email": "taken@example.com"}),
        ("POST", f"/public/v1/contacts/{b_contact}/tags", {"add": []}),
        ("GET", f"/public/v1/conversations/{b_conversation}", None),
        ("GET", f"/public/v1/conversations/{b_conversation}/messages", None),
        ("POST", f"/public/v1/conversations/{b_conversation}/messages", {"text": "Into B"}),
        (
            "POST",
            f"/public/v1/contacts/{setup.thread.contact_id}/tags",
            {"add": [tag_b["id"]]},
        ),
        ("POST", "/public/v1/contacts", {"account_id": other.account_id, "phone": "+919876543299"}),
    ):
        response = await client.request(method, path, json=body, headers=auth)
        assert response.status_code == 404, f"{method} {path}: {response.text}"
        assert response.json()["code"] == "not_found"
    by_run = await client.get(
        f"/public/v1/automation-runs?automation_id={automation_b}", headers=auth
    )
    assert by_run.json()["items"] == []
    assert str(run_b) not in by_run.text

    async with engine.connect() as conn:  # nothing was written to B
        sent = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM messages"
                    " WHERE conversation_id = :c AND direction = 'outbound'"
                ),
                {"c": b_conversation},
            )
        ).scalar_one()
        email = (
            await conn.execute(text("SELECT email FROM contacts WHERE id = :c"), {"c": b_contact})
        ).scalar_one()
    assert sent == 0
    assert email is None


async def test_a_key_only_authenticates_its_own_workspace_even_when_both_have_keys(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, setup: Setup
) -> None:
    other = await second_workspace(client, clerk, engine)
    key_a, _ = await make_key(client, setup, "contacts:read")
    key_b, _ = await make_key(client, other, "contacts:read")
    seen_a = await client.get("/public/v1/contacts", headers=bearer(key_a))
    seen_b = await client.get("/public/v1/contacts", headers=bearer(key_b))
    assert [c["id"] for c in seen_a.json()["items"]] == [str(setup.thread.contact_id)]
    assert [c["id"] for c in seen_b.json()["items"]] == [str(other.thread.contact_id)]
    # B's owner cannot see or revoke A's keys through the app either.
    keys_a = (await client.get(f"/v1/w/{setup.wid}/api-keys", headers=setup.headers)).json()
    revoke = await client.delete(
        f"/v1/w/{other.wid}/api-keys/{keys_a['items'][0]['id']}", headers=other.headers
    )
    assert revoke.status_code == 404
