"""GR-29: Page post comments (the ``feed`` webhook field) and the automations that answer them -
intake, public and private replies, hide and delete, the workspace's other platforms staying
apart - plus activation on a Page: what Messenger allows runs, what it doesn't is refused with a
plain reason, entry links open m.me, and conversation starters are pushed to the Page."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.tasks.purge import run_account_purge
from socialhood.media.purge import StoredFile, use_media_purger
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.deps import deps_from
from socialhood.platforms.events import ReferralInfo
from socialhood.platforms.sandbox import outbox
from socialhood.services.account_deletion import PurgeDeps
from socialhood.services.automations import validation
from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.services.webhook_handlers import instagram as instagram_handler
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import Ws
from tests.support.automations import make_automation
from tests.support.facebook import (
    PERSON,
    deliver_page,
    make_page_world,
    page_comment,
    page_delivery,
    page_message,
    with_facebook,
)
from tests.support.ingest import jobs, sessions
from tests.support.runtime import World, platform_deps
from tests.support.sending import clean_outbox

LINK_REPLIES = ["Sent you a message, {username}!", "Check your Messenger!"]


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_facebook(api_settings)


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture(autouse=True)
def _deps(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    deps = deps_from(app.state.http, app.state.settings)
    monkeypatch.setattr(instagram_handler, "platform_deps", lambda: deps)


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
        yield await make_page_world(engine, redis, deps)


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    """An owner with a sandbox Facebook Page."""
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com")
    wid = me["workspaces"][0]["id"]
    made = await client.post(
        f"/v1/w/{wid}/dev/sandbox/accounts",
        json={"platform": "facebook"},
        headers=clerk.headers(clerk_id),
    )
    assert made.status_code == 201, made.text
    return Ws(client, clerk, clerk_id, wid, me["id"], made.json()["id"])


async def _rows(engine: AsyncEngine, sql: str) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql))]


def keyed(ws: Ws, key: str) -> dict[str, str]:
    """The owner's headers with an Idempotency-Key (TR-API-05)."""
    headers = dict(ws.headers)
    headers["Idempotency-Key"] = key
    return headers


async def page_ref(world: World) -> str:
    [row] = await world.rows(
        "SELECT platform_account_id FROM social_accounts WHERE id = :id", id=world.account_id
    )
    return str(row["platform_account_id"])


async def link_automation(world: World, **values: Any) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "trigger": "comment_keyword",
        "message_text": "Here's the link, {username}!",
        "public_reply_texts": LINK_REPLIES,
        "message_buttons": [{"title": "Shop", "url": "https://maple.example/shop"}],
    }
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        **{**defaults, **values},
    )


# ---------------------------------------------------------------- intake


async def test_a_post_comment_is_stored_once_with_its_commenter_and_post(world: World) -> None:
    ref = await page_ref(world)
    body = page_comment(ref, f"{ref}_post_0_77", "LINK please", name="Asha Rao")
    maker = sessions(world.engine)

    assert await deliver_page(maker, world.redis, body) == [WebhookStatus.PROCESSED]
    [comment] = await world.rows("SELECT * FROM comments")
    assert (comment["text"], comment["author_username"], comment["analysis_status"]) == (
        "LINK please",
        "Asha Rao",
        "pending",
    )
    assert comment["parent_platform_comment_id"] is None
    [contact] = await world.rows("SELECT * FROM contacts")
    assert (contact["platform_user_id"], contact["username"]) == (PERSON, "Asha Rao")
    [post] = await world.rows("SELECT * FROM media_items")
    assert post["platform_media_id"] == f"{ref}_post_0"  # fetched from the Page, then stored
    assert comment["media_item_id"] == post["id"]

    # A second delivery of the same comment stores nothing.
    assert await deliver_page(maker, world.redis, body, copy="again") == [WebhookStatus.IGNORED]
    assert len(await world.rows("SELECT id FROM comments")) == 1


