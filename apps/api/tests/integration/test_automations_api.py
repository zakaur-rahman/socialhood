"""T4.3: the automations API (FR-AUT-01…04, 12…16, 19; F-11; UX-SCR-02, 03, 11, 12).

Done when: activation lists every missing field; the overlap warning names the other automation;
stats agree with the run log; the test sends nothing. Plus entitlements, templates, the list,
priorities, duplicate, delete and the post picker.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import time_machine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.services.automations import definitions
from tests.support.api import Clerk
from tests.support.automation_api import (
    Ws,
    count,
    make_outbound,
    make_run,
    set_plan,
    workspace,
)
from tests.support.automations import make_automation, make_comment, make_media_item
from tests.support.inbox import make_account, make_asset, make_thread
from tests.support.ingest import jobs, rows


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


def error_fields(response: httpx.Response) -> list[str]:
    return [e["field"] for e in response.json().get("errors", [])]


# ---------------------------------------------------------------- templates and drafts


async def test_the_template_gallery(ws: Ws) -> None:
    body = await ws.ok("GET", "/automation-templates")
    assert [t["key"] for t in body["items"]] == [
        "send_link",
        "giveaway",
        "price_on_request",
        "catalogue_by_dm",
        "answer_faqs",
        "book_a_call",
    ]
    first = body["items"][0]
    assert first == {
        "key": "send_link",
        "name": "Send a link to commenters",
        "outcome": "Send your link to everyone who comments LINK",
        "category": "grow",
        "icon": "link",
        "trigger": "comment_keyword",
        "action": "send_message",
        "requires_paid_plan": False,
    }


async def test_a_blank_draft_takes_the_only_instagram_account(ws: Ws, engine: AsyncEngine) -> None:
    created = await ws.ok("POST", "/automations", 201, json={"name": "Untitled automation"})

    assert created["name"] == "Untitled automation"
    assert (created["status"], created["display_status"]) == ("draft", "draft")
    assert created["social_account_id"] == ws.account_id
    assert created["keywords"] == []
    assert created["missing_for_activation"] == ["trigger", "action"]
    assert created["stats"] == {"runs_7d": 0, "daily_7d": [0] * 7, "last_run_at": None}
    assert created["queue"] == {"waiting": 0, "eta_minutes": None, "order": "oldest_first"}
    assert (created["priority"], created["template_key"], created["overlaps"]) == (100, None, [])
    stored = await rows(
        engine, "SELECT created_by_user_id FROM automations WHERE id = :i", i=created["id"]
    )
    assert str(stored[0]["created_by_user_id"]) == ws.user_id

    await make_account(engine, ws.wid, username="second.shop")
    second = await ws.ok("POST", "/automations", 201, json={})
    assert second["name"] == "Untitled automation"
    assert second["social_account_id"] is None
    assert second["missing_for_activation"] == ["social_account_id", "trigger", "action"]


async def test_a_template_fills_the_draft(ws: Ws) -> None:
    created = await ws.ok(
        "POST",
        "/automations",
        201,
        json={"template_key": "send_link", "social_account_id": ws.account_id},
    )
    assert created["name"] == "Send a link to commenters"
    assert created["template_key"] == "send_link"
    assert (created["trigger"], created["action"]) == ("comment_keyword", "send_message")
    assert created["keywords"] == ["link"]
    assert created["message_buttons"] == [{"title": "Open link", "url": "https://"}]
    assert len(created["public_reply_texts"]) == 3
    # Only the link is left to fill in.
    assert created["missing_for_activation"] == ["message_buttons.0.url"]

    giveaway = await ws.ok("POST", "/automations", 201, json={"template_key": "giveaway"})
    assert (giveaway["trigger"], giveaway["post_scope"]) == ("comment_any", "selected")
    assert giveaway["missing_for_activation"] == ["media_item_ids"]


async def test_create_refuses_unknown_templates_and_accounts(ws: Ws) -> None:
    response = await ws.call(
        "POST",
        "/automations",
        json={"template_key": "nope", "social_account_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert error_fields(response) == ["template_key", "social_account_id"]
    assert (await ws.ok("GET", "/automations"))["items"] == []


# ---------------------------------------------------------------- the definition (PUT)


async def test_put_replaces_the_whole_definition(ws: Ws, engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    older = await make_media_item(
        engine, workspace_id=ws.wid, account_id=ws.account_id, posted_at=now - timedelta(days=3)
    )
    newer = await make_media_item(
        engine, workspace_id=ws.wid, account_id=ws.account_id, posted_at=now - timedelta(days=1)
    )
    asset = await make_asset(engine, workspace_id=ws.wid)
    created = await ws.ok("POST", "/automations", 201, json={"name": "Draft"})
    starts = (now + timedelta(days=1)).replace(microsecond=0)
    body = ws.definition(
        name="Launch replies",
        trigger="comment_keyword",
        keywords=["Link", " LINK ", "Price  list", "price list", "  "],
        match_mode="exact",
        post_scope="selected",
        media_item_ids=[str(older), str(newer), str(older)],
        message_media_asset_id=str(asset),
        public_reply_texts=["Sent!", "Check your DMs, {first_name|friend}"],
        cooldown_hours=12,
        surge_order="newest_first",
        starts_at=starts.isoformat(),
        ends_at=(starts + timedelta(days=2)).isoformat(),
    )

    updated = await ws.ok("PUT", f"/automations/{created['id']}", json=body)

    assert updated["name"] == "Launch replies"
    assert updated["keywords"] == ["Link", "Price  list"]
    assert updated["match_mode"] == "exact"
    assert [p["media_item_id"] for p in updated["posts"]] == [str(newer), str(older)]
    assert updated["posts"][0]["caption"] == "New arrivals this week"
    assert updated["message_media_url"].endswith("/image/upload/sample.jpg")
    assert (updated["cooldown_hours"], updated["surge_order"]) == (12, "newest_first")
    assert updated["queue"]["order"] == "newest_first"
    # A comment's DM is a private reply, which Instagram sends without images (C-030).
    assert updated["missing_for_activation"] == ["message_media_asset_id"]
    assert updated["status"] == "draft"
    stored = await rows(
        engine,
        "SELECT keyword, keyword_normalized FROM automation_keywords WHERE automation_id = :i"
        " ORDER BY created_at",
        i=created["id"],
    )
    assert [(r["keyword"], r["keyword_normalized"]) for r in stored] == [
        ("Link", "link"),
        ("Price  list", "price list"),
    ]

    fewer = await ws.ok(
        "PUT", f"/automations/{created['id']}", json={**body, "media_item_ids": [str(newer)]}
    )
    assert [p["media_item_id"] for p in fewer["posts"]] == [str(newer)]
    everywhere = await ws.ok(
        "PUT", f"/automations/{created['id']}", json={**body, "post_scope": "all"}
    )
    assert everywhere["posts"] == []
    assert await count(engine, "automation_posts") == 0


async def test_put_refuses_what_is_not_this_workspaces(ws: Ws, engine: AsyncEngine) -> None:
    created = await ws.ok("POST", "/automations", 201, json={"name": "Draft"})
    body = ws.definition(
        social_account_id=str(uuid.uuid4()),
        post_scope="selected",
        media_item_ids=[str(uuid.uuid4())],
        message_media_asset_id=str(uuid.uuid4()),
        keywords=["k" * 101, "fine"],
    )
    response = await ws.call("PUT", f"/automations/{created['id']}", json=body)
    assert response.status_code == 422
    assert error_fields(response) == [
        "social_account_id",
        "media_item_ids",
        "message_media_asset_id",
        "keywords.0",
    ]
    video = await make_asset(engine, workspace_id=ws.wid, resource_type="video", fmt="mp4")
    response = await ws.call(
        "PUT",
        f"/automations/{created['id']}",
        json=ws.definition(message_media_asset_id=str(video)),
    )
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "message_media_asset_id", "message": "Attach an image."}
    ]
    missing = await ws.call("PUT", f"/automations/{uuid.uuid4()}", json=ws.definition())
    assert missing.status_code == 404


# ---------------------------------------------------------------- activation (FR-AUT-02)


async def test_activation_lists_every_missing_field(ws: Ws, engine: AsyncEngine) -> None:
    await make_account(engine, ws.wid, username="second.shop")
    blank = await ws.ok("POST", "/automations", 201, json={})
    response = await ws.call("POST", f"/automations/{blank['id']}/activate")
    assert response.status_code == 422
    assert response.json()["detail"] == "Finish these steps to activate the automation."
    assert error_fields(response) == ["social_account_id", "trigger", "action"]

    now = datetime.now(UTC)
    broken = ws.definition(
        trigger="comment_any",
        keywords=[],
        post_scope="all",
        message_text="",
        message_buttons=[{"title": "Shop", "url": "http://maple.example"}],
        public_reply_texts=["Thanks!", "x" * 301],
        starts_at=(now + timedelta(days=2)).isoformat(),
        ends_at=(now + timedelta(days=1)).isoformat(),
    )
    await ws.ok("PUT", f"/automations/{blank['id']}", json=broken)
    response = await ws.call("POST", f"/automations/{blank['id']}/activate")

    assert response.status_code == 422
    expected = [
        "post_scope",
        "message_text",
        "message_buttons.0.url",
        "public_reply_texts.1",
        "ends_at",
    ]
    assert error_fields(response) == expected
    messages = {e["field"]: e["message"] for e in response.json()["errors"]}
    assert messages["message_buttons.0.url"] == "Use a full link that starts with https://."
    shown = await ws.ok("GET", f"/automations/{blank['id']}")
    assert shown["missing_for_activation"] == expected
    assert shown["status"] == "draft"


async def test_the_byte_limit_includes_the_disclosure_line(ws: Ws) -> None:
    await ws.ok("PATCH", "", json={"automation_disclosure": "Sent automatically"})
    # No link buttons: with them the button template's 640 characters would apply first.
    draft = await ws.draft(message_text="a" * 990, message_buttons=[])
    response = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {
            "field": "message_text",
            "message": "Instagram allows 1,000 bytes. With a long name and the disclosure line"
            " this message is 1,010. Shorten it.",
        }
    ]
    await ws.ok("PATCH", "", json={"automation_disclosure": None})
    await ws.ok("POST", f"/automations/{draft['id']}/activate")


async def test_activate_pause_and_resume(ws: Ws, engine: AsyncEngine) -> None:
    draft = await ws.draft()
    active = await ws.ok("POST", f"/automations/{draft['id']}/activate")
    assert (active["status"], active["display_status"]) == ("active", "active")
    assert active["activated_at"] is not None
    assert active["missing_for_activation"] == []
    again = await ws.ok("POST", f"/automations/{draft['id']}/activate")
    assert again["activated_at"] == active["activated_at"]

    paused = await ws.ok("POST", f"/automations/{draft['id']}/pause")
    assert (paused["status"], paused["display_status"]) == ("paused", "paused")
    assert paused["paused_at"] is not None
    resumed = await ws.ok("POST", f"/automations/{draft['id']}/activate")
    assert (resumed["status"], resumed["paused_at"]) == ("active", None)

    other = await ws.ok("POST", "/automations", 201, json={})
    assert (await ws.ok("POST", f"/automations/{other['id']}/pause"))["status"] == "draft"
    assert (await ws.call("POST", f"/automations/{uuid.uuid4()}/activate")).status_code == 404


async def test_run_windows_show_scheduled_and_refuse_a_past_end(ws: Ws) -> None:
    now = datetime.now(UTC)
    later = await ws.draft(starts_at=(now + timedelta(days=1)).isoformat())
    scheduled = await ws.ok("POST", f"/automations/{later['id']}/activate")
    assert (scheduled["status"], scheduled["display_status"]) == ("active", "scheduled")

    past = await ws.draft(ends_at=(now - timedelta(minutes=5)).isoformat())
    response = await ws.call("POST", f"/automations/{past['id']}/activate")
    assert response.status_code == 422
    assert error_fields(response) == ["ends_at"]


async def test_the_free_plan_allows_three_active_automations(ws: Ws, engine: AsyncEngine) -> None:
    for word in ("one", "two", "three"):
        await make_automation(
            engine, workspace_id=ws.wid, account_id=ws.account_id, keywords=(word,)
        )
    draft = await ws.draft()
    response = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert response.status_code == 402
    assert response.json()["code"] == "quota_exceeded"
    assert response.json()["detail"] == "Your plan includes 3 active automations."

    await set_plan(engine, ws.wid, "pro")
    assert (await ws.ok("POST", f"/automations/{draft['id']}/activate"))["status"] == "active"


async def test_two_activations_at_once_cannot_pass_the_limit(ws: Ws, engine: AsyncEngine) -> None:
    for word in ("one", "two"):
        await make_automation(
            engine, workspace_id=ws.wid, account_id=ws.account_id, keywords=(word,)
        )
    first, second = await ws.draft(), await ws.draft()
    now = datetime.now(UTC)

    async def activate(session: AsyncSession, automation_id: str) -> None:
        await definitions.activate(
            session, uuid.UUID(automation_id), plan="free", disclosure=None, now=now
        )

    with workspace_scope(uuid.UUID(ws.wid)):
        async with AsyncSession(engine) as a, AsyncSession(engine) as b:
            await activate(a, first["id"])  # the third active one, not committed yet
            racing = asyncio.create_task(activate(b, second["id"]))
            await asyncio.sleep(0.3)
            assert not racing.done()  # waits for the first to finish
            await a.commit()
            with pytest.raises(ApiError) as refused:
                await racing
            assert refused.value.code == "quota_exceeded"

    active = await rows(engine, "SELECT id FROM automations WHERE status = 'active'")
    assert len(active) == 3


async def test_ai_replies_need_pro_and_then_the_knowledge_base(ws: Ws, engine: AsyncEngine) -> None:
    faq = await ws.ok("POST", "/automations", 201, json={"template_key": "answer_faqs"})
    response = await ws.call("POST", f"/automations/{faq['id']}/activate")
    assert response.status_code == 402
    assert response.json()["code"] == "entitlement_required"

    await set_plan(engine, ws.wid, "pro")
    response = await ws.call("POST", f"/automations/{faq['id']}/activate")
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {
            "field": "action",
            "message": "AI replies arrive with the knowledge base. Send a message for now.",
        }
    ]


async def test_an_active_automation_stays_complete(ws: Ws) -> None:
    active = await ws.active()
    for broken in ({"keywords": []}, {"trigger": None}, {"action": None, "message_text": None}):
        response = await ws.call(
            "PUT", f"/automations/{active['id']}", json=ws.definition(**broken)
        )
        assert response.status_code == 422, broken
        assert response.json()["detail"].startswith("An active automation has to stay complete")
    shown = await ws.ok("GET", f"/automations/{active['id']}")
    assert (shown["status"], shown["keywords"], shown["trigger"]) == (
        "active",
        ["link"],
        "dm_keyword",
    )
    edited = await ws.ok(
        "PUT", f"/automations/{active['id']}", json=ws.definition(keywords=["link", "shop"])
    )
    assert (edited["status"], edited["keywords"]) == ("active", ["link", "shop"])


# ---------------------------------------------------------------- overlaps and priority (FR-AUT-15)


async def test_overlaps_name_the_other_automation_and_follow_priority(
    ws: Ws, engine: AsyncEngine
) -> None:
    first = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        name="Price list",
        keywords=("price", "link"),
    )
    draft = await ws.draft(keywords=["PRICE", "shipping"])
    assert draft["overlaps"] == [
        {
            "keyword": "PRICE",
            "automation_id": str(first),
            "automation_name": "Price list",
            "this_runs_first": False,
        }
    ]
    comments = await ws.draft(trigger="comment_keyword", keywords=["price"])
    assert comments["overlaps"] == []  # another trigger type

    await ws.ok(
        "PUT",
        "/automations/priorities",
        204,
        json={"social_account_id": ws.account_id, "ordered_ids": [draft["id"], str(first)]},
    )
    reordered = await ws.ok("GET", f"/automations/{draft['id']}")
    assert reordered["overlaps"][0]["this_runs_first"] is True
    priorities = {
        str(r["id"]): r["priority"]
        for r in await rows(engine, "SELECT id, priority FROM automations")
    }
    assert priorities == {draft["id"]: 1, str(first): 2, comments["id"]: 3}


async def test_priorities_are_per_account(ws: Ws, engine: AsyncEngine) -> None:
    mine = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    second = await make_account(engine, ws.wid, username="second.shop")
    theirs = await make_automation(engine, workspace_id=ws.wid, account_id=second)
    body = {"social_account_id": ws.account_id, "ordered_ids": [str(theirs), str(mine)]}
    response = await ws.call("PUT", "/automations/priorities", json=body)
    assert response.status_code == 422
    assert error_fields(response) == ["ordered_ids"]
    body = {"social_account_id": ws.account_id, "ordered_ids": [str(uuid.uuid4())]}
    assert (await ws.call("PUT", "/automations/priorities", json=body)).status_code == 404
    body = {"social_account_id": str(uuid.uuid4()), "ordered_ids": [str(mine)]}
    assert (await ws.call("PUT", "/automations/priorities", json=body)).status_code == 404


# ---------------------------------------------------------------- the list (FR-AUT-03, 19)


async def test_the_list_filters_searches_and_sorts(ws: Ws, engine: AsyncEngine) -> None:
    second = await make_account(engine, ws.wid, username="second.shop")
    price = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        name="Answer prices",
        keywords=("price", "catalogue"),
    )
    giveaway = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        name="Giveaway",
        keywords=(),
        trigger="comment_any",
        status="paused",
    )
    await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=second,
        name="book calls",
        keywords=("book",),
        status="draft",
        activated_at=None,
    )
    thread = await make_thread(
        engine, workspace_id=ws.wid, account_id=ws.account_id, texts=("a", "b", "c")
    )
    now = datetime.now(UTC)
    for message_id in thread.message_ids[:2]:
        await make_run(
            engine,
            workspace_id=ws.wid,
            automation_id=giveaway,
            created_at=now - timedelta(seconds=2),
            trigger_message_id=message_id,
        )
    await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=price,
        created_at=now - timedelta(seconds=1),
        trigger_message_id=thread.message_ids[2],
    )

    async def names(**params: Any) -> list[str]:
        body = await ws.ok("GET", "/automations", params=params)
        return [item["name"] for item in body["items"]]

    assert await names() == ["Giveaway", "Answer prices", "book calls"]  # runs in 7 days
    assert await names(sort="name") == ["Answer prices", "book calls", "Giveaway"]
    assert await names(sort="created") == ["book calls", "Giveaway", "Answer prices"]
    assert await names(account_id=str(second)) == ["book calls"]
    assert await names(status="paused") == ["Giveaway"]
    assert sorted(await names(trigger="dm_keyword")) == ["Answer prices", "book calls"]
    assert await names(q="PRICES") == ["Answer prices"]  # the name
    assert await names(q="Catalog") == ["Answer prices"]  # a keyword
    assert await names(q="book") == ["book calls"]
    assert await names(q="%") == []

    listed = (await ws.ok("GET", "/automations"))["items"]
    assert listed[0]["stats"]["runs_7d"] == 2
    assert listed[0]["stats"]["daily_7d"][-1] == 2
    assert listed[0]["last_run_at"] is not None
    assert listed[0]["keywords"] == []
    assert sorted(listed[1]["keywords"]) == ["catalogue", "price"]
    assert listed[2]["display_status"] == "draft"


async def test_the_figures_strip_and_the_queue(ws: Ws, engine: AsyncEngine) -> None:
    second = await make_account(engine, ws.wid, username="second.shop")
    first = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    other = await make_automation(engine, workspace_id=ws.wid, account_id=second)
    await make_automation(engine, workspace_id=ws.wid, account_id=second, status="paused")
    media = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    now = datetime.now(UTC)
    for _ in range(3):
        comment = await make_comment(
            engine, workspace_id=ws.wid, account_id=ws.account_id, media_item_id=media
        )
        await make_run(
            engine,
            workspace_id=ws.wid,
            automation_id=first,
            created_at=now,
            result="queued",
            trigger_comment_id=comment,
        )
    their_post = await make_media_item(engine, workspace_id=ws.wid, account_id=second)
    comment = await make_comment(
        engine, workspace_id=ws.wid, account_id=second, media_item_id=their_post
    )
    await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=other,
        created_at=now,
        result="queued",
        trigger_comment_id=comment,
    )
    dm = await make_outbound(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        conversation_id=thread.conversation_id,
    )
    await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=first,
        created_at=now,
        trigger_message_id=thread.message_ids[0],
        private_reply_message_id=dm,
    )

    summary = await ws.ok("GET", "/automations/summary")
    assert summary == {
        "active": 2,
        "runs_7d": 5,
        "dms_sent_7d": 1,
        "waiting": 4,
        "longest_eta_minutes": 1,
    }
    shown = await ws.ok("GET", f"/automations/{first}")
    assert shown["queue"] == {"waiting": 3, "eta_minutes": 1, "order": "oldest_first"}


async def test_resuming_a_paused_automation_restarts_its_queue(
    ws: Ws, engine: AsyncEngine, queue: None
) -> None:
    held = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        status="paused",
        trigger="comment_keyword",
    )
    idle = await make_automation(
        engine, workspace_id=ws.wid, account_id=ws.account_id, status="paused", keywords=("menu",)
    )
    media = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    comment = await make_comment(
        engine, workspace_id=ws.wid, account_id=ws.account_id, media_item_id=media
    )
    await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=held,
        created_at=datetime.now(UTC),
        result="queued",
        trigger_comment_id=comment,
    )

    await ws.ok("POST", f"/automations/{idle}/activate")
    assert await jobs("drain_private_replies") == []

    await ws.ok("POST", f"/automations/{held}/activate")
    [drain] = await jobs("drain_private_replies")
    assert drain["queueing_lock"] == f"prq:{ws.account_id}"


# ---------------------------------------------------------------- runs and stats (FR-AUT-04, 16)


async def test_stats_agree_with_the_run_log(ws: Ws, engine: AsyncEngine) -> None:
    noon = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    with time_machine.travel(noon):
        automation = await make_automation(
            engine, workspace_id=ws.wid, account_id=ws.account_id, trigger="comment_keyword"
        )
        thread = await make_thread(
            engine,
            workspace_id=ws.wid,
            account_id=ws.account_id,
            texts=tuple(f"link please {i}" for i in range(6)),
        )
        media = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
        comments = [
            await make_comment(
                engine,
                workspace_id=ws.wid,
                account_id=ws.account_id,
                media_item_id=media,
                text=f"LINK {i}",
            )
            for i in range(2)
        ]
        sent = await make_outbound(
            engine,
            workspace_id=ws.wid,
            account_id=ws.account_id,
            conversation_id=thread.conversation_id,
        )
        delivered = await make_outbound(
            engine,
            workspace_id=ws.wid,
            account_id=ws.account_id,
            conversation_id=thread.conversation_id,
            status="delivered",
        )
        failed_dm = await make_outbound(
            engine,
            workspace_id=ws.wid,
            account_id=ws.account_id,
            conversation_id=thread.conversation_id,
            status="failed",
        )
        m = thread.message_ids
        runs: list[tuple[int, str, dict[str, Any]]] = [  # (days ago, result, columns)
            (
                0,
                "sent",
                {
                    "trigger_message_id": m[0],
                    "private_reply_message_id": sent,
                    "contact_id": thread.contact_id,
                    "contact_replied_at": noon,
                },
            ),
            (2, "sent", {"trigger_message_id": m[1], "private_reply_message_id": delivered}),
            (
                0,
                "failed",
                {
                    "trigger_message_id": m[2],
                    "private_reply_message_id": failed_dm,
                    "error_code": "platform_error",
                    "error_message": "Instagram refused the message.",
                },
            ),
            (3, "skipped_cooldown", {"trigger_message_id": m[3]}),
            (0, "queued", {"trigger_message_id": m[4]}),
            (10, "sent", {"trigger_message_id": m[5]}),
            (
                0,
                "partial",
                {"trigger_comment_id": comments[0], "public_reply_platform_id": "17900001"},
            ),
            (6, "skipped_expired", {"trigger_comment_id": comments[1]}),
        ]
        for i, (days, result, columns) in enumerate(runs):
            await make_run(
                engine,
                workspace_id=ws.wid,
                automation_id=automation,
                created_at=noon - timedelta(days=days, minutes=i + 1),
                result=result,
                **columns,
            )

        week = await ws.ok("GET", f"/automations/{automation}/stats", params={"days": 7})
        log = await ws.ok("GET", f"/automations/{automation}/runs", params={"limit": 100})
        month = await ws.ok("GET", f"/automations/{automation}/stats", params={"days": 30})

    week_start = datetime.combine(noon.date() - timedelta(days=6), datetime.min.time(), UTC)
    in_week = [
        r
        for r in log["items"]
        if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= week_start
    ]
    assert week["runs"] == len(in_week) == sum(d["runs"] for d in week["daily"]) == 7
    failed_in_log = [r for r in in_week if r["result"] in ("failed", "partial")]
    assert week["failures"] == sum(d["failures"] for d in week["daily"]) == len(failed_in_log)
    assert week["failures"] == 2
    assert week["dms_sent"] == 2  # sent and delivered, not the failed one
    assert week["public_replies"] == 1
    assert week["replied_24h"] == 1
    assert week["skipped"] == {"cooldown": 1, "expired": 1, "outside_window": 0}
    assert week["queued_now"] == 1
    assert len(week["daily"]) == 7
    assert week["daily"][-1]["date"] == noon.date().isoformat()
    assert week["daily"][-1] == {"date": noon.date().isoformat(), "runs": 4, "failures": 2}
    assert month["runs"] == len(log["items"]) == 8
    assert len(month["daily"]) == 30
    for days in ("5", "seven"):
        other = await ws.call("GET", f"/automations/{automation}/stats", params={"days": days})
        assert other.status_code == 422

    failed = next(r for r in log["items"] if r["result"] == "failed")
    assert failed["error"] == {
        "code": "platform_error",
        "message": "Instagram refused the message.",
    }
    assert failed["trigger_kind"] == "dm"
    assert failed["trigger_text"] == "link please 2"
    first = next(r for r in log["items"] if r["contact_replied_at"])
    assert first["contact"]["display_name"] == "Priya Shah"
    partial = next(r for r in log["items"] if r["result"] == "partial")
    assert (partial["trigger_kind"], partial["trigger_text"]) == ("comment", "LINK 0")


async def test_the_run_log_filters_and_pages(ws: Ws, engine: AsyncEngine) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    thread = await make_thread(
        engine, workspace_id=ws.wid, account_id=ws.account_id, texts=("a", "b", "c", "d", "e")
    )
    now = datetime.now(UTC)
    for i, message_id in enumerate(thread.message_ids):
        await make_run(
            engine,
            workspace_id=ws.wid,
            automation_id=automation,
            created_at=now - timedelta(minutes=i),
            result="failed" if i % 2 else "sent",
            trigger_message_id=message_id,
        )
    path = f"/automations/{automation}/runs"
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = await ws.ok("GET", path, params=params)
        seen += [r["trigger_text"] for r in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ["a", "b", "c", "d", "e"]  # newest first: message i ran i minutes ago
    failed = await ws.ok("GET", path, params={"result": "failed"})
    assert [r["trigger_text"] for r in failed["items"]] == ["b", "d"]
    bad = await ws.call("GET", path, params={"cursor": "not-a-cursor"})
    assert bad.status_code == 422


# ---------------------------------------------------------------- duplicate, pause, delete


async def test_duplicate_makes_a_draft_copy(ws: Ws, engine: AsyncEngine) -> None:
    media = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    source = await ws.active(
        trigger="comment_keyword",
        post_scope="selected",
        media_item_ids=[str(media)],
        keywords=["link", "shop"],
        public_reply_texts=["Sent!"],
    )
    copy = await ws.ok("POST", f"/automations/{source['id']}/duplicate", 201)
    assert copy["id"] != source["id"]
    assert copy["name"] == "Send the link (copy)"
    assert (copy["status"], copy["activated_at"], copy["priority"]) == ("draft", None, 100)
    for key in ("keywords", "trigger", "message_text", "message_buttons", "public_reply_texts"):
        assert copy[key] == source[key], key
    assert [p["media_item_id"] for p in copy["posts"]] == [str(media)]
    assert copy["missing_for_activation"] == []
    assert (await ws.call("POST", f"/automations/{uuid.uuid4()}/duplicate")).status_code == 404


async def test_bulk_pause(ws: Ws, engine: AsyncEngine) -> None:
    one = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    two = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    draft = await make_automation(
        engine, workspace_id=ws.wid, account_id=ws.account_id, status="draft"
    )
    ids = [str(one), str(two), str(draft)]
    missing = await ws.call("POST", "/automations/pause", json={"ids": [*ids, str(uuid.uuid4())]})
    assert missing.status_code == 404
    assert await count(engine, "automations WHERE status = 'active'") == 2

    await ws.ok("POST", "/automations/pause", 204, json={"ids": ids})
    statuses = {
        str(r["id"]): r["status"] for r in await rows(engine, "SELECT id, status FROM automations")
    }
    assert statuses == {str(one): "paused", str(two): "paused", str(draft): "draft"}


async def test_delete(ws: Ws, engine: AsyncEngine) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=automation,
        created_at=datetime.now(UTC),
        trigger_message_id=thread.message_ids[0],
    )
    await ws.ok("DELETE", f"/automations/{automation}", 204)
    assert (await ws.call("GET", f"/automations/{automation}")).status_code == 404
    assert (await ws.call("DELETE", f"/automations/{automation}")).status_code == 404
    assert await count(engine, "automation_runs") == 0
    assert await count(engine, "automation_keywords") == 0
    assert await count(engine, "messages") == 1  # the customer's message stays


# ---------------------------------------------------------------- the test tab


async def test_the_test_tab_explains_and_sends_nothing(
    ws: Ws, engine: AsyncEngine, queue: None
) -> None:
    await ws.ok("PATCH", "", json={"automation_disclosure": "Sent automatically"})
    await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        name="Price list",
        keywords=("price",),
    )
    draft = await ws.draft(
        name="Costs", keywords=["price", "Cost"], message_text="Hi {first_name|there}!"
    )
    before = [await count(engine, t) for t in ("messages", "automation_runs", "notifications")]
    jobs_before = len(await jobs())
    path = f"/automations/{draft['id']}/test"

    loses = await ws.ok("POST", path, json={"kind": "dm", "text": "What's the PRICE?"})
    assert loses["matched"] is True
    assert loses["matched_keyword"] == "price"
    assert loses["winner"]["name"] == "Price list"
    assert loses["reason"] == "“Price list” runs first: it's higher in the list."
    assert loses["rendered_message"] == "Hi Priya!\n\nSent automatically"
    assert loses["rendered_public_reply"] is None

    wins = await ws.ok("POST", path, json={"kind": "dm", "text": "cost?", "first_name": ""})
    assert (wins["matched"], wins["matched_keyword"]) == (True, "Cost")
    assert wins["winner"] == {"id": draft["id"], "name": "Costs"}
    assert wins["reason"] == "It matches. It will run once you activate it."
    assert wins["rendered_message"] == "Hi there!\n\nSent automatically"

    nothing = await ws.ok("POST", path, json={"kind": "dm", "text": "priceless"})
    assert (nothing["matched"], nothing["winner"]) == (False, None)
    assert nothing["reason"] == "None of its keywords is in this message."

    wrong = await ws.ok("POST", path, json={"kind": "comment", "text": "price"})
    assert wrong["reason"] == "This automation answers DMs, not comments."

    assert [
        await count(engine, t) for t in ("messages", "automation_runs", "notifications")
    ] == before
    assert len(await jobs()) == jobs_before


async def test_the_test_tab_checks_the_post_scope(ws: Ws, engine: AsyncEngine) -> None:
    chosen = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    other = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    active = await ws.active(
        trigger="comment_keyword",
        post_scope="selected",
        media_item_ids=[str(chosen)],
        public_reply_texts=["Sent you a DM, @{username}!"],
    )
    path = f"/automations/{active['id']}/test"
    body = {"kind": "comment", "text": "LINK pls", "username": "curious.cat"}

    hit = await ws.ok("POST", path, json={**body, "media_item_id": str(chosen)})
    assert (hit["matched"], hit["reason"]) == (True, None)
    assert hit["winner"]["id"] == active["id"]
    assert hit["rendered_public_reply"] == "Sent you a DM, @curious.cat!"
    assert hit["rendered_message"] == "Hi there! Here's the link."

    miss = await ws.ok("POST", path, json={**body, "media_item_id": str(other)})
    assert (miss["matched"], miss["winner"]) == (False, None)
    assert miss["reason"] == "This post isn't one of the automation's posts."

    unknown = await ws.call("POST", path, json={**body, "media_item_id": str(uuid.uuid4())})
    assert unknown.status_code == 422
    assert error_fields(unknown) == ["media_item_id"]


# ---------------------------------------------------------------- posts for the picker


async def test_posts_for_the_picker(ws: Ws, engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    second = await make_account(engine, ws.wid, username="second.shop")
    ids = [
        await make_media_item(
            engine,
            workspace_id=ws.wid,
            account_id=ws.account_id,
            caption=caption,
            posted_at=now - timedelta(days=days),
        )
        for caption, days in (("Monsoon SALE", 1), ("Behind the scenes", 2), ("Sale ends", 3))
    ]
    story = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE media_items SET media_type = 'story' WHERE id = :i"), {"i": story}
        )
    elsewhere = await make_media_item(engine, workspace_id=ws.wid, account_id=second, posted_at=now)

    mine = await ws.ok("GET", "/posts", params={"account_id": ws.account_id})
    assert [p["id"] for p in mine["items"]] == [str(i) for i in ids]
    assert mine["items"][0]["media_type"] == "image"
    everything = await ws.ok("GET", "/posts")
    assert everything["items"][0]["id"] == str(elsewhere)
    sale = await ws.ok("GET", "/posts", params={"account_id": ws.account_id, "q": "sale"})
    assert [p["caption"] for p in sale["items"]] == ["Monsoon SALE", "Sale ends"]

    first = await ws.ok("GET", "/posts", params={"account_id": ws.account_id, "limit": 2})
    assert len(first["items"]) == 2
    rest = await ws.ok(
        "GET",
        "/posts",
        params={"account_id": ws.account_id, "limit": 2, "cursor": first["next_cursor"]},
    )
    assert [p["id"] for p in rest["items"]] == [str(ids[2])]
    assert rest["next_cursor"] is None


# ---------------------------------------------------------------- Home checklist (FR-ACC-04)


async def test_the_checklist_ticks_once_an_automation_is_activated(ws: Ws) -> None:
    async def done() -> bool:
        overview = await ws.ok("GET", "/overview")
        steps = {s["key"]: s["done"] for s in overview["checklist"]["steps"]}
        return steps["create_automation"]

    draft = await ws.draft()
    assert await done() is False
    await ws.ok("POST", f"/automations/{draft['id']}/activate")
    assert await done() is True
    await ws.ok("POST", f"/automations/{draft['id']}/pause")
    assert await done() is True
