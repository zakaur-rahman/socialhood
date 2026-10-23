"""GR-06, GR-07: the story picker route, a story reply automation's definition (scope, heart,
activation), the Mentions list and the Home count."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.inbox import make_thread


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


def story_definition(ws: Ws, **values: Any) -> dict[str, Any]:
    return ws.definition(trigger="story_reply", keywords=[], message_buttons=[], **values)


# ---------------------------------------------------------------- the story picker


async def test_the_picker_lists_the_live_stories_newest_first(ws: Ws) -> None:
    body = await ws.ok("GET", f"/stories?account_id={ws.account_id}")
    assert len(body["items"]) == 2
    first, second = body["items"]
    assert first["id"].endswith("_story_0")
    assert first["posted_at"] > second["posted_at"]
    posted = datetime.fromisoformat(first["posted_at"])
    assert datetime.fromisoformat(first["expires_at"]) == posted + timedelta(hours=24)
    assert first["media_url"].startswith("https://")


async def test_the_picker_wants_one_of_the_workspaces_accounts(
    ws: Ws, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    other = await workspace(client, clerk, email="other@example.com")
    assert (await ws.call("GET", f"/stories?account_id={other.account_id}")).status_code == 404
    assert (await ws.call("GET", "/stories")).status_code == 422


# ---------------------------------------------------------------- a story reply automation


async def test_a_story_reply_automation_keeps_its_stories_and_heart(ws: Ws) -> None:
    draft = await ws.draft(
        **story_definition(
            ws,
            post_scope="selected",
            story_ids=["story_a", "story_b", "story_a"],
            story_heart=True,
        )
    )
    assert draft["trigger"] == "story_reply"
    assert (draft["post_scope"], draft["story_ids"], draft["story_heart"]) == (
        "selected",
        ["story_a", "story_b"],
        True,
    )
    assert draft["missing_for_activation"] == []

    active = await ws.ok("POST", f"/automations/{draft['id']}/activate")
    assert active["status"] == "active"


async def test_a_story_reply_on_chosen_stories_needs_a_story_to_activate(ws: Ws) -> None:
    draft = await ws.draft(**story_definition(ws, post_scope="selected"))
    assert draft["missing_for_activation"] == ["story_ids"]
    response = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["story_ids"]


async def test_a_story_reply_needs_no_keywords_and_a_mention_needs_none(ws: Ws) -> None:
    anything = await ws.active(**story_definition(ws))
    assert (anything["keywords"], anything["status"]) == ([], "active")
    thanks = await ws.draft(
        **ws.definition(trigger="story_mention", keywords=[], message_buttons=[], name="Mentions")
    )
    assert thanks["missing_for_activation"] == []


async def test_stories_are_kept_only_by_story_reply_automations(ws: Ws) -> None:
    draft = await ws.draft(
        **ws.definition(post_scope="all", story_ids=["story_a"], story_heart=True)
    )  # a DM keyword automation
    assert (draft["story_ids"], draft["story_heart"]) == ([], False)


async def test_a_story_reply_cannot_wait_for_the_next_post(ws: Ws) -> None:
    draft = await ws.draft(**story_definition(ws, post_scope="next_post"))
    assert draft["missing_for_activation"] == ["post_scope"]


async def test_the_story_templates_fill_a_draft(ws: Ws) -> None:
    for key, trigger in (
        ("story_reply_link", "story_reply"),
        ("thank_story_mentions", "story_mention"),
    ):
        draft = await ws.ok("POST", "/automations", 201, json={"template_key": key})
        assert draft["trigger"] == trigger
        assert draft["template_key"] == key


async def test_duplicating_keeps_the_stories(ws: Ws) -> None:
    draft = await ws.draft(
        **story_definition(ws, post_scope="selected", story_ids=["story_a"], story_heart=True)
    )
    copy = await ws.ok("POST", f"/automations/{draft['id']}/duplicate", 201)
    assert (copy["story_ids"], copy["story_heart"]) == (["story_a"], True)


async def test_the_test_tab_matches_story_replies(ws: Ws) -> None:
    draft = await ws.draft(**story_definition(ws, keywords=["link"]))
    hit = await ws.ok(
        "POST", f"/automations/{draft['id']}/test", json={"kind": "dm", "text": "LINK please"}
    )
    assert (hit["matched"], hit["matched_keyword"]) == (True, "link")
    miss = await ws.ok(
        "POST", f"/automations/{draft['id']}/test", json={"kind": "dm", "text": "hello"}
    )
    assert miss["matched"] is False


# ---------------------------------------------------------------- the Mentions list


async def mention(
    engine: AsyncEngine,
    ws: Ws,
    *,
    ago: timedelta,
    expires: timedelta | None,
    url: str | None = "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=1",
    contact_ref: str | None = None,
) -> uuid.UUID:
    """A mention of the workspace's account: a contact, its message and the record."""
    thread = await make_thread(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        texts=("mention",),
        contact_ref=contact_ref,
    )
    at = datetime.now(UTC) - ago
    async with engine.begin() as conn:
        row = await conn.execute(
            text(
                "INSERT INTO story_mentions (workspace_id, social_account_id, contact_id,"
                " message_id, mentioned_at, media_url, media_expires_at)"
                " VALUES (:w, :a, :c, :m, :at, :u, :e) RETURNING id"
            ),
            {
                "w": ws.wid,
                "a": ws.account_id,
                "c": thread.contact_id,
                "m": thread.message_ids[0],
                "at": at,
                "u": url,
                "e": at + expires if expires is not None else None,
            },
        )
        return uuid.UUID(str(row.scalar_one()))


