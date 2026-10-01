"""C-067: deleting one connected account's data (FR-CON-06, F-16).

Disconnect and delete data, Remove, and Meta's data-deletion callback all queue
purge_account_data. The purge leaves none of the account's rows in any account table (the list
comes from the schema: repositories/account_deletion.account_tables), none of the files its
messages own, none of its Valkey keys, and then removes the account; another account in the same
workspace, the workspace's own data (knowledge, settings, billing) and other workspaces are
untouched. Cloudinary is a fake.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.tasks.privacy import delete_user_data
from socialhood.jobs.tasks.purge import run_account_purge, sweep_all
from socialhood.media.cloudinary import CloudinaryError
from socialhood.media.purge import StoredFile, use_media_purger
from socialhood.platforms.deps import deps_from
from socialhood.repositories.account_deletion import account_tables, owned_by
from socialhood.repositories.workspace_deletion import tenant_tables
from socialhood.security.signatures import sign_request
from socialhood.services import account_deletion as deletion
from socialhood.services.connections import BEING_DELETED
from socialhood.services.scheduled_posts import views as scheduled_post_views
from tests.support.ai import make_analysis, make_decision, make_source, make_suggestion
from tests.support.analytics import make_account_day, make_comment_analysis, make_snapshot
from tests.support.api import IG_APP_SECRET, Clerk, sign_in
from tests.support.automations import make_automation, make_comment, make_media_item
from tests.support.billing import set_subscription
from tests.support.inbox import make_account, make_asset, make_scheduled, make_thread
from tests.support.instagram import FakeInstagram, connect
from tests.support.publishing import make_posting_slot, make_scheduled_post
from tests.tenancy.test_isolation import seed_workspace_b

ACCOUNT_TABLES = [table.name for table in account_tables()]
TENANT_TABLES = sorted(table.name for table in tenant_tables())


@dataclass
class FakeMedia:
    """The media purger: records each file deleted; ``fail`` makes the next calls raise."""

    files: list[tuple[uuid.UUID, str]] = field(default_factory=list)
    folders: list[uuid.UUID] = field(default_factory=list)
    fail: int = 0

    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        self.folders.append(workspace_id)

    async def delete_files(self, workspace_id: uuid.UUID, files: Sequence[StoredFile]) -> None:
        if self.fail:
            self.fail -= 1
            raise CloudinaryError("Cloudinary is down")
        self.files.extend((workspace_id, f.public_id) for f in files)


@pytest.fixture
def media() -> Iterator[FakeMedia]:
    fake = FakeMedia()
    with use_media_purger(fake):
        yield fake


@pytest.fixture(autouse=True)
def post_views_use_test_deps(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Settling a scheduled post builds its event with the worker's deps (jobs/runtime, from the
    environment, which has no token key in CI); use the test app's instead."""
    monkeypatch.setattr(
        scheduled_post_views,
        "_worker_deps",
        lambda: deps_from(app.state.http, app.state.settings),
    )


