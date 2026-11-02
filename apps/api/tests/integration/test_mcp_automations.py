"""C-169: list_instagram_posts, create_automation and update_automation through the SDK client
against the mounted app: the preview (nothing stored) and the confirmed call, “latest” as the
newest synced post, an ambiguous account, the plan, role and mode gates, turning on within and
over the plan's active limit, overlaps, the notification and audit mirror, idempotency, and
update_automation refusing what it can't edit safely."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.plans import ENTITLEMENTS
from socialhood.mcp import confirmations
from tests.support.automation_api import set_plan
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_account
from tests.support.mcp import confirm, connect, error_of, make_key, structured
from tests.support.sending import Setup, clean_outbox

SCOPES = ("automations:read", "automations:write", "automations:create", "posts:read")


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


@pytest.fixture
async def key(client: httpx.AsyncClient, setup: Setup) -> str:
    made, _ = await make_key(client, setup, *SCOPES)
    return made


async def call(app: FastAPI, key: str, name: str, args: dict[str, Any]) -> Any:
    async with connect(app, key) as mcp:
        return await mcp.call_tool(name, args)


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def two_posts(engine: AsyncEngine, setup: Setup) -> tuple[uuid.UUID, uuid.UUID]:
    """(older, newer) synced posts of the setup's account."""
    now = datetime.now(UTC)
    older = await make_media_item(
        engine,
        workspace_id=setup.wid,
        account_id=setup.account_id,
        caption="Last week's drop",
        posted_at=now - timedelta(days=6),
    )
    newer = await make_media_item(
        engine,
        workspace_id=setup.wid,
        account_id=setup.account_id,
        caption="Linen shirts are back in five colours. " * 6,
        posted_at=now - timedelta(hours=3),
    )
    return older, newer


def price_args(**values: Any) -> dict[str, Any]:
    return {
        "name": "Price on comment",
        "trigger": "comment_keyword",
        "keywords": ["price"],
        "post": "latest",
        "dm_text": "Hi {first_name}! It's RS 500.",
        **values,
    }


# ---------------------------------------------------------------- list_instagram_posts