async def test_mentions_are_listed_newest_first_with_a_link_while_live(
    ws: Ws, engine: AsyncEngine
) -> None:
    old = await mention(engine, ws, ago=timedelta(days=3), expires=timedelta(hours=24))
    live = await mention(engine, ws, ago=timedelta(hours=2), expires=timedelta(hours=24))

    body = await ws.ok("GET", "/story-mentions")

    assert [m["id"] for m in body["items"]] == [str(live), str(old)]
    first, second = body["items"]
    assert first["link_url"].startswith("https://lookaside.fbsbx.com/")
    assert first["link_expires_at"] is not None
    assert (second["link_url"], second["link_expires_at"]) == (None, None)  # the story is gone
    assert first["contact"]["display_name"] == "Priya Shah"
    assert first["conversation_id"] is not None
    assert body["total_7d"] == 2
    assert body["next_cursor"] is None


async def test_a_mention_whose_address_was_cleared_has_no_link(ws: Ws, engine: AsyncEngine) -> None:
    await mention(engine, ws, ago=timedelta(hours=1), expires=timedelta(hours=24), url=None)
    [item] = (await ws.ok("GET", "/story-mentions"))["items"]
    assert item["link_url"] is None


async def test_mentions_page_by_cursor(ws: Ws, engine: AsyncEngine) -> None:
    ids = [
        await mention(engine, ws, ago=timedelta(hours=h), expires=timedelta(hours=24))
        for h in (1, 2, 3)
    ]
    first = await ws.ok("GET", "/story-mentions?limit=2")
    assert [m["id"] for m in first["items"]] == [str(ids[0]), str(ids[1])]
    assert first["next_cursor"] is not None
    second = await ws.ok("GET", f"/story-mentions?limit=2&cursor={first['next_cursor']}")
    assert [m["id"] for m in second["items"]] == [str(ids[2])]
    assert second["next_cursor"] is None
    assert (await ws.call("GET", "/story-mentions?cursor=nonsense")).status_code == 422


async def test_total_7d_counts_only_the_last_week(ws: Ws, engine: AsyncEngine) -> None:
    await mention(engine, ws, ago=timedelta(days=2), expires=timedelta(hours=24))
    await mention(engine, ws, ago=timedelta(days=9), expires=timedelta(hours=24))
    body = await ws.ok("GET", "/story-mentions")
    assert (len(body["items"]), body["total_7d"]) == (2, 1)


async def test_mentions_can_be_filtered_by_account(ws: Ws, engine: AsyncEngine) -> None:
    await mention(engine, ws, ago=timedelta(hours=1), expires=timedelta(hours=24))
    assert len((await ws.ok("GET", f"/story-mentions?account_id={ws.account_id}"))["items"]) == 1
    assert (await ws.ok("GET", f"/story-mentions?account_id={uuid.uuid4()}"))["items"] == []


async def test_another_workspace_sees_none_of_them(
    ws: Ws, engine: AsyncEngine, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    await mention(engine, ws, ago=timedelta(hours=1), expires=timedelta(hours=24))
    other = await workspace(client, clerk, email="other@example.com")
    body = await other.ok("GET", "/story-mentions")
    assert (body["items"], body["total_7d"]) == ([], 0)


async def test_home_counts_the_mentions_of_the_range(ws: Ws, engine: AsyncEngine) -> None:
    await mention(engine, ws, ago=timedelta(hours=1), expires=timedelta(hours=24))
    await mention(engine, ws, ago=timedelta(hours=2), expires=timedelta(hours=24))
    body = await ws.ok("GET", "/overview?range=7d")
    assert body["current"]["story_mentions"] == 2
    assert body["previous"]["story_mentions"] == 0