def deps(app: FastAPI, media: FakeMedia) -> deletion.PurgeDeps:
    return deletion.PurgeDeps(
        sessionmaker=app.state.sessionmaker, redis=app.state.redis, media=media
    )


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def execute(engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def owned_counts(engine: AsyncEngine, wid: str, account_id: str) -> dict[str, int]:
    """The account's rows per account table (non-zero ones)."""
    w, a = uuid.UUID(wid), uuid.UUID(account_id)
    found: dict[str, int] = {}
    async with engine.connect() as conn:
        for table in account_tables():
            n = await conn.scalar(
                select(func.count())
                .select_from(table)
                .where(table.c.workspace_id == w, owned_by(table, a, w))
            )
            if n:
                found[table.name] = int(n)
    return found


async def tenant_counts(engine: AsyncEngine, wid: str) -> dict[str, int]:
    found: dict[str, int] = {}
    async with engine.connect() as conn:
        for table in TENANT_TABLES:
            n = await conn.scalar(
                text(f"SELECT count(*) FROM {table} WHERE workspace_id = :w"),  # noqa: S608
                {"w": wid},
            )
            if n:
                found[table] = int(n)
    return found


async def add_member(engine: AsyncEngine, wid: str, user_id: str, role: str) -> None:
    await execute(
        engine,
        "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (:w, :u, :r)",
        w=wid,
        u=user_id,
        r=role,
    )


async def attach(
    engine: AsyncEngine, message_id: uuid.UUID, asset_ids: Sequence[uuid.UUID]
) -> None:
    attachments = [
        {
            "id": str(a),
            "type": "image",
            "url": "https://res.cloudinary.com/x.jpg",
            "asset_id": str(a),
        }
        for a in asset_ids
    ]
    await execute(
        engine,
        "UPDATE messages SET attachments = CAST(:a AS jsonb) WHERE id = :m",
        a=json.dumps(attachments),
        m=message_id,
    )


@dataclass(frozen=True)
class Seeded:
    conversation_id: uuid.UUID
    message_ids: list[uuid.UUID]
    scheduled_message_id: uuid.UUID
    automation_id: uuid.UUID
    post_id: uuid.UUID


async def seed_account(engine: AsyncEngine, wid: str, account_id: str) -> Seeded:
    """A row in every account table for the account."""
    thread = await make_thread(
        engine, workspace_id=wid, account_id=account_id, texts=("Hi", "How much?")
    )
    on = {
        "workspace_id": wid,
        "conversation_id": thread.conversation_id,
        "message_id": thread.message_ids[0],
    }
    await make_analysis(engine, **on)
    await make_suggestion(engine, **on)
    await make_decision(engine, **on)
    scheduled = await make_scheduled(
        engine, workspace_id=wid, conversation_id=thread.conversation_id
    )
    post = await make_media_item(engine, workspace_id=wid, account_id=account_id)
    comment = await make_comment(
        engine,
        workspace_id=wid,
        account_id=account_id,
        media_item_id=post,
        contact_id=thread.contact_id,
    )
    await make_comment_analysis(engine, workspace_id=wid, comment_id=comment)
    await make_snapshot(engine, workspace_id=wid, media_item_id=post)
    await make_account_day(engine, workspace_id=wid, account_id=account_id)
    automation = await make_automation(
        engine, workspace_id=wid, account_id=account_id, media_item_ids=(post,)
    )
    await execute(
        engine,
        "INSERT INTO automation_runs (workspace_id, automation_id, trigger_comment_id,"
        " matched_keyword, result) VALUES (:w, :a, :c, 'link', 'queued')",
        w=wid,
        a=automation,
        c=comment,
    )
    await make_posting_slot(engine, workspace_id=wid, account_id=account_id)
    return Seeded(
        conversation_id=thread.conversation_id,
        message_ids=thread.message_ids,
        scheduled_message_id=scheduled,
        automation_id=automation,
        post_id=post,
    )


async def pro_workspace(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> tuple[str, str, dict[str, Any]]:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com", first_name="Priya")
    wid = me["workspaces"][0]["id"]
    await set_subscription(engine, workspace_id=wid, plan="pro", status="active")
    return clerk_id, wid, me


# ---------------------------------------------------------------- the purge


async def test_the_purge_leaves_nothing_of_the_account_and_spares_everything_else(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    media: FakeMedia,
) -> None:
    other_workspace = await seed_workspace_b(client, clerk, engine)
    _, wid, _ = await pro_workspace(client, clerk, engine)
    doomed = str(await make_account(engine, wid, platform_account_id="17841400000000001"))
    kept = str(await make_account(engine, wid, platform_account_id="17841400000000002"))
    x = await seed_account(engine, wid, doomed)
    y = await seed_account(engine, wid, kept)
    await make_source(engine, workspace_id=wid)

    # Posts: one to both accounts, one published only to the doomed one, one scheduled for it.
    both = await make_scheduled_post(
        engine, workspace_id=wid, account_ids=[doomed, kept], status="scheduled"
    )
    only_published = await make_scheduled_post(
        engine,
        workspace_id=wid,
        account_ids=[doomed],
        status="published",
        target_status="published",
    )
    only_scheduled = await make_scheduled_post(
        engine, workspace_id=wid, account_ids=[doomed], status="scheduled"
    )

    # Files: which the doomed account's messages own, and which something else also names.
    inbound = await make_asset(engine, workspace_id=wid, purpose="inbound")
    shared_with_kept = await make_asset(engine, workspace_id=wid)
    library = await make_asset(engine, workspace_id=wid, purpose="post")
    in_kept_automation = await make_asset(engine, workspace_id=wid)
    in_own_automation = await make_asset(engine, workspace_id=wid)
    scheduled_only = await make_asset(engine, workspace_id=wid)
    kept_inbound = await make_asset(engine, workspace_id=wid, purpose="inbound")
    await attach(
        engine,
        x.message_ids[0],
        [inbound, shared_with_kept, library, in_kept_automation, in_own_automation],
    )
    await attach(engine, y.message_ids[0], [shared_with_kept, kept_inbound])
    await execute(
        engine,
        "UPDATE automations SET message_media_asset_id = :m WHERE id = :a",
        m=in_kept_automation,
        a=y.automation_id,
    )
    await execute(
        engine,
        "UPDATE automations SET message_media_asset_id = :m WHERE id = :a",
        m=in_own_automation,
        a=x.automation_id,
    )
    await execute(
        engine,
        "UPDATE scheduled_messages SET attachment_asset_ids = ARRAY[CAST(:m AS uuid)]"
        " WHERE id = :s",
        m=scheduled_only,
        s=x.scheduled_message_id,
    )
    public_ids = {
        r["id"]: r["public_id"]
        for r in await rows(
            engine, "SELECT id, public_id FROM media_assets WHERE workspace_id = :w", w=wid
        )
    }

    # Raw webhook payloads: the doomed account's here, the kept one's, and the same platform
    # account's in another workspace.
    for workspace_id, platform_id in (
        (wid, "17841400000000001"),
        (wid, "17841400000000002"),
        (other_workspace.workspace_id, "17841400000000001"),
    ):
        await execute(
            engine,
            "INSERT INTO webhook_events (provider, dedupe_key, event_type, platform_account_id,"
            " workspace_id, payload, status) VALUES ('instagram', :k, 'message', :p, :w, '{}',"
            " 'processed')",
            k=f"ig:{uuid.uuid4()}",
            p=platform_id,
            w=workspace_id,
        )

    # Valkey: the doomed account's keys, the kept one's, and the workspace's event stream.
    doomed_keys = [f"bucket:send:{doomed}", f"profile:{doomed}:igsid_1", f"wa:templates:{doomed}"]
    kept_keys = [f"bucket:send:{kept}", f"profile:{kept}:igsid_1"]
    for key in doomed_keys + kept_keys:
        await redis.set(key, "1")
    await redis.xadd(f"events:{wid}", {"type": "message.created", "data": '{"text": "Hi"}'})

    seeded = await owned_counts(engine, wid, doomed)
    assert sorted(seeded) == sorted(ACCOUNT_TABLES), (
        "Seed a row in every account table so the purge is tested against it (extend "
        f"seed_account): {sorted(set(ACCOUNT_TABLES) - set(seeded))}"
    )
    kept_before = await owned_counts(engine, wid, kept)
    other_before = await tenant_counts(engine, other_workspace.workspace_id)
    workspace_before = await tenant_counts(engine, wid)

    await mark_deleting(app, wid, doomed)
    result = await deletion.purge_account(deps(app, media), uuid.UUID(wid), uuid.UUID(doomed))

    assert result.status == "purged"
    for table, n in seeded.items():
        assert result.deleted.get(table) == n, table  # each by the purge, not a cascade
    assert await rows(engine, "SELECT id FROM social_accounts WHERE id = :a", a=doomed) == []

    # Files: only those the doomed account's messages own.
    owned_files = {inbound, in_own_automation, scheduled_only}
    assert sorted(media.files) == sorted((uuid.UUID(wid), public_ids[a]) for a in owned_files)
    assert result.files == 3
    left = {
        r["id"]
        for r in await rows(engine, "SELECT id FROM media_assets WHERE workspace_id = :w", w=wid)
    }
    assert left.isdisjoint(owned_files)
    assert {shared_with_kept, library, in_kept_automation, kept_inbound} <= left

    # Posts: the shared one keeps its other account; the ones that were only the doomed
    # account's are gone (published there) or canceled.
    targets = await rows(
        engine,
        "SELECT social_account_id FROM scheduled_post_targets WHERE workspace_id = :w",
        w=wid,
    )
    assert [str(t["social_account_id"]) for t in targets] == [kept]  # the shared post's
    statuses = {
        r["id"]: r["status"]
        for r in await rows(
            engine, "SELECT id, status FROM scheduled_posts WHERE workspace_id = :w", w=wid
        )
    }
    assert only_published.id not in statuses
    assert statuses[only_scheduled.id] == "canceled"
    assert statuses[both.id] == "scheduled"

    # The kept account, the workspace's own data and the other workspace are untouched.
    assert await owned_counts(engine, wid, kept) == kept_before
    assert await tenant_counts(engine, other_workspace.workspace_id) == other_before
    workspace_after = await tenant_counts(engine, wid)
    for table in set(TENANT_TABLES) - set(ACCOUNT_TABLES):
        expected = workspace_before.get(table, 0)
        if table == "media_assets":
            expected -= 3
        elif table in ("social_accounts", "scheduled_posts", "scheduled_post_assets"):
            expected -= 1  # the account; the post published only to it, and its image
        assert workspace_after.get(table, 0) == expected, table
    for table in ACCOUNT_TABLES:  # what is left is the kept account's
        assert workspace_after.get(table, 0) == kept_before.get(table, 0), table

    events_left = await rows(
        engine,
        "SELECT platform_account_id, workspace_id FROM webhook_events ORDER BY platform_account_id",
    )
    assert [(e["platform_account_id"], str(e["workspace_id"])) for e in events_left] == [
        ("17841400000000001", other_workspace.workspace_id),
        ("17841400000000002", wid),
    ]

    assert [await redis.exists(k) for k in doomed_keys] == [0] * len(doomed_keys)
    assert [await redis.exists(k) for k in kept_keys] == [1] * len(kept_keys)
    stream = await redis.xrange(f"events:{wid}")
    assert [entry["type"] for _, entry in stream] == ["resync"]

    # Idempotent: another run finds nothing to do.
    again = await deletion.purge_account(deps(app, media), uuid.UUID(wid), uuid.UUID(doomed))
    assert again.status == "gone"


async def mark_deleting(app: FastAPI, wid: str, account_id: str) -> None:
    """What Disconnect and delete data does before the purge (without the API)."""
    from socialhood.db.tenancy import workspace_scope
    from socialhood.repositories import social_accounts

    with workspace_scope(uuid.UUID(wid)):
        async with app.state.sessionmaker() as session:
            acct = await social_accounts.get(session, uuid.UUID(account_id))
            assert acct is not None
            await deletion.begin(
                session,
                acct,
                requested_by=None,
                deps=deps_from(app.state.http, app.state.settings),
            )
            await session.commit()


async def test_a_purge_that_runs_out_of_time_resumes(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, media: FakeMedia
) -> None:
    _, wid, _ = await pro_workspace(client, clerk, engine)
    account = str(await make_account(engine, wid, platform_account_id="17841400000000003"))
    await seed_account(engine, wid, account)
    await make_thread(engine, workspace_id=wid, account_id=account, texts=("a", "b", "c"))
    files = [await make_asset(engine, workspace_id=wid, purpose="inbound") for _ in range(3)]
    thread = await make_thread(engine, workspace_id=wid, account_id=account)
    await attach(engine, thread.message_ids[0], files)
    await mark_deleting(app, wid, account)

    runs = []
    while True:
        result = await deletion.purge_account(
            deps(app, media),
            uuid.UUID(wid),
            uuid.UUID(account),
            batch=1,
            file_batch=1,
            budget_s=0,
        )
        runs.append(result.status)
        if result.status != "continue":
            break
    assert runs[-1] == "purged"
    assert runs.count("continue") >= 6  # at least one hand-over per file and per message
    assert len(media.files) == 3
    assert await rows(engine, "SELECT id FROM social_accounts WHERE id = :a", a=account) == []
    left = await tenant_counts(engine, wid)
    assert [table for table in ACCOUNT_TABLES if left.get(table)] == []


async def test_a_cloudinary_outage_keeps_the_messages_until_their_files_are_gone(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, media: FakeMedia
) -> None:
    _, wid, _ = await pro_workspace(client, clerk, engine)
    account = str(await make_account(engine, wid, platform_account_id="17841400000000004"))
    thread = await make_thread(engine, workspace_id=wid, account_id=account)
    photo = await make_asset(engine, workspace_id=wid, purpose="inbound")
    await attach(engine, thread.message_ids[0], [photo])
    await mark_deleting(app, wid, account)

    media.fail = 1
    with pytest.raises(deletion.AccountPurgeBlocked) as blocked:
        await deletion.purge_account(deps(app, media), uuid.UUID(wid), uuid.UUID(account))
    assert blocked.value.reasons == ["media"]
    assert len(await rows(engine, "SELECT id FROM messages WHERE workspace_id = :w", w=wid)) == 1
    assert len(await rows(engine, "SELECT id FROM media_assets WHERE id = :a", a=photo)) == 1

    result = await deletion.purge_account(deps(app, media), uuid.UUID(wid), uuid.UUID(account))
    assert result.status == "purged"
    assert len(media.files) == 1


async def test_the_purge_never_touches_an_account_that_isnt_being_deleted(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, media: FakeMedia
) -> None:
    _, wid, _ = await pro_workspace(client, clerk, engine)
    account = str(await make_account(engine, wid, platform_account_id="17841400000000005"))
    await seed_account(engine, wid, account)
    before = await owned_counts(engine, wid, account)
    result = await deletion.purge_account(deps(app, media), uuid.UUID(wid), uuid.UUID(account))
    assert result.status == "not_deleting"
    assert await owned_counts(engine, wid, account) == before


# ---------------------------------------------------------------- DELETE …/social-accounts/{id}


def url(wid: str, account_id: str) -> str:
    return f"/v1/w/{wid}/social-accounts/{account_id}"


async def jobs(task: str) -> list[dict[str, Any]]:
    return await jobs_app.connector.execute_query_all_async(
        "SELECT args, queueing_lock, lock, queue_name FROM procrastinate_jobs"
        " WHERE task_name = %(task)s ORDER BY id",
        task=task,
    )


async def test_disconnect_and_delete_data(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    media: FakeMedia,
    queue: None,
) -> None:
    owner_id, wid, _ = await pro_workspace(client, clerk, engine)
    admin_id, admin = await sign_in(client, clerk, email="admin@example.com")
    agent_id, agent = await sign_in(client, clerk, email="agent@example.com")
    await add_member(engine, wid, admin["id"], "admin")
    await add_member(engine, wid, agent["id"], "agent")
    account = str(await make_account(engine, wid, platform_account_id="17841400000000006"))
    other = str(
        await make_account(
            engine, wid, platform_account_id="17841400000000007", username="other.shop"
        )
    )
    seeded = await seed_account(engine, wid, account)

    billing = (await client.get(f"/v1/w/{wid}/billing", headers=clerk.headers(owner_id))).json()
    meters = {m["metric"]: m["used"] for m in billing["usage"]}
    assert meters["instagram_accounts"] == 2
    assert meters["active_automations"] == 1

    ask = {"delete_data": "true", "confirm": "@maple.bakery"}
    denied = await client.delete(url(wid, account), params=ask, headers=clerk.headers(agent_id))
    assert denied.status_code == 403

    for params in ({"delete_data": "true"}, {"delete_data": "true", "confirm": "@other.shop"}):
        refused = await client.delete(
            url(wid, account), params=params, headers=clerk.headers(admin_id)
        )
        assert refused.status_code == 422, refused.text
        assert refused.json()["errors"] == [
            {"field": "confirm", "message": "Type @maple.bakery exactly as shown to confirm."}
        ]
    [row] = await rows(
        engine, "SELECT status, deletion_requested_at FROM social_accounts WHERE id = :a", a=account
    )
    assert (row["status"], row["deletion_requested_at"]) == ("active", None)
    assert await jobs("purge_account_data") == []

    # Any case, with or without "@".
    response = await client.delete(
        url(wid, account),
        params={"delete_data": "true", "confirm": " MAPLE.bakery "},
        headers=clerk.headers(admin_id),
    )
    assert response.status_code == 204, response.text

    [row] = await rows(engine, "SELECT * FROM social_accounts WHERE id = :a", a=account)
    assert (row["status"], row["access_token_enc"]) == ("disconnected", None)
    assert row["deletion_requested_at"] is not None
    assert str(row["deletion_requested_by_user_id"]) == admin["id"]
    [automation] = await rows(
        engine, "SELECT status FROM automations WHERE id = :a", a=seeded.automation_id
    )
    assert automation["status"] == "paused"
    [scheduled] = await rows(
        engine, "SELECT status FROM scheduled_messages WHERE id = :s", s=seeded.scheduled_message_id
    )
    assert scheduled["status"] == "canceled"
    assert await jobs("purge_account_data") == [
        {
            "args": {"workspace_id": wid, "account_id": account},
            "queueing_lock": f"acctpurge:{account}",
            "lock": f"acctpurge:{account}",
            "queue_name": "bulk",
        }
    ]

    listed = (
        await client.get(f"/v1/w/{wid}/social-accounts", headers=clerk.headers(owner_id))
    ).json()["items"]
    by_id = {a["id"]: a for a in listed}
    assert (by_id[account]["status"], by_id[account]["deleting"]) == ("disconnected", True)
    assert by_id[other]["deleting"] is False
    billing = (await client.get(f"/v1/w/{wid}/billing", headers=clerk.headers(owner_id))).json()
    meters = {m["metric"]: m["used"] for m in billing["usage"]}
    assert meters["instagram_accounts"] == 1  # the slot is free at once
    assert meters["active_automations"] == 0

    # Asking again is harmless; the purge then removes it.
    again = await client.delete(url(wid, account), params=ask, headers=clerk.headers(owner_id))
    assert again.status_code == 204
    result = await run_account_purge(deps(app, media), uuid.UUID(wid), uuid.UUID(account))
    assert result.status == "purged"
    listed = (
        await client.get(f"/v1/w/{wid}/social-accounts", headers=clerk.headers(owner_id))
    ).json()["items"]
    assert [a["id"] for a in listed] == [other]


async def test_remove_is_for_disconnected_and_sandbox_accounts(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    media: FakeMedia,
    queue: None,
) -> None:
    owner_id, wid, _ = await pro_workspace(client, clerk, engine)
    headers = clerk.headers(owner_id)
    live = str(await make_account(engine, wid, platform_account_id="17841400000000008"))

    refused = await client.delete(
        url(wid, live), params={"confirm": "@maple.bakery"}, headers=headers
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == deletion.ACTIVE_ACCOUNT
    assert await jobs("purge_account_data") == []

    # Disconnected first (keeping its data), it can be removed.
    assert (await client.delete(url(wid, live), headers=headers)).status_code == 204
    [row] = await rows(
        engine, "SELECT status, deletion_requested_at FROM social_accounts WHERE id = :a", a=live
    )
    assert (row["status"], row["deletion_requested_at"]) == ("disconnected", None)
    mismatch = await client.delete(url(wid, live), params={"confirm": "maple"}, headers=headers)
    assert mismatch.status_code == 422
    removed = await client.delete(
        url(wid, live), params={"confirm": "maple.bakery"}, headers=headers
    )
    assert removed.status_code == 204

    # A sandbox can be removed while connected.
    sandbox = (await client.post(f"/v1/w/{wid}/dev/sandbox/accounts", headers=headers)).json()
    removed = await client.delete(
        url(wid, sandbox["id"]), params={"confirm": f"@{sandbox['username']}"}, headers=headers
    )
    assert removed.status_code == 204
    assert [j["args"]["account_id"] for j in await jobs("purge_account_data")] == [
        live,
        sandbox["id"],
    ]
    listed = (await client.get(f"/v1/w/{wid}/social-accounts", headers=headers)).json()["items"]
    assert all(a["deleting"] and a["status"] == "disconnected" for a in listed)

    for account_id in (live, sandbox["id"]):
        assert (
            await run_account_purge(deps(app, media), uuid.UUID(wid), uuid.UUID(account_id))
        ).status == "purged"
    assert (await client.get(f"/v1/w/{wid}/social-accounts", headers=headers)).json()["items"] == []


async def test_an_account_being_deleted_cannot_be_reconnected_until_it_is_gone(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
    media: FakeMedia,
    queue: None,
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    connected = await connect(client, clerk, clerk_id, wid)
    account = connected.json()
    response = await client.delete(
        url(wid, account["id"]),
        params={"delete_data": "true", "confirm": f"@{account['username']}"},
        headers=clerk.headers(clerk_id),
    )
    assert response.status_code == 204

    again = await connect(client, clerk, clerk_id, wid, code="code-2")
    assert again.status_code == 409
    assert again.json()["detail"] == BEING_DELETED

    await run_account_purge(deps(app, media), uuid.UUID(wid), uuid.UUID(account["id"]))
    reconnected = await connect(client, clerk, clerk_id, wid, code="code-3")
    assert reconnected.status_code == 200
    assert reconnected.json()["id"] != account["id"]


async def test_the_sweep_requeues_every_account_still_deleting_and_alerts_when_overdue(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    _, wid, _ = await pro_workspace(client, clerk, engine)
    fresh = str(await make_account(engine, wid, platform_account_id="17841400000000009"))
    stuck = str(await make_account(engine, wid, platform_account_id="17841400000000010"))
    now = datetime.now(UTC)
    for account_id, asked in (
        (fresh, now - timedelta(minutes=5)),
        (stuck, now - timedelta(hours=7)),
    ):
        await execute(
            engine,
            "UPDATE social_accounts SET status = 'disconnected', deletion_requested_at = :t"
            " WHERE id = :a",
            t=asked,
            a=account_id,
        )
    await sweep_all(app.state.sessionmaker, now)
    assert sorted(j["args"]["account_id"] for j in await jobs("purge_account_data")) == sorted(
        [fresh, stuck]
    )
    await sweep_all(app.state.sessionmaker, now)  # a waiting purge isn't queued twice
    assert len(await jobs("purge_account_data")) == 2


# ---------------------------------------------------------------- Meta's data-deletion callback


APP_SCOPED_ID = "26000000000000077"


def signed_form(user_id: str) -> dict[str, str]:
    payload = {"algorithm": "HMAC-SHA256", "user_id": user_id, "issued_at": 1790000000}
    return {"signed_request": sign_request(payload, IG_APP_SECRET)}


async def test_meta_deletion_purges_the_users_accounts_in_every_workspace(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    media: FakeMedia,
    queue: None,
) -> None:
    """The same Instagram account, disconnected in one workspace (its data kept) and connected in
    another: both are disconnected and purged; the request goes received → processing → failed
    (a purge is retried) → processing → completed once the last purge finishes."""
    _, first = await sign_in(client, clerk, email="first@example.com")
    second_clerk, second = await sign_in(client, clerk, email="second@example.com")
    w1, w2 = first["workspaces"][0]["id"], second["workspaces"][0]["id"]
    old = str(await make_account(engine, w1, platform_account_id="17841400000000011"))
    await execute(engine, "UPDATE social_accounts SET status = 'disconnected' WHERE id = :a", a=old)
    live = str(await make_account(engine, w2, platform_account_id="17841400000000011"))
    bystander = str(
        await make_account(
            engine, w2, platform_account_id="17841400000000012", username="someone.else"
        )
    )
    await execute(
        engine,
        "UPDATE social_accounts SET app_scoped_id = :s WHERE id IN (:a, :b)",
        s=APP_SCOPED_ID,
        a=old,
        b=live,
    )
    await seed_account(engine, w1, old)
    await seed_account(engine, w2, live)
    await seed_account(engine, w2, bystander)
    bystander_before = await owned_counts(engine, w2, bystander)
    await execute(
        engine,
        "INSERT INTO webhook_events (provider, dedupe_key, event_type, platform_account_id,"
        " workspace_id, payload, status) VALUES ('instagram', 'ig:x', 'message',"
        " '17841400000000011', :w, '{}', 'processed')",
        w=w2,
    )

    response = await client.post("/webhooks/meta/data-deletion", data=signed_form(APP_SCOPED_ID))
    assert response.status_code == 200
    code = response.json()["confirmation_code"]

    async def status() -> dict[str, Any]:
        answer = await client.get(f"/v1/data-deletion/{code}")
        assert answer.status_code == 200
        return dict(answer.json())

    assert (await status())["status"] == "received"

    deps_ = deps_from(app.state.http, app.state.settings)
    assert await delete_user_data(app.state.sessionmaker, app.state.redis, deps_, code) is True
    assert (await status())["status"] == "processing"
    marked = await rows(
        engine,
        "SELECT id, status, access_token_enc, deletion_requested_at, deletion_requested_by_user_id"
        " FROM social_accounts WHERE id IN (:a, :b)",
        a=old,
        b=live,
    )
    assert all(
        (r["status"], r["access_token_enc"], r["deletion_requested_by_user_id"])
        == ("disconnected", None, None)
        and r["deletion_requested_at"] is not None
        for r in marked
    )
    assert len(marked) == 2
    assert sorted(j["args"]["account_id"] for j in await jobs("purge_account_data")) == sorted(
        [old, live]
    )
    assert await rows(engine, "SELECT id FROM webhook_events") == []
    notes = (
        await client.get(f"/v1/w/{w2}/notifications", headers=clerk.headers(second_clerk))
    ).json()
    assert [n["type"] for n in notes["items"]] == ["account_disconnected"]

    # The first purge finishes: another account is still waiting.
    assert (
        await run_account_purge(deps(app, media), uuid.UUID(w1), uuid.UUID(old))
    ).status == "purged"
    assert (await status())["status"] == "processing"

    # The second fails (Cloudinary down) and is retried.
    photo = await make_asset(engine, workspace_id=w2, purpose="inbound")
    thread = await make_thread(engine, workspace_id=w2, account_id=live)
    await attach(engine, thread.message_ids[0], [photo])
    media.fail = 1
    with pytest.raises(deletion.AccountPurgeBlocked):
        await run_account_purge(deps(app, media), uuid.UUID(w2), uuid.UUID(live))
    assert (await status())["status"] == "failed"

    result = await run_account_purge(deps(app, media), uuid.UUID(w2), uuid.UUID(live))
    assert result.status == "purged"
    done = await status()
    assert done["status"] == "completed"
    assert done["completed_at"] is not None

    assert (
        await rows(engine, "SELECT id FROM social_accounts WHERE id IN (:a, :b)", a=old, b=live)
        == []
    )
    assert await owned_counts(engine, w2, bystander) == bystander_before
    assert await delete_user_data(app.state.sessionmaker, app.state.redis, deps_, code) is False


async def test_a_meta_request_with_nothing_left_completes_at_once(
    app: FastAPI, client: httpx.AsyncClient, queue: None
) -> None:
    response = await client.post(
        "/webhooks/meta/data-deletion", data=signed_form("26000000000000099")
    )
    code = response.json()["confirmation_code"]
    deps_ = deps_from(app.state.http, app.state.settings)
    assert await delete_user_data(app.state.sessionmaker, app.state.redis, deps_, code) is True
    status = (await client.get(f"/v1/data-deletion/{code}")).json()
    assert status["status"] == "completed"