async def test_a_reply_under_a_comment_keeps_its_parent(world: World) -> None:
    ref = await page_ref(world)
    maker = sessions(world.engine)
    await deliver_page(maker, world.redis, page_comment(ref, "c_top", "Nice"))
    reply = page_comment(ref, "c_reply", "Agreed", sender="7009990001", parent_id="c_top")
    assert await deliver_page(maker, world.redis, reply) == [WebhookStatus.PROCESSED]
    [row] = await world.rows(
        "SELECT parent_platform_comment_id FROM comments WHERE platform_comment_id = 'c_reply'"
    )
    assert row["parent_platform_comment_id"] == "c_top"


async def test_the_pages_own_comments_and_other_feed_items_are_ignored(world: World) -> None:
    ref = await page_ref(world)
    maker = sessions(world.engine)
    own = page_comment(ref, "c_own", "Thanks!", sender=ref, name="Maple Bakery")
    assert await deliver_page(maker, world.redis, own) == [WebhookStatus.IGNORED]
    edited = page_comment(ref, "c_edit", "Nice (edited)", verb="edited")
    assert await deliver_page(maker, world.redis, edited) == [WebhookStatus.IGNORED]
    status = page_delivery(
        ref,
        changes=[
            {
                "field": "feed",
                "value": {"item": "status", "verb": "add", "post_id": f"{ref}_post_5"},
            }
        ],
    )
    assert await deliver_page(maker, world.redis, status) == [WebhookStatus.IGNORED]
    assert await world.rows("SELECT id FROM comments") == []


async def test_a_comment_enqueues_the_pages_comment_automations(world: World) -> None:
    await link_automation(world)
    comment_id = await world.comment("LINK")
    [job] = await jobs("run_automation")
    assert job["queueing_lock"] == f"automation:comment:{comment_id}"


# ---------------------------------------------------------------- the runtime on a Page


async def test_a_keyword_comment_gets_a_public_reply_and_a_private_message_from_the_queue(
    world: World,
) -> None:
    await link_automation(world)
    comment_id = await world.comment("LINK please", username="Asha Rao")
    assert comment_id is not None

    assert await world.run("comment", comment_id) is Outcome.FIRED
    [reply] = outbox.COMMENT_REPLIES
    assert reply.text in ("Sent you a message, Asha Rao!", "Check your Messenger!")
    assert not outbox.PRIVATE_REPLIES  # waits in the account's queue

    result = await world.drain()
    assert (result.sent, result.failed) == (1, 0)
    [comment] = await world.rows("SELECT * FROM comments")
    [private] = outbox.PRIVATE_REPLIES
    assert private.recipient_ref == comment["platform_comment_id"]
    assert private.message.text == "Here's the link, Asha Rao!"
    assert [b.title for b in private.message.buttons] == ["Shop"]

    [conv] = await world.rows("SELECT platform FROM conversations")
    assert conv["platform"] == "facebook"
    [run] = await world.rows("SELECT result FROM automation_runs")
    assert run["result"] == "sent"


async def test_a_failed_private_message_still_posts_the_public_reply(world: World) -> None:
    await link_automation(world)
    comment_id = await world.comment("link")
    assert comment_id is not None
    outbox.fail_next("recipient_unavailable", kind="private_reply")
    await world.run("comment", comment_id)
    assert len(outbox.COMMENT_REPLIES) == 1
    assert (await world.drain()).failed == 1
    [run] = await world.rows("SELECT result, error_code, error_message FROM automation_runs")
    assert (run["result"], run["error_code"]) == ("partial", "recipient_unavailable")


async def test_a_dm_keyword_automation_answers_a_messenger_message(world: World) -> None:
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        message_text="We open at 9, {first_name}.",
    )
    message_id = await world.dm("7001234500001", "link please")
    assert message_id is not None
    assert await world.run("dm", message_id) is Outcome.FIRED
    sent = [m for m in outbox.SENT if m.message.text and m.message.text.startswith("We open")]
    assert len(sent) == 1
    [conv] = await world.rows("SELECT platform FROM conversations")
    assert conv["platform"] == "facebook"


