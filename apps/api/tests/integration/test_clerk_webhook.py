"""T1.5: POST /webhooks/clerk (TR-AUTH-04, TR-WH-01…03) and processing (TR-WH-05)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from svix.webhooks import Webhook

from socialhood.billing.dodo import DodoError
from socialhood.billing.dodo_fake import FakeDodo
from socialhood.jobs.app import app as jobs_app
from socialhood.models.platform import WebhookStatus
from socialhood.services import workspace_deletion as deletion
from socialhood.services.webhook_processing import process_event
from tests.support.api import Clerk, sign_in
from tests.support.billing import PRO_PRODUCT, set_subscription
from tests.support.identity import WEBHOOK_SECRET, clerk_user


def signed(payload: dict[str, Any], *, msg_id: str | None = None) -> tuple[str, dict[str, str]]:
    body = json.dumps(payload)
    msg_id = msg_id or f"msg_{uuid.uuid4().hex}"
    now = datetime.now(UTC)
    signature = Webhook(WEBHOOK_SECRET).sign(msg_id, now, body)
    return body, {
        "svix-id": msg_id,
        "svix-timestamp": str(int(now.timestamp())),
        "svix-signature": signature,
        "content-type": "application/json",
    }


async def stored(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id, provider, dedupe_key, event_type, status FROM webhook_events")
        )
        return [dict(row._mapping) for row in rows]


async def test_a_valid_event_is_stored_once_and_enqueued(
    client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    body, headers = signed({"type": "user.updated", "data": clerk_user("user_x")})
    first = await client.post("/webhooks/clerk", content=body, headers=headers)
    again = await client.post("/webhooks/clerk", content=body, headers=headers)  # Clerk retry
    assert (first.status_code, again.status_code) == (200, 200)

    events = await stored(engine)
    assert len(events) == 1
    assert events[0]["provider"] == "clerk"
    assert events[0]["dedupe_key"] == f"clerk:{headers['svix-id']}"
    assert events[0]["event_type"] == "user.updated"
    jobs = await jobs_app.connector.execute_query_all_async(
        "SELECT task_name, args FROM procrastinate_jobs"
    )
    assert jobs == [
        {"task_name": "process_webhook_event", "args": {"webhook_event_id": str(events[0]["id"])}}
    ]


async def test_invalid_or_missing_signatures_store_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    body, headers = signed({"type": "user.updated", "data": clerk_user("user_x")})
    tampered = body.replace("Priya", "Mallory")
    bad = await client.post("/webhooks/clerk", content=tampered, headers=headers)
    missing = await client.post(
        "/webhooks/clerk", content=body, headers={"content-type": "application/json"}
    )
    assert (bad.status_code, missing.status_code) == (401, 401)
    assert bad.json()["code"] == "unauthorized"
    assert await stored(engine) == []


async def _deliver_and_process(
    client: httpx.AsyncClient, app: FastAPI, payload: dict[str, Any]
) -> WebhookStatus | None:
    body, headers = signed(payload)
    async with jobs_app.open_async():
        response = await client.post("/webhooks/clerk", content=body, headers=headers)
    assert response.status_code == 200
    async with app.state.engine.connect() as conn:
        event_id = await conn.scalar(
            text("SELECT id FROM webhook_events WHERE dedupe_key = :k"),
            {"k": f"clerk:{headers['svix-id']}"},
        )
    return await process_event(app.state.sessionmaker, event_id)


async def test_user_updated_refreshes_the_profile(
    client: httpx.AsyncClient, app: FastAPI, clerk: Clerk
) -> None:
    clerk_id, _ = await sign_in(client, clerk, first_name="Priya")
    changed = clerk_user(clerk_id, first_name="Priya", last_name="Sharma", email="new@example.com")
    status = await _deliver_and_process(client, app, {"type": "user.updated", "data": changed})
    assert status is WebhookStatus.PROCESSED
    me = (await client.get("/v1/me", headers=clerk.headers(clerk_id))).json()
    assert (me["name"], me["email"]) == ("Priya Sharma", "new@example.com")


async def test_unknown_users_and_events_are_ignored(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    status = await _deliver_and_process(
        client, app, {"type": "user.updated", "data": clerk_user("user_never_seen")}
    )
    assert status is WebhookStatus.IGNORED
    status = await _deliver_and_process(
        client, app, {"type": "session.created", "data": {"id": "sess_1"}}
    )
    assert status is WebhookStatus.IGNORED


@dataclass
class NoMedia:
    """The Cloudinary folder purge, faked (nothing was uploaded)."""

    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        return None


async def purge(app: FastAPI, dodo: FakeDodo, workspace_id: str) -> str:
    deps = deletion.PurgeDeps(
        sessionmaker=app.state.sessionmaker, redis=app.state.redis, dodo=dodo, media=NoMedia()
    )
    return (await deletion.purge_workspace(deps, uuid.UUID(workspace_id))).status


async def workspace_rows(engine: AsyncEngine) -> dict[str, tuple[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT id, status, owner_user_id FROM workspaces"))
        return {str(r.id): (r.status, r.owner_user_id) for r in rows}


async def test_user_deleted_removes_solely_owned_workspaces(
    client: httpx.AsyncClient,
    app: FastAPI,
    clerk: Clerk,
    engine: AsyncEngine,
    fake_dodo: FakeDodo,
) -> None:
    """The user goes at once; their workspace is marked deleting (it may outlive its owner) and
    the purge removes it (T9.6)."""
    doomed, me = await sign_in(client, clerk, email="doomed@example.com")
    _, survivor = await sign_in(client, clerk, email="survivor@example.com")
    status = await _deliver_and_process(
        client, app, {"type": "user.deleted", "data": {"id": doomed, "deleted": True}}
    )
    assert status is WebhookStatus.PROCESSED
    wid, kept = me["workspaces"][0]["id"], survivor["workspaces"][0]["id"]
    assert await workspace_rows(engine) == {
        wid: ("deleting", None),
        kept: ("active", uuid.UUID(survivor["id"])),
    }
    async with engine.connect() as conn:
        emails = (await conn.execute(text("SELECT email FROM users"))).scalars().all()
    assert emails == ["survivor@example.com"]

    assert await purge(app, fake_dodo, wid) == "purged"
    assert list(await workspace_rows(engine)) == [kept]


async def _paid(engine: AsyncEngine, fake_dodo: FakeDodo, wid: str, sub_id: str) -> None:
    fake_dodo.add_subscription(
        sub_id, product_id=PRO_PRODUCT, status="active", customer_id=f"cus_{sub_id}"
    )
    await set_subscription(
        engine,
        workspace_id=wid,
        plan="pro",
        status="active",
        dodo_subscription_id=sub_id,
        dodo_customer_id=f"cus_{sub_id}",
        dodo_product_id=PRO_PRODUCT,
    )


async def test_user_deleted_cancels_the_deleted_workspaces_dodo_subscription(
    client: httpx.AsyncClient, app: FastAPI, clerk: Clerk, engine: AsyncEngine, fake_dodo: FakeDodo
) -> None:
    """F-16: a solely owned workspace's subscription is cancelled at Dodo (the purge's first
    step) before it is deleted; a shared one keeps its subscription with its new owner."""
    doomed, me = await sign_in(client, clerk, email="doomed@example.com")
    _, partner = await sign_in(client, clerk, email="partner@example.com")
    await _paid(engine, fake_dodo, me["workspaces"][0]["id"], "sub_mine")
    await _paid(engine, fake_dodo, partner["workspaces"][0]["id"], "sub_theirs")
    shared = partner["workspaces"][0]["id"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role) "
                "VALUES (:w, :u, 'owner')"
            ),
            {"w": shared, "u": me["id"]},
        )
        await conn.execute(
            text("UPDATE workspaces SET owner_user_id = :u WHERE id = :w"),
            {"w": shared, "u": me["id"]},
        )

    status = await _deliver_and_process(
        client, app, {"type": "user.deleted", "data": {"id": doomed, "deleted": True}}
    )
    assert status is WebhookStatus.PROCESSED
    mine = me["workspaces"][0]["id"]
    assert await purge(app, fake_dodo, mine) == "purged"
    assert fake_dodo.subscriptions["sub_mine"].status == "cancelled"
    assert fake_dodo.subscriptions["sub_theirs"].status == "active"
    assert list(await workspace_rows(engine)) == [shared]


async def test_user_deleted_retries_the_dodo_cancel_until_it_goes_through(
    client: httpx.AsyncClient, app: FastAPI, clerk: Clerk, engine: AsyncEngine, fake_dodo: FakeDodo
) -> None:
    """C-052, fixed in T9.6: Dodo not answering doesn't lose the cancel. The person and their
    data go, but the deleting workspace keeps its subscription row until the purge's retry gets
    the cancel through."""
    doomed, me = await sign_in(client, clerk, email="doomed@example.com")
    wid = me["workspaces"][0]["id"]
    await _paid(engine, fake_dodo, wid, "sub_mine")
    fake_dodo.fail_next(DodoError("down", status=503, retryable=True))

    status = await _deliver_and_process(
        client, app, {"type": "user.deleted", "data": {"id": doomed, "deleted": True}}
    )
    assert status is WebhookStatus.PROCESSED
    with pytest.raises(deletion.PurgeBlocked):
        await purge(app, fake_dodo, wid)
    assert fake_dodo.subscriptions["sub_mine"].status == "active"
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT id FROM users"))).scalars().all() == []
        subs = await conn.execute(
            text("SELECT dodo_subscription_id FROM subscriptions WHERE workspace_id = :w"),
            {"w": wid},
        )
        assert subs.scalars().all() == ["sub_mine"]
    assert await workspace_rows(engine) == {wid: ("deleting", None)}

    assert await purge(app, fake_dodo, wid) == "purged"  # the job's retry
    assert fake_dodo.subscriptions["sub_mine"].status == "cancelled"
    assert await workspace_rows(engine) == {}


async def test_user_deleted_hands_shared_workspaces_to_another_owner(
    client: httpx.AsyncClient, app: FastAPI, clerk: Clerk, engine: AsyncEngine
) -> None:
    leaving, me = await sign_in(client, clerk, email="leaving@example.com")
    _, partner = await sign_in(client, clerk, email="partner@example.com")
    wid = me["workspaces"][0]["id"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role) "
                "VALUES (:w, :u, 'owner')"
            ),
            {"w": wid, "u": partner["id"]},
        )
    await _deliver_and_process(
        client, app, {"type": "user.deleted", "data": {"id": leaving, "deleted": True}}
    )
    async with engine.connect() as conn:
        owner = await conn.scalar(
            text("SELECT owner_user_id FROM workspaces WHERE id = :w"), {"w": wid}
        )
    assert str(owner) == partner["id"]


async def test_processing_twice_does_nothing_the_second_time(
    client: httpx.AsyncClient, app: FastAPI, clerk: Clerk
) -> None:
    clerk_id, _ = await sign_in(client, clerk)
    body, headers = signed({"type": "user.updated", "data": clerk_user(clerk_id)})
    async with jobs_app.open_async():
        await client.post("/webhooks/clerk", content=body, headers=headers)
    async with app.state.engine.connect() as conn:
        event_id = await conn.scalar(text("SELECT id FROM webhook_events"))
    assert await process_event(app.state.sessionmaker, event_id) is WebhookStatus.PROCESSED
    assert await process_event(app.state.sessionmaker, event_id) is None
