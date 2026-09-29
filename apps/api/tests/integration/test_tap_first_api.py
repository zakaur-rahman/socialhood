"""T4.8: tap first and the follow nudge in the automations API (FR-AUT-21, FR-AUT-22): defaults
on drafts and templates, the definition, activation, duplicate, the run log, stats and the Test
tab."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.services.automations.templates import (
    FOLLOW_NUDGE_TEXT,
    OPENING_BUTTON,
    OPENING_TEXT,
)
from tests.support.api import Clerk
from tests.support.automation_api import Ws, make_outbound, make_run, workspace
from tests.support.automations import make_automation, make_comment, make_media_item
from tests.support.inbox import make_asset, make_thread

TAP_FIELDS = (
    "confirm_first",
    "opening_text",
    "opening_button",
    "follow_nudge",
    "follow_nudge_text",
)


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


def error_fields(response: httpx.Response) -> list[str]:
    return [e["field"] for e in response.json().get("errors", [])]


def comment_definition(ws: Ws, **values: Any) -> dict[str, Any]:
    return ws.definition(
        trigger="comment_keyword",
        public_reply_texts=["Sent you a DM!"],
        confirm_first=True,
        opening_text="Hi {first_name|there}! Tap below or reply 👇",
        opening_button="Send me the link",
        follow_nudge=True,
        follow_nudge_text="Enjoying this? Follow us for more like it.",
        **values,
    )


async def test_new_comment_automations_start_with_tap_first(ws: Ws) -> None:
    blank = await ws.ok("POST", "/automations", 201, json={})
    assert {k: blank[k] for k in TAP_FIELDS} == {
        "confirm_first": True,
        "opening_text": OPENING_TEXT,
        "opening_button": OPENING_BUTTON,
        "follow_nudge": False,
        "follow_nudge_text": FOLLOW_NUDGE_TEXT,
    }
    assert OPENING_TEXT == (
        "Hi {first_name|there}! Tap the button below, or just reply here, and I'll send it right"
        " over 👇"
    )
    expected = {
        "send_link": (True, True),
        "giveaway": (True, False),
        "price_on_request": (False, False),  # AI replies ignore both
        "catalogue_by_dm": (False, False),
        "answer_faqs": (False, False),
        "book_a_call": (False, False),
    }
    for key, (confirm_first, nudge) in expected.items():
        made = await ws.ok("POST", "/automations", 201, json={"template_key": key})
        assert (made["confirm_first"], made["follow_nudge"]) == (confirm_first, nudge), key
        assert (made["opening_button"], made["follow_nudge_text"]) == (
            OPENING_BUTTON,
            FOLLOW_NUDGE_TEXT,
        )
    link = await ws.ok("POST", "/automations", 201, json={"template_key": "send_link"})
    assert link["missing_for_activation"] == ["message_buttons.0.url"]  # the defaults activate


async def test_the_definition_activation_and_duplicate(ws: Ws, engine: AsyncEngine) -> None:
    asset = await make_asset(engine, workspace_id=ws.wid)
    created = await ws.ok("POST", "/automations", 201, json={})
    path = f"/automations/{created['id']}"
    body = comment_definition(ws, message_media_asset_id=str(asset))

    stored = await ws.ok("PUT", path, json=body)
    assert {k: stored[k] for k in TAP_FIELDS} == {k: body[k] for k in TAP_FIELDS}
    # The message follows their answer as a normal DM, so it may carry the image (C-030 no
    # longer applies); without tap first it is a private reply again.
    assert stored["missing_for_activation"] == []
    plain = await ws.ok("PUT", path, json={**body, "confirm_first": False})
    assert plain["missing_for_activation"] == ["message_media_asset_id"]

    broken = await ws.ok(
        "PUT",
        path,
        json={**body, "opening_text": "  ", "opening_button": "", "follow_nudge_text": None},
    )
    assert broken["missing_for_activation"] == [
        "opening_text",
        "opening_button",
        "follow_nudge_text",
    ]
    response = await ws.call("POST", f"{path}/activate")
    assert response.status_code == 422
    assert error_fields(response) == ["opening_text", "opening_button", "follow_nudge_text"]
    too_long = await ws.call("PUT", path, json={**body, "opening_button": "x" * 21})
    assert too_long.status_code == 422

    # The opening's 1,000 bytes count the longest name and the disclosure line.
    await ws.ok("PATCH", "", json={"automation_disclosure": "Sent automatically"})
    long_opening = await ws.ok("PUT", path, json={**body, "opening_text": "a" * 985})
    assert long_opening["missing_for_activation"] == ["opening_text"]
    await ws.ok("PATCH", "", json={"automation_disclosure": None})

    # A DM trigger ignores tap first; the nudge still applies.
    dm = await ws.ok(
        "PUT",
        path,
        json={**body, "trigger": "dm_keyword", "public_reply_texts": [], "opening_text": ""},
    )
    assert dm["missing_for_activation"] == []

    await ws.ok("PUT", path, json=body)
    active = await ws.ok("POST", f"{path}/activate")
    assert active["status"] == "active"
    copy = await ws.ok("POST", f"{path}/duplicate", 201)
    assert {k: copy[k] for k in TAP_FIELDS} == {k: body[k] for k in TAP_FIELDS}
    assert copy["missing_for_activation"] == []


async def test_runs_and_stats_show_taps_waiting_runs_and_nudges(
    ws: Ws, engine: AsyncEngine
) -> None:
    now = datetime.now(UTC)
    automation = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        trigger="comment_keyword",
        confirm_first=True,
        opening_text="Hi! Tap below",
        opening_button="Send me the link",
        follow_nudge=True,
        follow_nudge_text="Follow us!",
    )
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    media = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)

    async def comment() -> uuid.UUID:
        return await make_comment(
            engine, workspace_id=ws.wid, account_id=ws.account_id, media_item_id=media
        )

    async def message(at: datetime) -> uuid.UUID:
        msg = await make_outbound(
            engine,
            workspace_id=ws.wid,
            account_id=ws.account_id,
            conversation_id=thread.conversation_id,
        )
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE messages SET occurred_at = :t WHERE id = :i"), {"t": at, "i": msg}
            )
        return msg

    fresh_opening = await message(now - timedelta(hours=2))
    old_opening = await message(now - timedelta(days=8))
    nudge = await message(now - timedelta(minutes=5))
    answered = await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=automation,
        created_at=now - timedelta(hours=1),
        trigger_comment_id=await comment(),
        confirmed_at=now - timedelta(minutes=10),
        follows_business=False,
        nudge_message_id=nudge,
    )
    await make_run(  # waiting now
        engine,
        workspace_id=ws.wid,
        automation_id=automation,
        created_at=now - timedelta(hours=2),
        result="awaiting_reply",
        trigger_comment_id=await comment(),
        private_reply_message_id=fresh_opening,
    )
    await make_run(  # its opening is past the 7 days: no longer waiting
        engine,
        workspace_id=ws.wid,
        automation_id=automation,
        created_at=now - timedelta(days=8),
        result="awaiting_reply",
        trigger_comment_id=await comment(),
        private_reply_message_id=old_opening,
    )

    stats = await ws.ok("GET", f"/automations/{automation}/stats", params={"days": 7})
    assert (stats["tapped"], stats["awaiting_now"], stats["nudged"]) == (1, 1, 1)
    log = await ws.ok("GET", f"/automations/{automation}/runs", params={"limit": 10})
    by_id = {r["id"]: r for r in log["items"]}
    shown = by_id[str(answered)]
    assert shown["confirmed_at"] is not None
    assert (shown["follows_business"], shown["nudge_message_id"]) == (False, str(nudge))
    waiting = await ws.ok(
        "GET", f"/automations/{automation}/runs", params={"result": "awaiting_reply"}
    )
    assert len(waiting["items"]) == 2
    assert all(r["confirmed_at"] is None for r in waiting["items"])


async def test_the_test_tab_renders_the_opening_and_the_nudge(ws: Ws) -> None:
    await ws.ok("PATCH", "", json={"automation_disclosure": "Sent automatically"})
    draft = await ws.draft(
        **{
            **comment_definition(ws),
            "follow_nudge_text": "Enjoying this, {first_name|friend}? Follow us.",
        }
    )
    path = f"/automations/{draft['id']}/test"
    result = await ws.ok("POST", path, json={"kind": "comment", "text": "LINK please"})
    assert result["rendered_opening"] == "Hi Priya! Tap below or reply 👇\n\nSent automatically"
    assert result["rendered_message"] == "Hi Priya! Here's the link.\n\nSent automatically"
    assert result["rendered_nudge"] == "Enjoying this, Priya? Follow us.\n\nSent automatically"
    assert result["rendered_public_reply"] == "Sent you a DM!"

    # Without tap first a commenter never answers: no opening, and no nudge can follow.
    plain = await ws.draft(**{**comment_definition(ws), "confirm_first": False})
    result = await ws.ok(
        "POST", f"/automations/{plain['id']}/test", json={"kind": "comment", "text": "link"}
    )
    assert (result["rendered_opening"], result["rendered_nudge"]) == (None, None)

    # A DM automation nudges after its message; there is no opening.
    dm = await ws.draft(follow_nudge=True, follow_nudge_text="Follow us!")
    result = await ws.ok(
        "POST", f"/automations/{dm['id']}/test", json={"kind": "dm", "text": "link"}
    )
    assert (result["rendered_opening"], result["rendered_nudge"]) == (
        None,
        "Follow us!\n\nSent automatically",
    )