async def test_list_instagram_posts_newest_first_with_limit_and_account(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    older, newer = await two_posts(engine, setup)
    other = await make_account(engine, setup.wid, username="cafe.pune")
    theirs = await make_media_item(
        engine,
        workspace_id=setup.wid,
        account_id=other,
        posted_at=datetime.now(UTC) - timedelta(days=2),
    )
    async with engine.begin() as conn:  # a Story: listed only when asked for
        await conn.execute(
            text(
                "INSERT INTO media_items (workspace_id, social_account_id, platform_media_id, "
                "media_type, caption, posted_at) VALUES (:w, :a, 'story-1', 'story', NULL, :at)"
            ),
            {"w": setup.wid, "a": setup.account_id, "at": datetime.now(UTC)},
        )
    found = structured(await call(mcp_app, key, "list_instagram_posts", {}))
    assert [i["post_id"] for i in found["items"]] == [str(newer), str(theirs), str(older)]
    first = found["items"][0]
    assert first["type"] == "post"
    assert len(first["caption_start"]) <= 120
    assert first["caption_start"].endswith("…")
    assert "UTC)" in first["published_at"]
    assert first["permalink"].startswith("https://www.instagram.com/")
    assert found["total"] == 3

    limited = structured(await call(mcp_app, key, "list_instagram_posts", {"limit": 1}))
    assert [i["post_id"] for i in limited["items"]] == [str(newer)]
    assert limited["more"] == 2

    mine = structured(await call(mcp_app, key, "list_instagram_posts", {"account": "@cafe.pune"}))
    assert [i["post_id"] for i in mine["items"]] == [str(theirs)]
    assert mine["items"][0]["account"] == "@cafe.pune"

    stories = structured(
        await call(mcp_app, key, "list_instagram_posts", {"include_stories": True})
    )
    assert stories["items"][0]["type"] == "story"


# ---------------------------------------------------------------- create_automation


async def test_create_previews_then_creates_on_the_latest_post(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    _, newer = await two_posts(engine, setup)
    preview = structured(
        await call(mcp_app, key, "create_automation", price_args(public_reply="Sent you a DM!"))
    )
    assert preview["preview"] is True
    assert preview["automation_id"] is None
    assert preview["status"] == "draft"
    assert preview["post"]["post_id"] == str(newer)  # “latest”: the newest synced post
    assert preview["post"]["caption_start"].startswith("Linen shirts")
    assert preview["posts"] == "one post"
    assert (preview["keywords"], preview["match"]) == (["price"], "word")
    assert preview["dm_text"] == "Hi {first_name}! It's RS 500."
    assert preview["public_replies"] == ["Sent you a DM!"]
    assert preview["tap_first_opening"]  # the app's tap first opening comes first
    assert preview["needs_before_on"] == []
    assert preview["active_automations"] == {"on_now": 0, "allowed": 50}
    assert "confirmed: true" in preview["next_step"]
    # A preview leaves nothing behind.
    assert await rows(engine, "SELECT 1 FROM automations") == []
    assert await rows(engine, "SELECT 1 FROM automation_keywords") == []
    assert await rows(engine, "SELECT 1 FROM audit_events WHERE action LIKE 'automation.%'") == []
    assert await rows(engine, "SELECT 1 FROM notifications") == []

    done = structured(
        await confirm(mcp_app, key, "create_automation", price_args(public_reply="Sent you a DM!"))
    )
    assert (done["preview"], done["status"]) == (False, "draft")
    assert done["dashboard_url"].endswith(f"/automations/{done['automation_id']}")
    [row] = await rows(engine, "SELECT * FROM automations")
    assert str(row["id"]) == done["automation_id"]
    assert (row["status"], row["trigger"], row["action"]) == (
        "draft",
        "comment_keyword",
        "send_message",
    )
    assert row["post_scope"] == "selected"
    assert row["public_reply_texts"] == ["Sent you a DM!"]
    [link] = await rows(engine, "SELECT media_item_id FROM automation_posts")
    assert link["media_item_id"] == newer
    [kw] = await rows(engine, "SELECT keyword FROM automation_keywords")
    assert kw["keyword"] == "price"
    [note] = await rows(engine, "SELECT * FROM notifications WHERE type = 'ai_automation_change'")
    assert "created the automation “Price on comment”" in note["title"]
    assert note["link"] == f"/automations/{done['automation_id']}"
    [audit] = await rows(engine, "SELECT * FROM audit_events WHERE action = 'automation.created'")
    assert audit["actor_label"].startswith("Asha")
    assert " via " in audit["actor_label"]
    assert audit["target_id"] == done["automation_id"]
    assert audit["detail"]["via"] == "mcp"


async def test_turn_on_activates_within_the_limit_and_refuses_over_it(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    on = structured(
        await confirm(
            mcp_app,
            key,
            "create_automation",
            {
                "name": "DM price",
                "account": setup.account_id,
                "trigger": "dm_keyword",
                "keywords": ["price", "cost"],
                "dm_text": "It's RS 500.",
                "link_button": {"title": "Shop", "url": "https://example.com/shop"},
                "turn_on": True,
            },
        )
    )
    assert on["status"] == "active"
    assert on["posts"] == "DMs, not posts"
    assert on["link_buttons"] == [{"title": "Shop", "url": "https://example.com/shop"}]
    [row] = await rows(engine, "SELECT status, activated_at FROM automations")
    assert row["status"] == "active"
    assert row["activated_at"] is not None
    activated = await rows(
        engine, "SELECT 1 FROM audit_events WHERE action = 'automation.activated'"
    )
    assert len(activated) == 1
    [note] = await rows(engine, "SELECT title FROM notifications")
    assert note["title"].endswith(", which is on")

    monkeypatch.setitem(ENTITLEMENTS["active_automations"], "max", 1)
    args = {
        "name": "DM hours",
        "account": setup.account_id,
        "trigger": "dm_keyword",
        "keywords": ["hours"],
        "dm_text": "We open at 9.",
        "turn_on": True,
    }
    monkeypatch.setitem(ENTITLEMENTS["active_automations"], "max", 2)
    token = structured(await call(mcp_app, key, "create_automation", args))["confirmation_token"]
    monkeypatch.setitem(ENTITLEMENTS["active_automations"], "max", 1)
    # The preview refuses, and so does a confirmed call whose preview was fine when it was made.
    for extra in ({}, {"confirmed": True, "confirmation_token": token}):
        error = error_of(await call(mcp_app, key, "create_automation", {**args, **extra}))
        assert (error["code"], error["entitlement"]) == ("quota_exceeded", "active_automations")
        assert "Pause one" in error["message"]
        assert "1 are on" in error["message"]
    assert len(await rows(engine, "SELECT 1 FROM automations")) == 1  # nothing was created
    off = structured(await confirm(mcp_app, key, "create_automation", {**args, "turn_on": False}))
    assert off["status"] == "draft"
    assert off["active_automations"] == {"on_now": 1, "allowed": 1}


async def test_overlaps_with_live_automations_are_shown(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    await two_posts(engine, setup)
    live = await make_automation(
        engine,
        workspace_id=setup.wid,
        account_id=setup.account_id,
        name="Old price reply",
        trigger="comment_keyword",
        keywords=("Price",),
    )
    preview = structured(await call(mcp_app, key, "create_automation", price_args()))
    assert preview["overlaps"] == [
        {
            "keyword": "price",
            "automation_id": str(live),
            "automation_name": "Old price reply",
            "this_runs_first": False,
        }
    ]
    assert preview["active_automations"]["on_now"] == 1


async def test_the_same_key_replays_and_an_identical_resend_is_deduplicated(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    await two_posts(engine, setup)
    args = price_args(idempotency_key="automation-0001")
    token = structured(await call(mcp_app, key, "create_automation", args))["confirmation_token"]
    args = {**args, "confirmed": True, "confirmation_token": token}
    first = structured(await call(mcp_app, key, "create_automation", args))
    again = structured(await call(mcp_app, key, "create_automation", args))
    assert again == {**first, "duplicate_of_previous_call": True}
    # A retry replays whatever its token says now: the key decides, before the token is read.
    stale = {**args, "confirmation_token": "1.dead"}
    assert structured(await call(mcp_app, key, "create_automation", stale)) == again
    plain = price_args(name="Second")
    one = structured(await confirm(mcp_app, key, "create_automation", plain))
    two = structured(await confirm(mcp_app, key, "create_automation", plain))
    assert two == {**one, "duplicate_of_previous_call": True}  # the window, whatever the token
    assert len(await rows(engine, "SELECT 1 FROM automations")) == 2
    assert len(await rows(engine, "SELECT 1 FROM notifications")) == 2
    # A preview isn't stored: the same key can still create.
    other = price_args(name="Third", idempotency_key="automation-0002")
    done = structured(await confirm(mcp_app, key, "create_automation", other))
    assert done["automation_id"]
    assert done["duplicate_of_previous_call"] is False


async def test_bad_arguments_and_an_ambiguous_account(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    no_posts = error_of(await call(mcp_app, key, "create_automation", price_args()))
    assert no_posts["code"] == "not_found"
    assert "synced" in no_posts["message"]
    dm_post = error_of(
        await call(mcp_app, key, "create_automation", price_args(trigger="dm_keyword"))
    )
    assert dm_post["code"] == "validation_error"
    garbage = error_of(await call(mcp_app, key, "create_automation", price_args(post="yesterday")))
    assert garbage["code"] == "validation_error"
    unknown = error_of(
        await call(mcp_app, key, "create_automation", price_args(post=str(uuid.uuid4())))
    )
    assert unknown["code"] == "not_found"
    too_many = error_of(
        await call(
            mcp_app, key, "create_automation", price_args(keywords=[f"k{i}" for i in range(21)])
        )
    )
    assert too_many["code"] == "validation_error"
    for _ in range(2):
        await make_account(engine, setup.wid, username="twin.shop")
    twin = error_of(
        await call(mcp_app, key, "create_automation", price_args(account="@twin.shop", post="any"))
    )
    assert twin["code"] == "conflict"
    assert "Several accounts match" in twin["message"]
    # No account named and several could run it: asked, not left without one.
    which = error_of(await call(mcp_app, key, "create_automation", price_args(post="any")))
    assert which["code"] == "conflict"
    assert "Which one?" in which["message"]
    assert await rows(engine, "SELECT 1 FROM automations") == []


async def test_plan_role_and_mode_gate_the_automation_writes(
    client: httpx.AsyncClient, mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    args = price_args(post="any", confirmed=True)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET ai_connections_mode = 'read_drafts' WHERE id = :w"),
            {"w": setup.wid},
        )
    drafts = error_of(await call(mcp_app, key, "create_automation", args))
    assert drafts["code"] == "forbidden"
    assert "only read and prepare drafts" in drafts["message"]
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET ai_connections_mode = 'full' WHERE id = :w"),
            {"w": setup.wid},
        )
    await set_plan(engine, setup.wid, "free")
    free = error_of(await call(mcp_app, key, "create_automation", args))
    assert (free["code"], free["entitlement"]) == ("entitlement_required", "ai_connections")
    # list_instagram_posts reads, on every plan.
    assert structured(await call(mcp_app, key, "list_instagram_posts", {}))["items"] == []
    await set_plan(engine, setup.wid, "max")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": setup.wid},
        )
    async with connect(mcp_app, key) as mcp:
        names = {t.name for t in (await mcp.list_tools()).tools}
        agent = error_of(await mcp.call_tool("create_automation", args))
    assert "create_automation" not in names
    assert "update_automation" not in names
    assert "list_instagram_posts" in names  # any member, as the Comments page
    assert agent["code"] == "forbidden"
    assert await rows(engine, "SELECT 1 FROM automations") == []


# ---------------------------------------------------------------- update_automation


async def test_update_previews_then_changes_the_automation(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    older, newer = await two_posts(engine, setup)
    made = structured(await confirm(mcp_app, key, "create_automation", price_args(turn_on=True)))
    automation_id = made["automation_id"]
    change = {
        "automation_id": automation_id,
        "keywords": ["price", "rate"],
        "dm_text": "It's RS 450 this week.",
        "post": str(older),
        "public_reply": "Check your DMs!",
    }
    preview = structured(await call(mcp_app, key, "update_automation", change))
    assert preview["preview"] is True
    assert preview["keywords"] == ["price", "rate"]
    assert preview["post"]["post_id"] == str(older)
    assert preview["status"] == "active"  # the tool never turns it on or off
    [row] = await rows(engine, "SELECT message_text, public_reply_texts FROM automations")
    assert row["message_text"] == "Hi {first_name}! It's RS 500."  # unchanged by the preview
    assert row["public_reply_texts"] == []
    [link] = await rows(engine, "SELECT media_item_id FROM automation_posts")
    assert link["media_item_id"] == newer

    done = structured(
        await call(
            mcp_app,
            key,
            "update_automation",
            {**change, "confirmed": True, "confirmation_token": preview["confirmation_token"]},
        )
    )
    assert (done["preview"], done["status"]) == (False, "active")
    [row] = await rows(engine, "SELECT * FROM automations")
    assert row["message_text"] == "It's RS 450 this week."
    assert row["public_reply_texts"] == ["Check your DMs!"]
    assert row["confirm_first"] is True  # what the tool doesn't touch is kept
    words = {r["keyword"] for r in await rows(engine, "SELECT keyword FROM automation_keywords")}
    assert words == {"price", "rate"}
    [link] = await rows(engine, "SELECT media_item_id FROM automation_posts")
    assert link["media_item_id"] == older
    [audit] = await rows(engine, "SELECT * FROM audit_events WHERE action = 'automation.updated'")
    assert audit["target_id"] == automation_id
    changed = await rows(
        engine, "SELECT title FROM notifications WHERE title LIKE '%changed the automation%'"
    )
    assert len(changed) == 1

    # A call that changes nothing is refused.
    nothing = error_of(
        await call(mcp_app, key, "update_automation", {"automation_id": automation_id})
    )
    assert nothing["code"] == "validation_error"


async def test_update_refuses_flows_and_other_shapes(
    client: httpx.AsyncClient, mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    created = await client.post(
        f"/v1/w/{setup.wid}/automations",
        json={"template_key": "price_by_option", "social_account_id": setup.account_id},
        headers=setup.headers,
    )
    assert created.status_code == 201, created.text
    flow_id = created.json()["id"]
    assert created.json()["flow_source"] == "flow"
    refused = error_of(
        await call(mcp_app, key, "update_automation", {"automation_id": flow_id, "name": "X"})
    )
    assert refused["code"] == "conflict"
    assert "multi-step flow" in refused["message"]
    assert f"/automations/{flow_id}" in refused["message"]

    ai = await make_automation(
        engine,
        workspace_id=setup.wid,
        account_id=setup.account_id,
        action="ai_reply",
        ai_instructions="Answer from the knowledge base.",
    )
    refused_ai = error_of(
        await call(mcp_app, key, "update_automation", {"automation_id": str(ai), "name": "X"})
    )
    assert refused_ai["code"] == "conflict"
    assert "AI" in refused_ai["message"]

    dm = await make_automation(engine, workspace_id=setup.wid, account_id=setup.account_id)
    dm_post = error_of(
        await call(mcp_app, key, "update_automation", {"automation_id": str(dm), "post": "any"})
    )
    assert dm_post["code"] == "validation_error"
    missing = error_of(
        await call(
            mcp_app, key, "update_automation", {"automation_id": str(uuid.uuid4()), "name": "X"}
        )
    )
    assert missing["code"] == "not_found"
    [name] = await rows(engine, "SELECT name FROM automations WHERE id = :i", i=flow_id)
    assert name["name"] != "X"


async def test_get_post_comments_summary_reads_latest_through_the_same_resolver(
    client: httpx.AsyncClient, mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    comments_key, _ = await make_key(client, setup, "comments:read")
    missing = error_of(
        await call(mcp_app, comments_key, "get_post_comments_summary", {"post": "latest"})
    )
    assert missing["code"] == "not_found"
    _, newer = await two_posts(engine, setup)
    summary = structured(
        await call(mcp_app, comments_key, "get_post_comments_summary", {"post": "latest"})
    )
    assert summary["post_id"] == str(newer)


async def test_get_analytics_summary_reads_latest_through_the_same_resolver(
    client: httpx.AsyncClient, mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    analytics_key, _ = await make_key(client, setup, "analytics:read")
    _, newer = await two_posts(engine, setup)
    result = structured(
        await call(
            mcp_app, analytics_key, "get_analytics_summary", {"scope": "post", "post_id": "latest"}
        )
    )
    assert result["post"]["post_id"] == str(newer)
    bad = error_of(
        await call(
            mcp_app, analytics_key, "get_analytics_summary", {"scope": "post", "post_id": "nope"}
        )
    )
    assert bad["code"] == "validation_error"


async def test_what_activation_would_refuse_is_shown_on_a_draft_and_stops_a_live_change(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    long_dm = "x" * 1500  # over Instagram's 1,000 bytes, under the argument's backstop
    args = {
        "name": "Long",
        "account": setup.account_id,
        "trigger": "dm_keyword",
        "keywords": ["long"],
        "dm_text": long_dm,
    }
    preview = structured(await call(mcp_app, key, "create_automation", args))
    assert preview["needs_before_on"]
    assert "1,000" in preview["needs_before_on"][0] or "bytes" in preview["needs_before_on"][0]
    refused = error_of(await call(mcp_app, key, "create_automation", {**args, "turn_on": True}))
    assert refused["code"] == "validation_error"
    assert await rows(engine, "SELECT 1 FROM automations") == []

    live = await make_automation(engine, workspace_id=setup.wid, account_id=setup.account_id)
    broken = error_of(
        await call(
            mcp_app,
            key,
            "update_automation",
            {"automation_id": str(live), "dm_text": long_dm},
        )
    )
    assert broken["code"] == "validation_error"
    [row] = await rows(engine, "SELECT message_text FROM automations")
    assert row["message_text"] != long_dm


async def test_update_refuses_a_live_comments_automation(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    live_only = await make_automation(
        engine,
        workspace_id=setup.wid,
        account_id=setup.account_id,
        trigger="comment_keyword",
        comment_surface="live",
    )
    refused = error_of(
        await call(
            mcp_app, key, "update_automation", {"automation_id": str(live_only), "name": "X"}
        )
    )
    assert refused["code"] == "conflict"
    assert "Live comments" in refused["message"]


async def test_the_comment_automation_prompt_previews_before_creating(
    mcp_app: FastAPI, key: str
) -> None:
    async with connect(mcp_app, key) as mcp:
        prompt = await mcp.get_prompt(
            "set_up_comment_automation", {"keyword": "price", "message": "RS 500"}
        )
    body = prompt.messages[0].content.text  # type: ignore[union-attr]
    assert "price" in body
    assert "list_instagram_posts" in body
    assert "confirmation_token only after I say yes" in body


# ---------------------------------------------------------------- the server-checked preview


async def test_confirming_needs_a_valid_token_for_exactly_those_arguments(
    client: httpx.AsyncClient,
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await two_posts(engine, setup)
    args = price_args(turn_on=True)
    tool = "create_automation"
    good = structured(await call(mcp_app, key, tool, args))["confirmation_token"]
    assert good

    async def refused(arguments: dict[str, Any], *, by: str = key) -> dict[str, Any]:
        error = error_of(await call(mcp_app, by, tool, arguments))
        assert error["code"] == "validation_error"
        assert error["field_errors"][0]["field"] == "confirmation_token"
        assert "preview" in error["message"]
        assert await rows(engine, "SELECT 1 FROM automations") == []
        return error

    # The first call of the owner's report: live with no preview.
    await refused({**args, "confirmed": True})
    await refused({**args, "confirmed": True, "confirmation_token": "wrong"})
    await refused({**args, "confirmed": True, "confirmation_token": good[:-1] + "0"})
    await refused({**args, "confirmed": True, "confirmation_token": "99999999999.é"})
    # Changed arguments need a new preview, whichever one changed.
    changed = {"confirmed": True, "confirmation_token": good}
    await refused({**args, **changed, "dm_text": "RS 900"})
    await refused({**args, **changed, "keywords": ["price", "cost"]})
    # Off in the preview, on in the call: the one change that matters most.
    off_token = structured(await call(mcp_app, key, tool, price_args()))["confirmation_token"]
    await refused({**args, "confirmed": True, "confirmation_token": off_token})
    # Another connection's preview isn't this one's.
    other, _ = await make_key(client, setup, *SCOPES, name="Other laptop")
    theirs = structured(await call(mcp_app, other, tool, args))["confirmation_token"]
    await refused({**args, "confirmed": True, "confirmation_token": theirs})
    await refused({**args, "confirmed": True, "confirmation_token": good}, by=other)
    # Expired.
    monkeypatch.setattr(confirmations, "TTL_S", -1)
    old = structured(await call(mcp_app, key, tool, args))["confirmation_token"]
    monkeypatch.undo()
    expired = await refused({**args, "confirmed": True, "confirmation_token": old})
    assert "expired" in expired["message"]
    # “latest” is a different post now: what was shown is not what would be done.
    await make_media_item(
        engine, workspace_id=setup.wid, account_id=setup.account_id, posted_at=datetime.now(UTC)
    )
    await refused({**args, "confirmed": True, "confirmation_token": good})
    # A good token, for the arguments as they were previewed.
    fresh = structured(await call(mcp_app, key, tool, args))["confirmation_token"]
    done = structured(
        await call(mcp_app, key, tool, {**args, "confirmed": True, "confirmation_token": fresh})
    )
    assert done["status"] == "active"


async def test_update_automation_needs_the_token_too(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    live = await make_automation(engine, workspace_id=setup.wid, account_id=setup.account_id)
    change = {"automation_id": str(live), "dm_text": "New words"}
    error = error_of(await call(mcp_app, key, "update_automation", {**change, "confirmed": True}))
    assert error["field_errors"][0]["field"] == "confirmation_token"
    token = structured(await call(mcp_app, key, "update_automation", change))["confirmation_token"]
    other = error_of(
        await call(
            mcp_app,
            key,
            "update_automation",
            {**change, "dm_text": "Other words", "confirmed": True, "confirmation_token": token},
        )
    )
    assert other["field_errors"][0]["field"] == "confirmation_token"
    [row] = await rows(engine, "SELECT message_text FROM automations")
    assert row["message_text"] != "New words"
    done = structured(await confirm(mcp_app, key, "update_automation", change))
    assert done["dm_text"] == "New words"


# ---------------------------------------------------------------- the new scope (§6.8)


async def test_automations_write_alone_doesn_t_open_the_new_tools(
    client: httpx.AsyncClient, mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    old_key, _ = await make_key(client, setup, "automations:read", "automations:write")
    async with connect(mcp_app, old_key) as mcp:
        names = {t.name for t in (await mcp.list_tools()).tools}
        refused = error_of(await mcp.call_tool("create_automation", price_args(post="any")))
    assert {"pause_automation", "resume_automation", "list_automations"} <= names
    assert names.isdisjoint({"create_automation", "update_automation"})
    assert refused["code"] == "forbidden"
    assert "automations:create" in refused["message"]
    assert await rows(engine, "SELECT 1 FROM automations") == []
    new_key, _ = await make_key(client, setup, "automations:create")
    async with connect(mcp_app, new_key) as mcp:
        names = {t.name for t in (await mcp.list_tools()).tools}
    assert {"create_automation", "update_automation"} <= names
    assert "pause_automation" not in names
