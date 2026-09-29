"""T4.7: run windows (FR-AUT-17) and automations for upcoming posts (FR-AUT-18).

Done when: one past its end time stops and notifies; a next-post automation links itself to the
post published after it was activated; an automation scoped to a scheduled post gets its media
item when the post publishes (the scheduled posts table arrives in P7, so a made-up id stands in).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks.automation_windows import end_past_windows
from socialhood.models.automations import AutomationPost
from socialhood.models.media import MediaItem
from socialhood.platforms.deps import deps_from
from socialhood.services.automations import posts
from socialhood.services.sync import sync_account_media
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_account, make_workspace
from tests.support.ingest import rows, sessions


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def links(engine: AsyncEngine) -> dict[str, list[tuple[str | None, str | None]]]:
    found: dict[str, list[tuple[str | None, str | None]]] = {}
    for r in await rows(
        engine,
        "SELECT automation_id, media_item_id, scheduled_post_id FROM automation_posts"
        " ORDER BY created_at",
    ):
        media = str(r["media_item_id"]) if r["media_item_id"] else None
        scheduled = str(r["scheduled_post_id"]) if r["scheduled_post_id"] else None
        found.setdefault(str(r["automation_id"]), []).append((media, scheduled))
    return found


async def new_post(
    engine: AsyncEngine,
    wid: str,
    account_id: str,
    posted_at: datetime,
    *,
    media_type: str = "image",
) -> MediaItem:
    """Store a post the way sync, comment intake or publishing does, and run the hook."""
    with workspace_scope(uuid.UUID(wid)):
        async with sessions(engine)() as session:
            item = MediaItem(
                social_account_id=uuid.UUID(account_id),
                platform_media_id=f"1800{uuid.uuid4().int % 10**12:012d}",
                media_type=media_type,
                caption="Just posted",
                posted_at=posted_at,
            )
            session.add(item)
            await posts.on_new_media_item(session, item)
            await session.commit()
            return item


# ---------------------------------------------------------------- run windows (FR-AUT-17)


async def test_an_automation_past_its_end_pauses_and_notifies_once(
    ws: Ws, engine: AsyncEngine
) -> None:
    now = datetime.now(UTC)
    ended = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        name="Diwali giveaway",
        ends_at=now - timedelta(minutes=1),
    )
    running = await make_automation(
        engine, workspace_id=ws.wid, account_id=ws.account_id, ends_at=now + timedelta(hours=1)
    )
    scheduled = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
    )
    paused = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        status="paused",
        ends_at=now - timedelta(days=1),
    )
    other_wid = await make_workspace(engine)
    other_account = await make_account(engine, other_wid)
    theirs = await make_automation(
        engine,
        workspace_id=other_wid,
        account_id=other_account,
        ends_at=now - timedelta(seconds=5),
    )

    assert set(await end_past_windows(sessions(engine), now=now)) == {ended, theirs}
    assert await end_past_windows(sessions(engine), now=now) == []

    statuses = {
        r["id"]: (r["status"], r["paused_at"] is not None)
        for r in await rows(engine, "SELECT id, status, paused_at FROM automations")
    }
    assert statuses[ended] == ("paused", True)
    assert statuses[theirs] == ("paused", True)
    assert statuses[running] == ("active", False)
    assert statuses[scheduled] == ("active", False)
    assert statuses[paused] == ("paused", False)

    sent = await rows(
        engine, "SELECT user_id, type, title, body, link, workspace_id FROM notifications"
    )
    assert [(str(n["user_id"]), n["type"], n["title"], n["link"]) for n in sent] == [
        (ws.user_id, "automation_ended", "Diwali giveaway ended", f"/automations/{ended}")
    ]
    shown = await ws.ok("GET", f"/automations/{ended}")
    assert (shown["status"], shown["display_status"]) == ("paused", "ended")
    later = await ws.ok("GET", f"/automations/{scheduled}")
    assert later["display_status"] == "scheduled"


# ---------------------------------------------------------------- next post (FR-AUT-18)


async def test_next_post_automations_link_to_the_first_post_after_activation(
    ws: Ws, engine: AsyncEngine
) -> None:
    now = datetime.now(UTC)
    values = {"trigger": "comment_keyword", "post_scope": "next_post"}
    waiting = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        activated_at=now - timedelta(hours=1),
        **values,
    )
    draft = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        status="draft",
        activated_at=None,
        **values,
    )
    too_late = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        activated_at=now + timedelta(minutes=30),
        **values,
    )
    second = await make_account(engine, ws.wid, username="second.shop")
    elsewhere = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=second,
        activated_at=now - timedelta(hours=1),
        **values,
    )
    await make_media_item(
        engine, workspace_id=ws.wid, account_id=ws.account_id, posted_at=now - timedelta(hours=2)
    )
    await new_post(engine, ws.wid, ws.account_id, now - timedelta(minutes=30), media_type="story")
    assert await links(engine) == {}

    post = await new_post(engine, ws.wid, ws.account_id, now)
    assert await links(engine) == {str(waiting): [(str(post.id), None)]}

    await new_post(engine, ws.wid, ws.account_id, now + timedelta(hours=1))
    linked = await links(engine)
    assert linked[str(waiting)] == [(str(post.id), None)]  # still its first post
    assert str(too_late) in linked  # activated before this later post
    assert str(draft) not in linked
    assert str(elsewhere) not in linked

    shown = await ws.ok("GET", f"/automations/{waiting}")
    assert [p["media_item_id"] for p in shown["posts"]] == [str(post.id)]
    # The editor's autosave keeps the link while the scope and account stay the same.
    body = ws.definition(
        trigger="comment_keyword", post_scope="next_post", media_item_ids=[], keywords=["link"]
    )
    kept = await ws.ok("PUT", f"/automations/{waiting}", json=body)
    assert [p["media_item_id"] for p in kept["posts"]] == [str(post.id)]


async def test_post_sync_links_the_earliest_new_post(
    app: FastAPI, ws: Ws, engine: AsyncEngine
) -> None:
    # The sandbox has posts from 1, 3 and 5 days ago; the automation was activated 4 days ago.
    now = datetime.now(UTC)
    waiting = await make_automation(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        trigger="comment_any",
        post_scope="next_post",
        keywords=(),
        activated_at=now - timedelta(days=4),
    )
    stored = await sync_account_media(
        sessions(engine),
        deps_from(app.state.http, app.state.settings),
        workspace_id=uuid.UUID(ws.wid),
        account_id=uuid.UUID(ws.account_id),
        now=now,
    )
    assert stored == 3
    linked = await rows(
        engine,
        "SELECT m.posted_at FROM automation_posts p JOIN media_items m ON m.id = p.media_item_id"
        " WHERE p.automation_id = :a",
        a=waiting,
    )
    assert len(linked) == 1
    assert abs(linked[0]["posted_at"] - (now - timedelta(days=3))) < timedelta(minutes=1)


# ---------------------------------------------------------------- scheduled posts (FR-AUT-18, P7)


async def test_a_scheduled_post_automation_gets_its_post_when_it_publishes(
    ws: Ws, engine: AsyncEngine
) -> None:
    scheduled_post_id = str(uuid.uuid4())  # scheduled_posts arrives in P7
    draft = await ws.draft(
        trigger="comment_keyword", post_scope="selected", scheduled_post_ids=[scheduled_post_id]
    )
    assert draft["posts"] == [
        {
            "media_item_id": None,
            "scheduled_post_id": scheduled_post_id,
            "caption": None,
            "thumbnail_url": None,
            "media_type": None,
            "posted_at": None,
        }
    ]
    assert draft["missing_for_activation"] == []
    await ws.ok("POST", f"/automations/{draft['id']}/activate")
    second = await make_account(engine, ws.wid, username="second.shop")
    other = await make_automation(
        engine, workspace_id=ws.wid, account_id=second, trigger="comment_keyword"
    )
    with workspace_scope(uuid.UUID(ws.wid)):
        async with sessions(engine)() as session:
            session.add(
                AutomationPost(automation_id=other, scheduled_post_id=uuid.UUID(scheduled_post_id))
            )
            await session.commit()

    with workspace_scope(uuid.UUID(ws.wid)):
        async with sessions(engine)() as session:
            item = MediaItem(
                social_account_id=uuid.UUID(ws.account_id),
                platform_media_id="18000000000000042",
                media_type="image",
                caption="Launch day",
                posted_at=datetime.now(UTC),
            )
            session.add(item)
            linked = await posts.link_scheduled_post(session, uuid.UUID(scheduled_post_id), item)
            await session.commit()

    assert linked == 1
    assert (await links(engine))[str(other)] == [(None, scheduled_post_id)]
    shown = await ws.ok("GET", f"/automations/{draft['id']}")
    assert [(p["media_item_id"], p["scheduled_post_id"], p["caption"]) for p in shown["posts"]] == [
        (str(item.id), scheduled_post_id, "Launch day")
    ]
    # The editor sends the scheduled post back; the link to the published post stays.
    body = ws.definition(
        trigger="comment_keyword", post_scope="selected", scheduled_post_ids=[scheduled_post_id]
    )
    kept = await ws.ok("PUT", f"/automations/{draft['id']}", json=body)
    assert kept["posts"][0]["media_item_id"] == str(item.id)
