"""C-165 phase B: create_post, update_post and cancel_post through the SDK client against the
mounted app: drafts, the preview and the confirmed call, the app's 1 minute lead, publish now,
Free saving drafts only, the workspace mode, idempotency, the caps, the owner notification and
the audit mirror."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.plans import ENTITLEMENTS
from socialhood.errors import ApiError
from socialhood.mcp import confirmations, limits
from socialhood.mcp.idempotency import WriteGuard
from socialhood.mcp.principal import McpPrincipal
from socialhood.models.identity import Role
from socialhood.models.mcp import CredentialKind
from socialhood.security import ratelimit
from socialhood.services.scheduled_posts import views
from tests.support.api import Clerk
from tests.support.automation_api import set_plan
from tests.support.inbox import make_account, make_asset
from tests.support.ingest import jobs
from tests.support.mcp import confirm, connect, error_of, make_key, structured
from tests.support.publishing import make_posting_slot, make_scheduled_post
from tests.support.sending import Setup, clean_outbox, workspace_with_thread

WRITE_SCOPES = ("posts:read", "posts:write", "media:write")


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


@pytest.fixture
async def key(client: httpx.AsyncClient, setup: Setup) -> str:
    made, _ = await make_key(client, setup, *WRITE_SCOPES)
    return made


async def call(app: FastAPI, key: str, name: str, args: dict[str, Any]) -> Any:
    async with connect(app, key) as mcp:
        return await mcp.call_tool(name, args)


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def image(engine: AsyncEngine, setup: Setup) -> str:
    return str(await make_asset(engine, workspace_id=setup.wid, purpose="post", height=1350))


def at(**delta: float) -> str:
    return (datetime.now(UTC) + timedelta(**delta)).isoformat()


def post_args(setup: Setup, media: str, **values: Any) -> dict[str, Any]:
    return {
        "accounts": [setup.account_id],
        "media_ids": [media],
        "caption": "Linen shirts are back #summer",
        **values,
    }


async def test_a_draft_is_saved_without_confirmation(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    result = structured(
        await call(mcp_app, key, "create_post", post_args(setup, media, when="draft"))
    )
    assert (result["status"], result["preview"], result["ready"]) == ("draft", False, True)
    assert result["post_id"]
    assert result["dashboard_url"].endswith(f"/schedule/{result['post_id']}")
    assert result["media_ids"] == [media]
    [audit] = await rows(engine, "SELECT * FROM audit_events WHERE action = 'post.created'")
    assert audit["actor_label"].startswith("Asha")
    assert " via " in audit["actor_label"]  # the AI app (its clientInfo, else its User-Agent)
    assert audit["detail"]["via"] == "mcp"
    # A draft tells no one: only scheduling notifies the team.
    assert await rows(engine, "SELECT 1 FROM notifications WHERE type = 'ai_post_change'") == []


async def test_scheduling_is_previewed_then_confirmed(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    when = at(days=2)
    args = post_args(setup, media, when=when)

    preview = structured(await call(mcp_app, key, "create_post", args))
    assert preview["preview"] is True
    assert preview["post_id"] is None
    assert "UTC)" in preview["publish_at"]  # the resolved time, local and UTC
    assert preview["ready"] is True
    assert "confirmed: true" in preview["next_step"]
    assert await rows(engine, "SELECT 1 FROM scheduled_posts") == []  # nothing stored
    assert await rows(engine, "SELECT 1 FROM audit_events WHERE action LIKE 'post.%'") == []

    assert preview["confirmation_token"]
    done = structured(
        await call(
            mcp_app,
            key,
            "create_post",
            {**args, "confirmed": True, "confirmation_token": preview["confirmation_token"]},
        )
    )
    assert (done["status"], done["preview"], done["confirmation_token"]) == (
        "scheduled",
        False,
        None,
    )
    [post] = await rows(engine, "SELECT status FROM scheduled_posts")
    assert post["status"] == "scheduled"
    [note] = await rows(engine, "SELECT * FROM notifications WHERE type = 'ai_post_change'")
    assert " scheduled a" in note["title"]
    assert note["link"] == f"/schedule/{done['post_id']}"
    [audit] = await rows(engine, "SELECT * FROM audit_events WHERE action = 'post.scheduled'")
    assert audit["target_id"] == done["post_id"]


async def test_the_same_key_returns_the_same_post(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    args = post_args(setup, media, when=at(days=2), idempotency_key="retry-0001")
    token = structured(await call(mcp_app, key, "create_post", args))["confirmation_token"]
    args = {**args, "confirmed": True, "confirmation_token": token}
    first = structured(await call(mcp_app, key, "create_post", args))
    again = structured(await call(mcp_app, key, "create_post", args))
    assert again == {**first, "duplicate_of_previous_call": True}
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1
    assert len(await rows(engine, "SELECT 1 FROM notifications WHERE type = 'ai_post_change'")) == 1
    # A preview isn't stored: the same key can still do the real thing.
    other = post_args(setup, media, when=at(days=3), idempotency_key="retry-0002")
    done = structured(await confirm(mcp_app, key, "create_post", other))
    assert done["status"] == "scheduled"
    assert done["duplicate_of_previous_call"] is False


async def test_a_token_runs_once_and_a_retry_with_its_key_replays(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    args = post_args(setup, media, when=at(days=2), idempotency_key="once-0001")
    token = structured(await call(mcp_app, key, "create_post", args))["confirmation_token"]
    args = {**args, "confirmed": True, "confirmation_token": token}
    first = structured(await call(mcp_app, key, "create_post", args))
    again = structured(await call(mcp_app, key, "create_post", args))
    assert again == {**first, "duplicate_of_previous_call": True}
    other_key = error_of(
        await call(mcp_app, key, "create_post", {**args, "idempotency_key": "once-0002"})
    )
    assert other_key["field_errors"][0]["field"] == "confirmation_token"
    assert "already been used" in other_key["message"]
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1


async def test_a_post_must_be_a_minute_ahead_as_in_the_app(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    for soon in (at(seconds=20), at(days=-1)):
        error = error_of(
            await call(
                mcp_app,
                key,
                "create_post",
                post_args(setup, media, when=soon, confirmed=True),
            )
        )
        assert error["code"] == "validation_error", soon
        assert error["field_errors"][0]["field"] == "when"
        assert "at least 1 minute" in error["field_errors"][0]["message"]
    # Words that aren't a time, and a date no post is planned for, are field errors too.
    for unreadable in ("whenever", "9999-12-31 23:00"):
        error = error_of(
            await call(mcp_app, key, "create_post", post_args(setup, media, when=unreadable))
        )
        assert error["code"] == "validation_error", unreadable
        assert error["field_errors"][0]["field"] == "when"
    assert await rows(engine, "SELECT 1 FROM scheduled_posts") == []
    # Two minutes ahead is enough, as for a person in the composer (it was 5 for AI apps).
    near = structured(
        await call(mcp_app, key, "create_post", post_args(setup, media, when=at(minutes=2)))
    )
    assert near["preview"] is True
    phrase = structured(
        await call(mcp_app, key, "create_post", post_args(setup, media, when="tomorrow 7 pm"))
    )
    assert phrase["preview"] is True
    assert "7:00 pm" in phrase["publish_at"]


async def test_the_checklist_stops_scheduling_and_shows_on_drafts(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    error = error_of(
        await call(
            mcp_app,
            key,
            "create_post",
            {"accounts": [setup.account_id], "caption": "no media", "when": at(days=2)},
        )
    )
    assert error["code"] == "validation_error"
    assert any(f["field"] == "asset_ids" for f in error["field_errors"])
    draft = structured(
        await call(
            mcp_app,
            key,
            "create_post",
            {"accounts": [setup.account_id], "caption": "no media", "when": "draft"},
        )
    )
    assert draft["ready"] is False
    assert any(not c["ok"] and c["key"] == "media" for c in draft["checklist"])
    assert "checklist item" in draft["summary"]


async def test_next_free_slot_uses_the_accounts_posting_times(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    for weekday in range(7):
        await make_posting_slot(
            engine,
            workspace_id=setup.wid,
            account_id=setup.account_id,
            weekday=weekday,
            local_time=time(18, 0),
        )
    media = await image(engine, setup)
    result = structured(
        await confirm(mcp_app, key, "create_post", post_args(setup, media, when="next_free_slot"))
    )
    assert result["status"] == "scheduled"
    assert "18:00 UTC" in result["publish_at"] or "6:00 pm" in result["publish_at"]


async def test_free_saves_drafts_only(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    await set_plan(engine, setup.wid, "free")
    draft = structured(
        await call(mcp_app, key, "create_post", post_args(setup, media, when="draft"))
    )
    assert draft["status"] == "draft"
    error = error_of(
        await call(
            mcp_app, key, "create_post", post_args(setup, media, when=at(days=2), confirmed=True)
        )
    )
    assert (error["code"], error["entitlement"]) == ("entitlement_required", "ai_connections")
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1
    # cancel_post is a write: Free's mode doesn't admit it.
    refused = error_of(
        await call(mcp_app, key, "cancel_post", {"post_id": draft["post_id"], "confirmed": True})
    )
    assert refused["code"] == "entitlement_required"


async def test_a_workspace_set_to_drafts_refuses_scheduling(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET ai_connections_mode = 'read_drafts' WHERE id = :w"),
            {"w": setup.wid},
        )
    refused = error_of(
        await call(mcp_app, key, "create_post", post_args(setup, media, when=at(days=2)))
    )
    assert refused["code"] == "forbidden"
    assert "only read and prepare drafts" in refused["message"]
    saved = structured(
        await call(mcp_app, key, "create_post", post_args(setup, media, when="draft"))
    )
    assert saved["status"] == "draft"


async def test_update_and_cancel_a_scheduled_post(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    made = structured(
        await confirm(mcp_app, key, "create_post", post_args(setup, media, when=at(days=2)))
    )
    post_id = made["post_id"]

    preview = structured(
        await call(mcp_app, key, "update_post", {"post_id": post_id, "caption": "New words"})
    )
    assert preview["preview"] is True
    assert preview["caption"] == "New words"
    assert (await rows(engine, "SELECT caption FROM scheduled_posts"))[0][
        "caption"
    ] == "Linen shirts are back #summer"

    changed = structured(
        await call(
            mcp_app,
            key,
            "update_post",
            {
                "post_id": post_id,
                "caption": "New words",
                "confirmed": True,
                "confirmation_token": preview["confirmation_token"],
            },
        )
    )
    assert (changed["caption"], changed["status"]) == ("New words", "scheduled")
    assert changed["media_ids"] == [media]  # what wasn't sent is kept
    assert (await rows(engine, "SELECT caption FROM scheduled_posts"))[0]["caption"] == "New words"

    moved = structured(
        await confirm(mcp_app, key, "update_post", {"post_id": post_id, "when": at(days=5)})
    )
    assert moved["publish_at"] != made["publish_at"]
    too_soon = error_of(
        await call(
            mcp_app,
            key,
            "update_post",
            {"post_id": post_id, "when": at(minutes=1), "confirmed": True},
        )
    )
    assert too_soon["field_errors"][0]["field"] == "when"
    to_draft = error_of(
        await call(mcp_app, key, "update_post", {"post_id": post_id, "when": "draft"})
    )
    assert "cancel_post" in to_draft["field_errors"][0]["message"]

    preview = structured(await call(mcp_app, key, "cancel_post", {"post_id": post_id}))
    assert preview["preview"] is True
    assert (await rows(engine, "SELECT status FROM scheduled_posts"))[0]["status"] == "scheduled"
    canceled = structured(
        await call(
            mcp_app,
            key,
            "cancel_post",
            {
                "post_id": post_id,
                "confirmed": True,
                "confirmation_token": preview["confirmation_token"],
            },
        )
    )
    assert (canceled["status"], canceled["preview"]) == ("draft", False)
    assert (await rows(engine, "SELECT status FROM scheduled_posts"))[0]["status"] == "draft"
    again = structured(await call(mcp_app, key, "cancel_post", {"post_id": post_id}))
    assert "already a draft" in again["summary"]
    actions = {r["action"] for r in await rows(engine, "SELECT action FROM audit_events")}
    assert {"post.scheduled", "post.updated", "post.canceled"} <= actions
    titles = [r["title"] for r in await rows(engine, "SELECT title FROM notifications")]
    assert any("cancelled" in t for t in titles)


async def test_a_draft_given_a_time_is_scheduled_and_unknown_posts_are_not_found(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    draft = structured(
        await call(mcp_app, key, "create_post", post_args(setup, media, when="draft"))
    )
    scheduled = structured(
        await confirm(
            mcp_app, key, "update_post", {"post_id": draft["post_id"], "when": at(days=3)}
        )
    )
    assert scheduled["status"] == "scheduled"
    missing = error_of(
        await call(
            mcp_app,
            key,
            "update_post",
            {"post_id": "00000000-0000-4000-8000-000000000000", "caption": "x"},
        )
    )
    assert missing["code"] == "not_found"
    gone = error_of(
        await call(
            mcp_app,
            key,
            "cancel_post",
            {"post_id": "00000000-0000-4000-8000-000000000000", "confirmed": True},
        )
    )
    assert gone["code"] == "not_found"


async def test_the_daily_post_cap(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["mcp_posts_daily"], "max", 1)
    media = await image(engine, setup)
    first = structured(
        await confirm(mcp_app, key, "create_post", post_args(setup, media, when=at(days=2)))
    )
    assert first["status"] == "scheduled"
    error = error_of(
        await confirm(mcp_app, key, "create_post", post_args(setup, media, when=at(days=3)))
    )
    assert (error["code"], error["entitlement"], error["limit"]) == (
        "quota_exceeded",
        "mcp_posts_daily",
        1,
    )
    # Drafts and previews don't use the day's posts.
    structured(await call(mcp_app, key, "create_post", post_args(setup, media, when="draft")))
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 2


async def test_roles_and_scopes_gate_the_write_tools(
    client: httpx.AsyncClient,
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
) -> None:
    read_only_key, _ = await make_key(client, setup, "posts:read")
    async with connect(mcp_app, read_only_key) as mcp:
        names = {t.name for t in (await mcp.list_tools()).tools}
        refused = await mcp.call_tool("create_post", {"accounts": ["x"], "when": "draft"})
    assert "create_post" not in names
    assert "posts:write" in error_of(refused)["message"]
    async with connect(mcp_app, key) as mcp:
        assert "create_post" in {t.name for t in (await mcp.list_tools()).tools}
    async with engine.begin() as conn:  # the member is demoted: the key shrinks at once
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": setup.wid},
        )
    async with connect(mcp_app, key) as mcp:
        assert "create_post" not in {t.name for t in (await mcp.list_tools()).tools}
        error = error_of(await mcp.call_tool("create_post", {"accounts": ["x"], "when": "draft"}))
    assert error["code"] == "forbidden"


# ---------------------------------------------------------------- the server-checked preview


async def test_a_change_needs_the_preview_s_token_and_a_draft_doesn_t(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    when = at(days=2)
    refused = error_of(
        await call(mcp_app, key, "create_post", post_args(setup, media, when=when, confirmed=True))
    )
    assert refused["code"] == "validation_error"
    assert refused["field_errors"][0]["field"] == "confirmation_token"
    assert "preview" in refused["message"]
    assert await rows(engine, "SELECT 1 FROM scheduled_posts") == []
    # Saving a draft needs none, even with confirmed.
    draft = structured(
        await call(
            mcp_app, key, "create_post", post_args(setup, media, when="draft", confirmed=True)
        )
    )
    assert draft["status"] == "draft"
    # A token for another post time, or from another tool, is not this change's.
    token = structured(await call(mcp_app, key, "create_post", post_args(setup, media, when=when)))[
        "confirmation_token"
    ]
    moved = error_of(
        await call(
            mcp_app,
            key,
            "create_post",
            post_args(setup, media, when=at(days=3), confirmed=True, confirmation_token=token),
        )
    )
    assert moved["code"] == "validation_error"
    other_tool = error_of(
        await call(
            mcp_app,
            key,
            "update_post",
            {
                "post_id": draft["post_id"],
                "when": when,
                "confirmed": True,
                "confirmation_token": token,
            },
        )
    )
    assert other_tool["field_errors"][0]["field"] == "confirmation_token"
    made = structured(
        await confirm(mcp_app, key, "create_post", post_args(setup, media, when=when, caption="B"))
    )
    # update_post and cancel_post refuse a scheduled post's change without a token.
    for name, args in (
        ("update_post", {"post_id": made["post_id"], "caption": "C", "confirmed": True}),
        ("cancel_post", {"post_id": made["post_id"], "confirmed": True}),
    ):
        error = error_of(await call(mcp_app, key, name, args))
        assert error["field_errors"][0]["field"] == "confirmation_token"
    [row] = await rows(
        engine, "SELECT status, caption FROM scheduled_posts WHERE id = :i", i=made["post_id"]
    )
    assert (row["status"], row["caption"]) == ("scheduled", "B")


# ---------------------------------------------------------------- the minute's limit (C-169)


def one_a_minute(monkeypatch: pytest.MonkeyPatch, n: int = 1) -> None:
    monkeypatch.setitem(ratelimit.LIMITS, "mcp_posts", ratelimit.Limit("mcp_posts", n, 60))


async def day_used(app: FastAPI, setup: Setup) -> int:
    return await limits.used(app.state.redis, limits.POSTS, uuid.UUID(setup.wid), datetime.now(UTC))


async def test_the_21st_post_in_a_minute_is_refused_without_using_the_day(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    assert ratelimit.LIMITS["mcp_posts"].max_requests == 20
    assert ratelimit.LIMITS["mcp_posts"].window_s == 60
    for _ in range(20):  # the workspace's window, as twenty posts would leave it
        wait = await ratelimit.hit(mcp_app.state.redis, ratelimit.LIMITS["mcp_posts"], setup.wid)
        assert wait == 0
    media = await image(engine, setup)
    args = post_args(setup, media, when=at(days=2))
    # A preview still works: it doesn't count.
    token = structured(await call(mcp_app, key, "create_post", args))["confirmation_token"]
    error = error_of(
        await call(
            mcp_app,
            key,
            "create_post",
            {**args, "confirmed": True, "confirmation_token": token},
        )
    )
    assert error["code"] == "rate_limited"
    assert "20 posts a minute" in error["message"]
    assert "Try again in" in error["message"]
    assert await day_used(mcp_app, setup) == 0
    assert await rows(engine, "SELECT 1 FROM scheduled_posts") == []
    # The token comes first: a call without one isn't counted or told to wait.
    no_token = error_of(await call(mcp_app, key, "create_post", {**args, "confirmed": True}))
    assert no_token["code"] == "validation_error"


async def test_only_real_scheduling_counts_and_connections_share_the_limit(
    client: httpx.AsyncClient,
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one_a_minute(monkeypatch, 2)
    media = await image(engine, setup)
    second_account = await make_account(engine, setup.wid, username="cafe.pune")
    other, _ = await make_key(client, setup, *WRITE_SCOPES, name="Other laptop")
    # Previews and drafts don't count.
    for _ in range(3):
        preview = await call(mcp_app, key, "create_post", post_args(setup, media, when=at(days=2)))
        assert structured(preview)["preview"] is True
        saved = await call(mcp_app, key, "create_post", post_args(setup, media, when="draft"))
        assert structured(saved)["status"] == "draft"
    draft_id = structured(saved)["post_id"]
    # One post to two accounts counts once, from one connection...
    two = post_args(setup, media, when=at(days=2), caption="Both")
    two["accounts"] = [setup.account_id, str(second_account)]
    assert structured(await confirm(mcp_app, key, "create_post", two))["status"] == "scheduled"
    assert await day_used(mcp_app, setup) == 1
    # ...a draft newly scheduled counts, from the other...
    change = {"post_id": draft_id, "when": at(days=3)}
    assert structured(await confirm(mcp_app, other, "update_post", change))["status"] == "scheduled"
    assert await day_used(mcp_app, setup) == 2
    # ...and that's the workspace's two, whichever connection asks.
    third = post_args(setup, media, when=at(days=4), caption="Third")
    for by in (key, other):
        error = error_of(await confirm(mcp_app, by, "create_post", third))
        assert error["code"] == "rate_limited"
    assert await day_used(mcp_app, setup) == 2
    # Changing a post already scheduled isn't new scheduling.
    moved = {"post_id": draft_id, "caption": "New words"}
    assert structured(await confirm(mcp_app, key, "update_post", moved))["caption"] == "New words"


async def test_a_post_the_checklist_refuses_gives_its_places_back(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one_a_minute(monkeypatch)
    media = await image(engine, setup)
    args = post_args(setup, media, when=at(days=2))
    token = structured(await call(mcp_app, key, "create_post", args))["confirmation_token"]
    # The account fills up between the preview and the yes.
    monkeypatch.setattr(views, "PUBLISHING_LIMIT", 1)
    await make_scheduled_post(
        engine,
        workspace_id=setup.wid,
        account_ids=[setup.account_id],
        status="scheduled",
        publish_at=datetime.fromisoformat(args["when"]) - timedelta(hours=1),
    )
    full = error_of(
        await call(
            mcp_app,
            key,
            "create_post",
            {**args, "confirmed": True, "confirmation_token": token},
        )
    )
    assert full["code"] == "validation_error"
    assert await day_used(mcp_app, setup) == 0
    monkeypatch.undo()
    one_a_minute(monkeypatch)
    # Its place in the minute came back too: the next post goes.
    assert structured(await confirm(mcp_app, key, "create_post", args))["status"] == "scheduled"


async def test_the_month_s_scheduled_posts_still_apply(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["scheduled_posts_monthly"], "max", 1)
    media = await image(engine, setup)
    first = post_args(setup, media, when=at(days=2))
    assert structured(await confirm(mcp_app, key, "create_post", first))["status"] == "scheduled"
    error = error_of(
        await call(mcp_app, key, "create_post", post_args(setup, media, when=at(days=3)))
    )
    assert (error["code"], error["entitlement"]) == ("quota_exceeded", "scheduled_posts_monthly")
    assert await day_used(mcp_app, setup) == 1


# ---------------------------------------------------------------- Instagram's 24 hour limit


async def test_an_account_with_a_full_24_hours_is_refused_per_account_by_the_checklist(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(views, "PUBLISHING_LIMIT", 1)
    media = await image(engine, setup)
    roomy = await make_account(engine, setup.wid, username="cafe.pune")
    when = datetime.now(UTC) + timedelta(days=2)
    await make_scheduled_post(
        engine,
        workspace_id=setup.wid,
        account_ids=[setup.account_id],
        status="scheduled",
        publish_at=when - timedelta(hours=2),
    )
    args = post_args(setup, media, when=when.isoformat())
    args["accounts"] = [str(roomy), setup.account_id]
    error = error_of(await call(mcp_app, key, "create_post", args))
    assert error["code"] == "validation_error"
    # One line, for the full account, not the one with room.
    [line] = [e["message"] for e in error["field_errors"]]
    assert "already has 1 posts" in line
    assert "cafe.pune" not in line
    # The same rule for a draft given a time.
    draft = post_args(setup, media, when="draft", accounts=[setup.account_id])
    draft_id = structured(await call(mcp_app, key, "create_post", draft))["post_id"]
    moved = error_of(
        await call(mcp_app, key, "update_post", {"post_id": draft_id, "when": when.isoformat()})
    )
    assert moved["field_errors"][0]["field"] == "targets.0"
    # The other account alone has room.
    alone = post_args(setup, media, when=when.isoformat(), accounts=[str(roomy)])
    assert structured(await confirm(mcp_app, key, "create_post", alone))["status"] == "scheduled"
    assert views.DEFAULT_PUBLISHING_LIMIT == 50


async def test_ai_apps_get_the_apps_one_minute_through_the_queue_and_when_editing(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    """Owner 2026-11-11: AI apps schedule by the app's own rule, 1 minute ahead (it was 5)."""
    # A posting time 3 minutes from now, every day: far enough ahead for an AI app to take today's.
    async with engine.connect() as conn:
        zone = (
            await conn.execute(
                text("SELECT timezone FROM workspaces WHERE id = :w"), {"w": setup.wid}
            )
        ).scalar_one()
    soon = (datetime.now(UTC) + timedelta(minutes=3)).astimezone(ZoneInfo(zone))
    for weekday in range(7):
        await make_posting_slot(
            engine,
            workspace_id=setup.wid,
            account_id=setup.account_id,
            weekday=weekday,
            local_time=soon.time().replace(second=0, microsecond=0),
        )
    media = await image(engine, setup)
    queued = structured(
        await confirm(mcp_app, key, "create_post", post_args(setup, media, when="next_free_slot"))
    )
    post_id = queued["post_id"]
    async with engine.connect() as conn:
        at = (
            await conn.execute(
                text("SELECT publish_at FROM scheduled_posts WHERE id = :p"), {"p": post_id}
            )
        ).scalar_one()
    assert at - datetime.now(UTC) < timedelta(minutes=4)

    # A post due in 2 minutes can still be edited, as in the app.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE scheduled_posts SET publish_at = now() + interval '2 minutes' WHERE id = :p"
            ),
            {"p": post_id},
        )
    changed = structured(
        await confirm(mcp_app, key, "update_post", {"post_id": post_id, "caption": "New words"})
    )
    assert (changed["caption"], changed["status"]) == ("New words", "scheduled")