async def test_an_m_me_link_starts_its_entry_link_automation(world: World) -> None:
    automation_id = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=(),
        trigger="entry_link",
        name="Welcome",
        message_text="Welcome from the shop window!",
    )
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO entry_links (workspace_id, social_account_id, automation_id, code,"
                " name) VALUES (:w, :a, :auto, 'window', 'window')"
            ),
            {"w": world.wid, "a": world.account_id, "auto": automation_id},
        )
    await world.referral("7001234500002", ref="window")
    first = await world.dm("7001234500002", "hi")
    assert first is not None
    assert await world.run("dm", first) is Outcome.FIRED
    run = await world.run_row()
    assert (run["automation_id"], run["result"]) == (automation_id, "sent")
    [conv] = await world.rows("SELECT entry_source, entry_ref FROM conversations")
    assert (conv["entry_source"], conv["entry_ref"]) == ("link", "window")


async def test_a_click_to_messenger_ad_starts_the_ad_click_automation(world: World) -> None:
    automation_id = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=(),
        trigger="ad_click",
        name="From ads",
        message_text="Thanks for tapping our ad!",
    )
    ad = ReferralInfo(source="ad", ad_id="ad_77", ad_title="Spring sale")
    first = await world.dm("7001234500003", "Is this still on?", referral=ad)
    assert first is not None
    assert await world.run("dm", first) is Outcome.FIRED
    assert (await world.run_row())["automation_id"] == automation_id


async def test_a_flow_with_quick_replies_waits_for_the_tap_on_a_page(world: World) -> None:
    automation_id = await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, message_text=None
    )
    flow = {
        "start": "ask",
        "steps": [
            {
                "type": "send",
                "id": "ask",
                "text": "What do you need?",
                "quick_replies": [{"title": "Prices", "next": "prices"}],
                "on_text": "prices",
            },
            {"type": "send", "id": "prices", "text": "Everything is 4 pounds."},
        ],
    }
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO automation_flows (workspace_id, automation_id, version, definition)"
                " VALUES (:w, :a, 1, CAST(:d AS jsonb))"
            ),
            {"w": world.wid, "a": automation_id, "d": json.dumps(flow)},
        )
        await conn.execute(
            text("UPDATE automations SET flow_version = 1 WHERE id = :a"), {"a": automation_id}
        )
    first = await world.dm("7001234500004", "link")
    assert first is not None
    assert await world.run("dm", first) is Outcome.FIRED
    [queued] = await world.rows(
        "SELECT id, quick_replies FROM messages WHERE direction = 'outbound'"
    )
    assert [q["title"] for q in queued["quick_replies"]] == ["Prices"]
    assert await world.send(queued["id"]) is Delivery.SENT
    [opening] = outbox.SENT
    assert [q.title for q in opening.message.quick_replies] == ["Prices"]

    run = await world.run_row()
    tapped = await world.dm(
        "7001234500004", "Prices", payload=queued["quick_replies"][0]["payload"]
    )
    assert tapped is not None
    assert await world.run("dm", tapped) is Outcome.ANSWERED
    assert await world.run("flow", run["id"]) is Outcome.FIRED
    [_, answer] = await world.rows(
        "SELECT id, text FROM messages WHERE direction = 'outbound' ORDER BY created_at"
    )
    assert answer["text"] == "Everything is 4 pounds."


# ---------------------------------------------------------------- the comment actions


