"""T9.6: deleting a workspace (FR-ACC-05, F-16) and purging it (§5.9, C-052).

DELETE /v1/w/{wid} makes the workspace unreachable at once and queues purge_workspace; the purge
leaves no row in any tenant table (checked against the TenantScoped registry, so a new table is
covered by the assertion without a change here), no Valkey key and no Cloudinary folder. Dodo and
Cloudinary are fakes; an outage of either keeps the workspace row until a later run succeeds.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.dodo import DodoError
from socialhood.billing.dodo_fake import FakeDodo
from socialhood.jobs.app import app as jobs_app
from socialhood.media.cloudinary import CloudinaryError
from socialhood.media.purge import use_media_purger
from socialhood.repositories.workspace_deletion import tenant_tables
from socialhood.services import workspace_deletion as deletion
from tests.support.api import Clerk, sign_in
from tests.support.automations import make_automation, make_media_item
from tests.support.billing import PRO_PRODUCT, set_subscription
from tests.support.inbox import make_scheduled, make_thread
from tests.support.notify import make_email_delivery
from tests.support.publishing import make_scheduled_post
from tests.tenancy.test_isolation import seed_workspace_b

TENANT_TABLES = sorted(table.name for table in tenant_tables())


@dataclass
class FakeMedia:
    """The Cloudinary folder purge: records each workspace; ``fail`` makes the next calls raise."""

    deleted: list[uuid.UUID] = field(default_factory=list)
    fail: int = 0

    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        if self.fail:
            self.fail -= 1
            raise CloudinaryError("Cloudinary is down")
        self.deleted.append(workspace_id)


@pytest.fixture
def media() -> Iterator[FakeMedia]:
    fake = FakeMedia()
    with use_media_purger(fake):
        yield fake


def deps(app: FastAPI, dodo: FakeDodo, media: FakeMedia) -> deletion.PurgeDeps:
    return deletion.PurgeDeps(
        sessionmaker=app.state.sessionmaker, redis=app.state.redis, dodo=dodo, media=media
    )


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def counts(engine: AsyncEngine, workspace_id: str) -> dict[str, int]:
    """Rows per tenant table for the workspace, from the registry (only non-zero ones)."""
    found: dict[str, int] = {}
    async with engine.connect() as conn:
        for table in TENANT_TABLES:
            n = await conn.scalar(
                text(f"SELECT count(*) FROM {table} WHERE workspace_id = :w"),  # noqa: S608
                {"w": workspace_id},
            )
            if n:
                found[table] = int(n)
    return found


async def delete(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str, name: str
) -> httpx.Response:
    return await client.delete(
        f"/v1/w/{wid}", params={"confirm_name": name}, headers=clerk.headers(clerk_id)
    )


async def signed_in(client: httpx.AsyncClient, clerk: Clerk, **profile: Any) -> tuple[str, str]:
    clerk_id, me = await sign_in(client, clerk, **profile)
    return clerk_id, me["workspaces"][0]["id"]


async def workspace_name(engine: AsyncEngine, wid: str) -> str:
    [row] = await rows(engine, "SELECT name FROM workspaces WHERE id = :w", w=wid)
    return str(row["name"])


async def add_member(engine: AsyncEngine, wid: str, user_id: str, role: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (:w, :u, :r)"),
            {"w": wid, "u": user_id, "r": role},
        )


# ---------------------------------------------------------------- DELETE /v1/w/{wid}


async def test_the_owner_deletes_by_typing_the_name_and_it_stops_at_once(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    clerk_id, me = await sign_in(client, clerk, first_name="Priya", email="priya@example.com")
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)
    account = await client.post(f"/v1/w/{wid}/dev/sandbox/accounts", headers=headers)
    account_id = account.json()["id"]
    await make_automation(engine, workspace_id=wid, account_id=account_id)
    thread = await make_thread(engine, workspace_id=wid, account_id=account_id)
    await make_scheduled(engine, workspace_id=wid, conversation_id=thread.conversation_id)
    await make_scheduled_post(
        engine, workspace_id=wid, account_ids=[account_id], status="scheduled"
    )
    await make_email_delivery(engine, workspace_id=wid)

    response = await delete(client, clerk, clerk_id, wid, "  Priya's workspace ")
    assert response.status_code == 202, response.text
    body = response.json()
    assert (body["id"], body["status"]) == (wid, "deleting")
    requested = datetime.fromisoformat(body["deletion_requested_at"])
    assert datetime.fromisoformat(body["purge_by"]) - requested == timedelta(hours=24)

    [ws] = await rows(engine, "SELECT * FROM workspaces WHERE id = :w", w=wid)
    assert ws["status"] == "deleting"
    assert str(ws["deletion_requested_by_user_id"]) == me["id"]
    assert ws["deletion_requested_at"] is not None
    [acct] = await rows(engine, "SELECT * FROM social_accounts WHERE workspace_id = :w", w=wid)
    assert (acct["status"], acct["access_token_enc"]) == ("disconnected", None)
    assert [
        r["status"]
        for r in await rows(engine, "SELECT status FROM automations WHERE workspace_id = :w", w=wid)
    ] == ["paused"]
    assert [
        r["status"]
        for r in await rows(
            engine, "SELECT status FROM scheduled_messages WHERE workspace_id = :w", w=wid
        )
    ] == ["canceled"]
    assert [
        r["status"]
        for r in await rows(
            engine, "SELECT status FROM scheduled_posts WHERE workspace_id = :w", w=wid
        )
    ] == ["canceled"]
    assert [
        r["status"]
        for r in await rows(
            engine, "SELECT status FROM scheduled_post_targets WHERE workspace_id = :w", w=wid
        )
    ] == ["canceled"]
    assert [
        r["status"]
        for r in await rows(
            engine, "SELECT status FROM email_deliveries WHERE workspace_id = :w", w=wid
        )
    ] == ["skipped"]

    # The purge is queued once the deletion commits.
    jobs = await jobs_app.connector.execute_query_all_async(
        "SELECT task_name, args, queueing_lock, lock, queue_name FROM procrastinate_jobs"
        " WHERE task_name = 'purge_workspace'"
    )
    assert jobs == [
        {
            "task_name": "purge_workspace",
            "args": {"workspace_id": wid},
            "queueing_lock": f"purge:{wid}",
            "lock": f"purge:{wid}",
            "queue_name": "bulk",
        }
    ]

    # Every route answers 404; the owner lands in a new workspace of their own (F-16).
    for path in (f"/v1/w/{wid}", f"/v1/w/{wid}/overview", f"/v1/w/{wid}/social-accounts"):
        gone = await client.get(path, headers=headers)
        assert gone.status_code == 404, path
    again = await delete(client, clerk, clerk_id, wid, "Priya's workspace")
    assert again.status_code == 404
    me_after = (await client.get("/v1/me", headers=headers)).json()
    assert [w["id"] for w in me_after["workspaces"]] != [wid]
    [fresh] = me_after["workspaces"]
    assert fresh["name"] == "Priya's workspace"
    assert me_after["last_workspace_id"] == fresh["id"]


async def test_an_owner_with_another_workspace_lands_there(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk, email="a@example.com", first_name="Anna")
    _, other = await sign_in(client, clerk, email="b@example.com", first_name="Ben")
    wid, shared = me["workspaces"][0]["id"], other["workspaces"][0]["id"]
    await add_member(engine, shared, me["id"], "owner")
    response = await delete(client, clerk, clerk_id, wid, "Anna's workspace")
    assert response.status_code == 202
    me_after = (await client.get("/v1/me", headers=clerk.headers(clerk_id))).json()
    assert [w["id"] for w in me_after["workspaces"]] == [shared]
    assert me_after["last_workspace_id"] == shared


async def test_a_wrong_name_changes_nothing(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, wid = await signed_in(client, clerk, first_name="Priya")
    for typed in ("priya's workspace", "Priya"):
        response = await delete(client, clerk, clerk_id, wid, typed)
        assert response.status_code == 422
        assert response.json()["errors"] == [
            {"field": "confirm_name", "message": deletion.CONFIRM_MISMATCH}
        ]
    missing = await client.delete(f"/v1/w/{wid}", headers=clerk.headers(clerk_id))
    assert missing.status_code == 422
    [ws] = await rows(engine, "SELECT status FROM workspaces WHERE id = :w", w=wid)
    assert ws["status"] == "active"


async def test_only_an_owner_can_delete(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    _, wid = await signed_in(client, clerk, email="owner@example.com", first_name="Priya")
    admin_id, admin = await sign_in(client, clerk, email="admin@example.com")
    await add_member(engine, wid, admin["id"], "admin")
    response = await delete(client, clerk, admin_id, wid, "Priya's workspace")
    assert response.status_code == 403
    [ws] = await rows(engine, "SELECT status FROM workspaces WHERE id = :w", w=wid)
    assert ws["status"] == "active"


# ---------------------------------------------------------------- the purge


async def _redis_keys(redis: Redis, wid: str, account_id: str) -> list[str]:
    names = [
        f"events:{wid}",
        f"idem:{wid}:{uuid.uuid4()}:key",
        f"bulk:{wid}",
        f"profile:{account_id}:igsid_1",
        f"bucket:send:{account_id}",
        f"wa:templates:{account_id}",
    ]
    for name in names:
        await redis.set(name, "1")
    return names


async def test_the_purge_leaves_no_row_key_or_file(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    fake_dodo: FakeDodo,
    media: FakeMedia,
) -> None:
    """Workspace B holds a row in every tenant table; after the purge none of B's is left, and
    workspace A (its rows, keys and webhook events) is untouched."""
    a_clerk, keep = await signed_in(client, clerk, email="a@example.com", first_name="Anna")
    keep_account = await client.post(
        f"/v1/w/{keep}/dev/sandbox/accounts", headers=clerk.headers(a_clerk)
    )
    keep_account_id = keep_account.json()["id"]
    keep_thread = await make_thread(engine, workspace_id=keep, account_id=keep_account_id)
    await make_automation(engine, workspace_id=keep, account_id=keep_account_id)
    await make_media_item(engine, workspace_id=keep, account_id=keep_account_id)
    await _extra_rows(engine, keep, str(keep_thread.message_ids[0]))

    seed = await seed_workspace_b(client, clerk, engine)
    wid = seed.workspace_id
    await _extra_rows(engine, wid, seed.message_id)
    async with engine.begin() as conn:
        for workspace_id in (wid, keep):
            await conn.execute(
                text(
                    "INSERT INTO webhook_events (provider, dedupe_key, event_type, workspace_id,"
                    " payload, status) VALUES ('instagram', :k, 'message', :w, '{}', 'processed')"
                ),
                {"k": f"ig:{uuid.uuid4()}", "w": workspace_id},
            )
    keys = await _redis_keys(redis, wid, seed.account_id)
    kept_keys = await _redis_keys(redis, keep, keep_account_id)

    seeded = await counts(engine, wid)
    unseeded = sorted(set(TENANT_TABLES) - set(seeded))
    assert not unseeded, (
        "Seed a row in every tenant table so the purge is tested against it (extend "
        f"_extra_rows or tests/tenancy/test_isolation.seed_workspace_b): {unseeded}"
    )
    kept_before = await counts(engine, keep)

    owner_b = await _owner_clerk_id(engine, wid)
    response = await delete(client, clerk, owner_b, wid, await workspace_name(engine, wid))
    assert response.status_code == 202, response.text
    result = await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))

    assert result.status == "purged"
    assert await counts(engine, wid) == {}
    assert await rows(engine, "SELECT id FROM workspaces WHERE id = :w", w=wid) == []
    assert await rows(engine, "SELECT id FROM webhook_events WHERE workspace_id = :w", w=wid) == []
    assert [await redis.exists(k) for k in keys] == [0] * len(keys)
    assert media.deleted == [uuid.UUID(wid)]

    assert await counts(engine, keep) == kept_before
    assert [await redis.exists(k) for k in kept_keys] == [1] * len(kept_keys)
    kept_events = await rows(
        engine, "SELECT id FROM webhook_events WHERE workspace_id = :w", w=keep
    )
    assert len(kept_events) == 1

    # Idempotent: another run finds nothing to do.
    again = await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))
    assert again.status == "gone"


async def _owner_clerk_id(engine: AsyncEngine, wid: str) -> str:
    [row] = await rows(
        engine,
        "SELECT u.clerk_user_id FROM workspaces w JOIN users u ON u.id = w.owner_user_id"
        " WHERE w.id = :w",
        w=wid,
    )
    return str(row["clerk_user_id"])


async def _extra_rows(engine: AsyncEngine, wid: str, message_id: str) -> None:
    """Rows the isolation seed doesn't make: a triggered automation run, a post an automation is
    limited to, a usage counter and an AI usage event."""
    async with engine.begin() as conn:
        automation = (
            await conn.execute(
                text("SELECT id FROM automations WHERE workspace_id = :w LIMIT 1"), {"w": wid}
            )
        ).scalar_one()
        media_item = (
            await conn.execute(
                text("SELECT id FROM media_items WHERE workspace_id = :w LIMIT 1"), {"w": wid}
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO automation_posts (workspace_id, automation_id, media_item_id)"
                " VALUES (:w, :a, :m) ON CONFLICT DO NOTHING"
            ),
            {"w": wid, "a": automation, "m": media_item},
        )
        await conn.execute(
            text(
                "INSERT INTO automation_runs (workspace_id, automation_id, trigger_message_id,"
                " matched_keyword, result) VALUES (:w, :a, :m, 'link', 'sent')"
            ),
            {"w": wid, "a": automation, "m": message_id},
        )
        await conn.execute(
            text(
                "INSERT INTO usage_counters (workspace_id, metric, period_start, period_end, used)"
                " VALUES (:w, 'ai_credits', current_date, current_date + 30, 3)"
                " ON CONFLICT DO NOTHING"
            ),
            {"w": wid},
        )
        await conn.execute(
            text(
                "INSERT INTO ai_usage_events (workspace_id, feature, model, credits, outcome)"
                " VALUES (:w, 'message_analysis', 'fake', 1, 'ok')"
            ),
            {"w": wid},
        )


async def _deleting_paid_workspace(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, fake_dodo: FakeDodo
) -> str:
    clerk_id, wid = await signed_in(client, clerk, first_name="Priya")
    fake_dodo.add_subscription("sub_live", product_id=PRO_PRODUCT, status="active")
    await set_subscription(
        engine,
        workspace_id=wid,
        plan="pro",
        status="active",
        dodo_subscription_id="sub_live",
        dodo_customer_id="cus_live",
        dodo_product_id=PRO_PRODUCT,
    )
    response = await delete(client, clerk, clerk_id, wid, "Priya's workspace")
    assert response.status_code == 202
    return wid


async def test_billing_is_cancelled_first_and_an_outage_keeps_the_subscription(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    fake_dodo: FakeDodo,
    media: FakeMedia,
) -> None:
    """C-052: Dodo not answering doesn't lose the cancel. Everything else is purged, but the
    subscription row (naming the Dodo subscription) and the workspace stay until a later run
    gets the cancel through."""
    wid = await _deleting_paid_workspace(client, clerk, engine, fake_dodo)
    fake_dodo.fail_next(DodoError("down", status=503, retryable=True))

    with pytest.raises(deletion.PurgeBlocked) as blocked:
        await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))
    assert blocked.value.reasons == ["billing"]
    assert fake_dodo.subscriptions["sub_live"].status == "active"
    assert await counts(engine, wid) == {"subscriptions": 1}
    [ws] = await rows(engine, "SELECT status FROM workspaces WHERE id = :w", w=wid)
    assert ws["status"] == "deleting"

    result = await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))
    assert result.status == "purged"
    assert fake_dodo.subscriptions["sub_live"].status == "cancelled"
    assert [name for name, _ in fake_dodo.calls] == ["cancel_now", "cancel_now"]
    assert await counts(engine, wid) == {}
    assert await rows(engine, "SELECT id FROM workspaces WHERE id = :w", w=wid) == []


async def test_a_subscription_dodo_no_longer_has_doesnt_block_the_purge(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    fake_dodo: FakeDodo,
    media: FakeMedia,
) -> None:
    wid = await _deleting_paid_workspace(client, clerk, engine, fake_dodo)
    fake_dodo.fail_next(DodoError("not found", status=404))
    result = await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))
    assert result.status == "purged"


async def test_a_cloudinary_outage_keeps_the_workspace_until_the_folder_is_gone(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    fake_dodo: FakeDodo,
    media: FakeMedia,
) -> None:
    clerk_id, wid = await signed_in(client, clerk, first_name="Priya")
    assert (await delete(client, clerk, clerk_id, wid, "Priya's workspace")).status_code == 202
    media.fail = 1
    with pytest.raises(deletion.PurgeBlocked) as blocked:
        await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))
    assert blocked.value.reasons == ["media"]
    assert await counts(engine, wid) == {"subscriptions": 1}
    assert len(await rows(engine, "SELECT id FROM workspaces WHERE id = :w", w=wid)) == 1

    result = await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))
    assert result.status == "purged"
    assert media.deleted == [uuid.UUID(wid)]


async def test_a_purge_that_runs_out_of_time_resumes(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    fake_dodo: FakeDodo,
    media: FakeMedia,
) -> None:
    clerk_id, wid = await signed_in(client, clerk, first_name="Priya")
    account = await client.post(
        f"/v1/w/{wid}/dev/sandbox/accounts", headers=clerk.headers(clerk_id)
    )
    await make_thread(
        engine, workspace_id=wid, account_id=account.json()["id"], texts=("a", "b", "c")
    )
    assert (await delete(client, clerk, clerk_id, wid, "Priya's workspace")).status_code == 202

    runs = []
    while True:
        result = await deletion.purge_workspace(
            deps(app, fake_dodo, media), uuid.UUID(wid), batch=1, budget_s=0
        )
        runs.append(result.status)
        if result.status != "continue":
            break
    assert runs[-1] == "purged"
    assert runs.count("continue") >= 3  # at least one hand-over per message
    assert await counts(engine, wid) == {}


async def test_the_purge_never_touches_an_active_workspace(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    fake_dodo: FakeDodo,
    media: FakeMedia,
) -> None:
    _, wid = await signed_in(client, clerk)
    before = await counts(engine, wid)
    result = await deletion.purge_workspace(deps(app, fake_dodo, media), uuid.UUID(wid))
    assert result.status == "not_deleting"
    assert await counts(engine, wid) == before
    assert media.deleted == []


async def test_the_sweep_requeues_every_deleting_workspace_and_alerts_when_overdue(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    _, fresh = await signed_in(client, clerk, email="a@example.com")
    _, stuck = await signed_in(client, clerk, email="b@example.com")
    _, active = await signed_in(client, clerk, email="c@example.com")
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        for wid, age in ((fresh, timedelta(minutes=5)), (stuck, timedelta(hours=7))):
            await conn.execute(
                text(
                    "UPDATE workspaces SET status = 'deleting', deletion_requested_at = :at"
                    " WHERE id = :w"
                ),
                {"w": wid, "at": now - age},
            )

    swept = await deletion.sweep(app.state.sessionmaker, now)
    assert swept.requeued == 2
    assert swept.overdue == [uuid.UUID(stuck)]
    jobs = await jobs_app.connector.execute_query_all_async(
        "SELECT args FROM procrastinate_jobs WHERE task_name = 'purge_workspace' ORDER BY id"
    )
    assert sorted(job["args"]["workspace_id"] for job in jobs) == sorted([fresh, stuck])
    assert active not in [job["args"]["workspace_id"] for job in jobs]

    again = await deletion.sweep(app.state.sessionmaker, now)
    assert again.requeued == 0  # still waiting: the queueing lock makes it a no-op