# ---------------------------------------------------------------- audit findings (2026-11-11)


async def test_a_second_change_to_the_same_post_is_told_too(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    made = structured(
        await confirm(mcp_app, key, "create_post", post_args(setup, media, when=at(days=2)))
    )
    for words in ("First change", "Second change"):
        change = {"post_id": made["post_id"], "caption": words}
        assert structured(await confirm(mcp_app, key, "update_post", change))["caption"] == words
    told = await rows(
        engine,
        "SELECT title FROM notifications WHERE type = 'ai_post_change' AND title LIKE :t",
        t="% changed %",
    )
    assert len(told) == 2  # the time didn't move, and each change still reached the team


async def test_the_same_post_asked_for_again_is_a_new_post_and_a_retry_is_not(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = await image(engine, setup)
    args = post_args(setup, media, when=at(days=2))
    token = structured(await call(mcp_app, key, "create_post", args))["confirmation_token"]
    confirmed = {**args, "confirmed": True, "confirmation_token": token}
    first = structured(await call(mcp_app, key, "create_post", confirmed))
    # The answer was lost and the app sends the same call again: the first result, no second post.
    retry = structured(await call(mcp_app, key, "create_post", confirmed))
    assert retry == {**first, "duplicate_of_previous_call": True}
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1
    # The member asks for the same post once more: a new preview, so a new request and a post.
    monkeypatch.setattr(confirmations, "TTL_S", confirmations.TTL_S + 1)  # a later preview's token
    second = structured(await confirm(mcp_app, key, "create_post", args))
    assert second["duplicate_of_previous_call"] is False
    assert second["post_id"] != first["post_id"]
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 2


async def test_a_second_identical_call_while_the_first_runs_is_refused(
    mcp_app: FastAPI, setup: Setup
) -> None:
    principal = McpPrincipal(
        workspace_id=uuid.UUID(setup.wid),
        user_id=uuid.uuid4(),
        role=Role.OWNER,
        scopes=frozenset(),
        credential=CredentialKind.API_KEY,
        credential_id=uuid.uuid4(),
        credential_label="API key",
    )

    def guard(tool: str, arguments: dict[str, Any], window: int | None) -> WriteGuard:
        return WriteGuard(mcp_app.state.redis, principal, tool, arguments, window)

    draft = {"when": "draft", "caption": "Linen shirts"}
    for arguments in (draft, {**draft, "idempotency_key": "running-0001"}):
        first = guard("create_post", arguments, 900)
        assert await first.begin() is None  # it runs
        with pytest.raises(ApiError) as refused:
            await guard("create_post", arguments, 900).begin()
        assert refused.value.code == "conflict"
        assert "still running" in (refused.value.detail or "")
        await first.complete({"summary": "Saved a draft"})
        # Once it finished, the retry gets its result.
        assert await guard("create_post", arguments, 900).begin() == {"summary": "Saved a draft"}
    # A failed call frees its place: the retry runs.
    failed = guard("create_post", {"when": "draft", "caption": "Other"}, 900)
    assert await failed.begin() is None
    await failed.release()
    assert await guard("create_post", {"when": "draft", "caption": "Other"}, 900).begin() is None
    # A tool without a window, called without a key: identical calls are separate requests.
    for _ in range(2):
        assert await guard("start_media_upload", {"kind": "video"}, None).begin() is None


async def test_per_account_captions_and_collaborators_through_mcp(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    second = str(await make_account(engine, setup.wid, username="cafe.pune"))
    both = post_args(setup, media, when="draft", accounts=[setup.account_id, second])
    saved = structured(
        await call(
            mcp_app,
            key,
            "create_post",
            {
                **both,
                "per_account_captions": {" @cafe.pune ": "Pune only"},
                "collaborators": [" friend.shop "],
            },
        )
    )
    assert saved["status"] == "draft"
    assert [c.lstrip("@") for c in saved["collaborators"]] == ["friend.shop"]
    targets = await rows(
        engine, "SELECT social_account_id, caption_override FROM scheduled_post_targets"
    )
    assert {str(t["social_account_id"]): t["caption_override"] for t in targets} == {
        setup.account_id: None,
        second: "Pune only",
    }
    # Over the app's own limits: field errors, not a crash.
    eleven = {f"@account{i}": "x" for i in range(11)}
    refusals: list[tuple[dict[str, Any], str]] = [
        ({"per_account_captions": eleven}, "per_account_captions"),
        ({"per_account_captions": {"@cafe.pune": "x" * 63_207}}, "per_account_captions"),
        ({"per_account_captions": {" ": "x"}}, "per_account_captions"),
        ({"collaborators": ["a" * 32]}, "collaborators.0"),
        ({"collaborators": [" "]}, "collaborators.0"),
        ({"accounts": [" "]}, "accounts.0"),
    ]
    for extra, field in refusals:
        error = error_of(await call(mcp_app, key, "create_post", {**both, **extra}))
        assert error["code"] == "validation_error", extra
        assert error["field_errors"][0]["field"].startswith(field), extra
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1


async def test_update_post_keeps_the_reel_options_that_were_not_sent(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    video = str(
        await make_asset(
            engine,
            workspace_id=setup.wid,
            purpose="post",
            resource_type="video",
            fmt="mp4",
            height=1920,
        )
    )
    reel = structured(
        await call(
            mcp_app,
            key,
            "create_post",
            {
                "accounts": [setup.account_id],
                "media_ids": [video],
                "caption": "Summer reel",
                "when": "draft",
                "reel_options": {
                    "share_to_feed": False,
                    "audio_name": "Old tune",
                    "cover_offset_ms": 1500,
                },
            },
        )
    )
    assert reel["format"] == "reel"
    # A draft is changed at once: no preview, no token.
    changed = structured(
        await call(
            mcp_app,
            key,
            "update_post",
            {"post_id": reel["post_id"], "reel_options": {"audio_name": "New tune"}},
        )
    )
    assert changed["preview"] is False
    [row] = await rows(
        engine,
        "SELECT share_to_feed, audio_name, cover_offset_ms FROM scheduled_posts WHERE id = :i",
        i=reel["post_id"],
    )
    assert (row["share_to_feed"], row["audio_name"], row["cover_offset_ms"]) == (
        False,
        "New tune",
        1500,
    )


async def test_another_workspaces_posts_media_and_accounts_are_not_found(
    client: httpx.AsyncClient,
    clerk: Clerk,
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
) -> None:
    other = await workspace_with_thread(client, clerk, engine, email="other@example.com")
    theirs = await make_scheduled_post(
        engine,
        workspace_id=other.wid,
        account_ids=[other.account_id],
        status="scheduled",
        publish_at=datetime.now(UTC) + timedelta(days=2),
    )
    attempts: list[tuple[str, dict[str, Any]]] = [
        ("update_post", {"caption": "Mine now"}),
        ("update_post", {"when": "now"}),
        ("cancel_post", {}),
        ("cancel_post", {"confirmed": True}),
    ]
    for name, extra in attempts:
        error = error_of(await call(mcp_app, key, name, {"post_id": str(theirs.id), **extra}))
        assert error["code"] == "not_found", (name, extra)
    media = await image(engine, setup)
    their_media = str(await make_asset(engine, workspace_id=other.wid, purpose="post", height=1350))
    account = error_of(
        await call(
            mcp_app,
            key,
            "create_post",
            post_args(setup, media, when="draft", accounts=[other.account_id]),
        )
    )
    assert account["code"] == "not_found"
    asset = error_of(
        await call(mcp_app, key, "create_post", post_args(setup, their_media, when="draft"))
    )
    assert asset["code"] == "validation_error"
    assert any(f["field"].startswith("asset_ids") for f in asset["field_errors"])
    [row] = await rows(engine, "SELECT status FROM scheduled_posts WHERE id = :i", i=theirs.id)
    assert row["status"] == "scheduled"
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1  # theirs, untouched


# ---------------------------------------------------------------- publish now (owner 2026-11-11)


async def test_publish_now_is_previewed_then_published_through_the_apps_own_path(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    media = await image(engine, setup)
    args = post_args(setup, media, when="now")
    refused = error_of(await call(mcp_app, key, "create_post", {**args, "confirmed": True}))
    assert refused["field_errors"][0]["field"] == "confirmation_token"
    preview = structured(await call(mcp_app, key, "create_post", args))
    assert preview["preview"] is True
    assert "publishes immediately to " in preview["summary"]
    assert "cannot be undone" in preview["summary"]
    assert preview["ready"] is True
    assert all(c["key"] != "publish_at" for c in preview["checklist"])
    assert "confirmed: true" in preview["next_step"]
    assert await rows(engine, "SELECT 1 FROM scheduled_posts") == []
    assert await jobs("publish_target") == []
    assert await day_used(mcp_app, setup) == 0

    confirmed = {**args, "confirmed": True, "confirmation_token": preview["confirmation_token"]}
    done = structured(await call(mcp_app, key, "create_post", confirmed))
    assert (done["preview"], done["status"], done["summary"]) == (
        False,
        "scheduled",
        "Publishing now",
    )
    [post] = await rows(engine, "SELECT status, publish_at FROM scheduled_posts")
    assert post["status"] == "scheduled"
    assert abs(post["publish_at"] - datetime.now(UTC)) < timedelta(seconds=30)
    # Its target went to the publishing jobs at once, as the app's own Publish now does.
    [target] = await rows(engine, "SELECT id FROM scheduled_post_targets")
    queued = await jobs("publish_target")
    assert [j["args"]["target_id"] for j in queued] == [str(target["id"])]
    assert await day_used(mcp_app, setup) == 1  # a post of the day and of the minute
    [note] = await rows(engine, "SELECT * FROM notifications WHERE type = 'ai_post_change'")
    assert " published a" in note["title"]
    assert note["title"].endswith(" now")
    assert note["link"] == f"/schedule/{done['post_id']}"
    [audit] = await rows(engine, "SELECT * FROM audit_events WHERE action = 'post.published'")
    assert audit["target_id"] == done["post_id"]
    # The token ran once: the same call under another key publishes nothing more.
    again = error_of(
        await call(mcp_app, key, "create_post", {**confirmed, "idempotency_key": "now-0002"})
    )
    assert again["field_errors"][0]["field"] == "confirmation_token"
    assert "already been used" in again["message"]
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1
    assert len(await jobs("publish_target")) == 1


async def test_publish_now_needs_a_paid_plan_and_full_mode_and_counts_against_the_caps(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = await image(engine, setup)
    draft = structured(
        await call(mcp_app, key, "create_post", post_args(setup, media, when="draft"))
    )
    change = {"post_id": draft["post_id"], "when": "now"}
    both = (("create_post", post_args(setup, media, when="now")), ("update_post", change))
    await set_plan(engine, setup.wid, "free")
    for name, args in both:
        error = error_of(await call(mcp_app, key, name, args))
        assert (error["code"], error["entitlement"]) == (
            "entitlement_required",
            "ai_connections",
        ), name
    await set_plan(engine, setup.wid, "max")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET ai_connections_mode = 'read_drafts' WHERE id = :w"),
            {"w": setup.wid},
        )
    for name, args in both:
        error = error_of(await call(mcp_app, key, name, args))
        assert error["code"] == "forbidden", name
        assert "only read and prepare drafts" in error["message"]
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET ai_connections_mode = 'full' WHERE id = :w"),
            {"w": setup.wid},
        )
    # A draft published now: previewed first, then counted like any post of the day.
    monkeypatch.setitem(ENTITLEMENTS["mcp_posts_daily"], "max", 1)
    preview = structured(await call(mcp_app, key, "update_post", change))
    assert preview["preview"] is True
    assert "cannot be undone" in preview["summary"]
    assert (await rows(engine, "SELECT status FROM scheduled_posts"))[0]["status"] == "draft"
    assert await day_used(mcp_app, setup) == 0
    done = structured(
        await call(
            mcp_app,
            key,
            "update_post",
            {**change, "confirmed": True, "confirmation_token": preview["confirmation_token"]},
        )
    )
    assert done["summary"] == "Publishing now"
    assert await day_used(mcp_app, setup) == 1
    # The day's one post is used: another publish now is refused and nothing is created.
    second = post_args(setup, media, when="now", caption="Second")
    error = error_of(await confirm(mcp_app, key, "create_post", second))
    assert (error["code"], error["entitlement"]) == ("quota_exceeded", "mcp_posts_daily")
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1