async def test_a_reply_hide_and_delete_go_to_the_page(
    client: httpx.AsyncClient, ws: Ws, engine: AsyncEngine, redis: Redis, queue: None
) -> None:
    [acct] = await _rows(engine, "SELECT platform_account_id FROM social_accounts")
    ref = acct["platform_account_id"]
    maker = sessions(engine)
    await deliver_page(maker, redis, page_comment(ref, "c_1", "Is it gluten free?"))
    [comment] = await _rows(engine, "SELECT id FROM comments")
    cid = comment["id"]

    reply = await ws.call(
        "POST",
        f"/comments/{cid}/reply",
        json={"text": "Yes it is!"},
        headers=keyed(ws, "reply-0001-abcd"),
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["public_reply"]["text"] == "Yes it is!"
    [posted] = outbox.COMMENT_REPLIES
    assert (posted.comment_ref, posted.text) == ("c_1", "Yes it is!")

    assert (await ws.call("POST", f"/comments/{cid}/hide")).status_code == 200
    assert (await ws.call("POST", f"/comments/{cid}/unhide")).status_code == 200
    assert (await ws.call("DELETE", f"/comments/{cid}")).status_code == 204
    assert [(m.comment_ref, m.action) for m in outbox.MODERATION] == [
        ("c_1", "hide"),
        ("c_1", "unhide"),
        ("c_1", "delete"),
    ]


async def test_a_private_reply_is_queued_once_and_limited_to_2000_characters(
    client: httpx.AsyncClient, ws: Ws, engine: AsyncEngine, redis: Redis, queue: None
) -> None:
    [acct] = await _rows(engine, "SELECT platform_account_id FROM social_accounts")
    ref = acct["platform_account_id"]
    await deliver_page(sessions(engine), redis, page_comment(ref, "c_9", "Price?"))
    [comment] = await _rows(engine, "SELECT id FROM comments")
    url = f"/comments/{comment['id']}/private-reply"

    long = await ws.call(
        "POST",
        url,
        json={"text": "x" * 2001},
        headers=keyed(ws, "dm-reply-0001-abcd"),
    )
    assert long.status_code == 422, long.text
    assert long.json()["errors"][0]["message"].startswith("Facebook messages can be up to 2,000")

    ok = await ws.call(
        "POST",
        url,
        json={"text": "It is 4 pounds."},
        headers=keyed(ws, "dm-reply-0002-abcd"),
    )
    assert ok.status_code == 202, ok.text
    [conv] = await _rows(engine, "SELECT platform FROM conversations")
    assert conv["platform"] == "facebook"
    again = await ws.call(
        "POST",
        url,
        json={"text": "Another"},
        headers=keyed(ws, "dm-reply-0003-abcd"),
    )
    assert again.status_code == 409


# ---------------------------------------------------------------- activation on a Page


async def refusals(ws: Ws, **values: Any) -> dict[str, str]:
    """Save a draft with these settings and try to activate it: the plain reasons by field."""
    draft = await ws.draft(**values)
    response = await ws.call("POST", f"/automations/{draft['id']}/activate")
    if response.status_code == 200:
        return {}
    assert response.status_code == 422, response.text
    return {e["field"]: e["message"] for e in response.json()["errors"]}


async def test_the_dm_comment_entry_and_ad_triggers_activate_on_a_page(ws: Ws) -> None:
    for trigger, extra in (
        ("dm_keyword", {}),
        ("comment_keyword", {"public_reply_texts": ["Sent you a message!"]}),
        ("entry_link", {"keywords": []}),
        ("ad_click", {"keywords": [], "post_scope": "all"}),
    ):
        assert await refusals(ws, **{"trigger": trigger, **extra}) == {}, trigger


async def test_story_triggers_are_refused_on_a_page(ws: Ws) -> None:
    for trigger in ("story_reply", "story_mention"):
        found = await refusals(ws, trigger=trigger, keywords=[], post_scope="all")
        assert found == {"trigger": validation.COPY["facebook_stories"]}, trigger


async def test_live_comments_are_refused_on_a_page(ws: Ws) -> None:
    found = await refusals(
        ws,
        trigger="comment_keyword",
        comment_surface="live",
        public_reply_texts=["Thanks!"],
    )
    assert found == {"comment_surface": validation.COPY["facebook_live"]}


async def test_the_follow_line_is_refused_on_a_page(ws: Ws) -> None:
    found = await refusals(ws, follow_nudge=True, follow_nudge_text="Follow us for more")
    assert found == {"follow_nudge": validation.COPY["facebook_follow"]}


async def test_a_page_message_may_be_longer_than_instagrams_limit(ws: Ws) -> None:
    long = "x" * 1500
    assert await refusals(ws, message_text=long, message_buttons=[]) == {}
    over = await refusals(ws, message_text="y" * 2001, message_buttons=[])
    assert over["message_text"].startswith("Facebook allows 2,000 characters.")


async def test_a_flow_that_branches_on_following_is_refused_on_a_page(ws: Ws) -> None:
    draft = await ws.draft()
    flow = {
        "start": "a",
        "steps": [
            {"type": "send", "id": "a", "text": "Hi", "next": "b"},
            {
                "type": "branch",
                "id": "b",
                "rules": [{"when": {"kind": "follows_business", "follows": False}, "next": "c"}],
            },
            {"type": "send", "id": "c", "text": "Please follow us"},
        ],
    }
    saved = await ws.call("PUT", f"/automations/{draft['id']}/flow", json=flow)
    assert saved.status_code == 200, saved.text
    assert "flow.steps.1.rules.0.when" in saved.json()["missing_for_activation"]


# ---------------------------------------------------------------- entry links and starters


async def test_an_entry_link_on_a_page_opens_messenger(ws: Ws) -> None:
    automation = await ws.active(
        **ws.definition(trigger="entry_link", keywords=[], message_buttons=[])
    )
    link = await ws.ok(
        "POST",
        "/entry-links",
        201,
        json={
            "social_account_id": ws.account_id,
            "name": "Shop window",
            "automation_id": automation["id"],
        },
    )
    assert link["url"].startswith("https://m.me/")
    assert link["url"].endswith(f"?ref={link['code']}")
    qr = await ws.call("GET", f"/entry-links/{link['id']}/qr?format=svg")
    assert qr.status_code == 200


async def test_conversation_starters_are_pushed_to_the_page(ws: Ws, engine: AsyncEngine) -> None:
    saved = await ws.ok(
        "PUT",
        f"/social-accounts/{ws.account_id}/ice-breakers",
        json={"items": [{"question": "Opening hours?", "answer_with_ai": True}]},
    )
    assert [i["question"] for i in saved["items"]] == ["Opening hours?"]
    [acct] = await _rows(engine, "SELECT platform_account_id FROM social_accounts")
    pushed = outbox.ICE_BREAKERS[acct["platform_account_id"]]
    assert [s.question for s in pushed] == ["Opening hours?"]
    assert pushed[0].payload.startswith("ib:")


async def test_a_tap_on_a_starter_is_a_postback_the_page_receives(
    world: World, engine: AsyncEngine, redis: Redis
) -> None:
    ref = await page_ref(world)
    body = page_delivery(
        ref,
        messaging=[
            {
                "sender": {"id": PERSON},
                "recipient": {"id": ref},
                "timestamp": int(time.time() * 1000),
                "postback": {"title": "Opening hours?", "payload": "ib:none"},
            }
        ],
    )
    assert await deliver_page(sessions(engine), redis, body) == [WebhookStatus.PROCESSED]
    [message] = await world.rows("SELECT text FROM messages")
    assert message["text"] == "Opening hours?"


# ---------------------------------------------------------------- deleting a Page's data


class NoFiles:
    """The media purger for a Page whose messages own no files."""

    async def delete_workspace_folder(self, workspace_id: uuid.UUID) -> None:
        raise AssertionError("no workspace is deleted here")

    async def delete_files(self, workspace_id: uuid.UUID, files: Sequence[StoredFile]) -> None:
        assert not files


async def test_disconnecting_a_page_and_deleting_its_data_leaves_nothing_of_it(
    app: FastAPI,
    client: httpx.AsyncClient,
    ws: Ws,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    [acct] = await _rows(engine, "SELECT platform_account_id, username FROM social_accounts")
    ref = acct["platform_account_id"]
    maker = sessions(engine)
    await deliver_page(maker, redis, page_message(ref, sender="7001234500005"))
    await deliver_page(maker, redis, page_comment(ref, "c_gone", "Hello"))
    assert len(await _rows(engine, "SELECT id FROM messages")) == 1
    assert len(await _rows(engine, "SELECT id FROM comments")) == 1

    with use_media_purger(NoFiles()):
        removed = await ws.call(
            "DELETE",
            f"/social-accounts/{ws.account_id}",
            params={"delete_data": "true", "confirm": acct["username"]},
        )
        assert removed.status_code == 204, removed.text
        purge = PurgeDeps(sessionmaker=app.state.sessionmaker, redis=redis, media=NoFiles())
        result = await run_account_purge(purge, uuid.UUID(ws.wid), uuid.UUID(ws.account_id))
    assert result.status == "purged"
    for table in ("social_accounts", "conversations", "messages", "contacts", "comments"):
        assert await _rows(engine, f"SELECT id FROM {table}") == [], table  # noqa: S608
    assert await _rows(engine, "SELECT id FROM webhook_events WHERE provider = 'facebook'") != []
