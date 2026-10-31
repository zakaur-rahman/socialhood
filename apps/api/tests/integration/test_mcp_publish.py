"""C-165 phase B: create_post, update_post and cancel_post through the SDK client against the
mounted app: drafts, the preview and the confirmed call, the 5 minute lead, Free saving drafts
only, the workspace mode, idempotency, the daily cap, the owner notification and the audit
mirror."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.plans import ENTITLEMENTS
from tests.support.automation_api import set_plan
from tests.support.inbox import make_asset
from tests.support.mcp import connect, error_of, make_key, structured
from tests.support.publishing import make_posting_slot
from tests.support.sending import Setup, clean_outbox

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

    done = structured(await call(mcp_app, key, "create_post", {**args, "confirmed": True}))
    assert (done["status"], done["preview"]) == ("scheduled", False)
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
    args = post_args(setup, media, when=at(days=2), confirmed=True, idempotency_key="retry-0001")
    first = structured(await call(mcp_app, key, "create_post", args))
    again = structured(await call(mcp_app, key, "create_post", args))
    assert again == {**first, "duplicate_of_previous_call": True}
    assert len(await rows(engine, "SELECT 1 FROM scheduled_posts")) == 1
    assert len(await rows(engine, "SELECT 1 FROM notifications WHERE type = 'ai_post_change'")) == 1
    # A preview isn't stored: the same key can still do the real thing.
    other = post_args(setup, media, when=at(days=3), idempotency_key="retry-0002")
    assert structured(await call(mcp_app, key, "create_post", other))["preview"] is True
    done = structured(await call(mcp_app, key, "create_post", {**other, "confirmed": True}))
    assert done["status"] == "scheduled"
    assert done["duplicate_of_previous_call"] is False


async def test_a_post_must_be_five_minutes_ahead(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    media = await image(engine, setup)
    for soon in (at(minutes=2), at(days=-1), "now"):
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
    unreadable = error_of(
        await call(mcp_app, key, "create_post", post_args(setup, media, when="whenever"))
    )
    assert unreadable["field_errors"][0]["field"] == "when"
    assert await rows(engine, "SELECT 1 FROM scheduled_posts") == []
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
        await call(
            mcp_app,
            key,
            "create_post",
            post_args(setup, media, when="next_free_slot", confirmed=True),
        )
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
        await call(
            mcp_app,
            key,
            "create_post",
            post_args(setup, media, when=at(days=2), confirmed=True),
        )
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
            {"post_id": post_id, "caption": "New words", "confirmed": True},
        )
    )
    assert (changed["caption"], changed["status"]) == ("New words", "scheduled")
    assert changed["media_ids"] == [media]  # what wasn't sent is kept
    assert (await rows(engine, "SELECT caption FROM scheduled_posts"))[0]["caption"] == "New words"

    moved = structured(
        await call(
            mcp_app,
            key,
            "update_post",
            {"post_id": post_id, "when": at(days=5), "confirmed": True},
        )
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
        await call(mcp_app, key, "cancel_post", {"post_id": post_id, "confirmed": True})
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
        await call(
            mcp_app,
            key,
            "update_post",
            {"post_id": draft["post_id"], "when": at(days=3), "confirmed": True},
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
    monkeypatch.setitem(ENTITLEMENTS["mcp_posts_daily"], "pro", 1)
    media = await image(engine, setup)
    first = structured(
        await call(
            mcp_app, key, "create_post", post_args(setup, media, when=at(days=2), confirmed=True)
        )
    )
    assert first["status"] == "scheduled"
    error = error_of(
        await call(
            mcp_app, key, "create_post", post_args(setup, media, when=at(days=3), confirmed=True)
        )
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
