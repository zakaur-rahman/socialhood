"""GR-06 and GR-07 at runtime: a story reply and a story mention are DMs that start story reply and
story mention automations through the DM runtime (matching, story scope, the heart, cooldown, run
records), and a mention leaves its record."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.services.automations.runtime import HEART, Outcome
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

CUSTOMER = "igsid_story_fan"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


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
        yield await make_world(engine, redis, deps)


async def story_automation(world: World, *keywords: str, **values: Any) -> Any:
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=keywords,
        trigger=values.pop("trigger", "story_reply"),
        name=values.pop("name", "Story link"),
        message_text=values.pop("message_text", "Hi {first_name}! Here's the link"),
        **values,
    )


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


# ---------------------------------------------------------------- GR-06: story replies


async def test_a_story_reply_with_the_keyword_gets_the_dm_and_a_run(world: World) -> None:
    automation_id = await story_automation(world, "link")
    trigger = await world.story(CUSTOMER, text_="LINK please")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.FIRED

    run = await world.run_row()
    assert (run["automation_id"], run["result"], run["matched_keyword"]) == (
        automation_id,
        "sent",
        "link",
    )
    assert run["trigger_message_id"] == trigger
    [dm] = await outbound(world)
    assert (dm["source"], dm["status"], dm["automation_run_id"]) == (
        "automation",
        "queued",
        run["id"],
    )
    assert run["private_reply_message_id"] == dm["id"]
    [stored] = await world.rows("SELECT kind FROM messages WHERE id = :id", id=trigger)
    assert stored["kind"] == "story_reply"


async def test_a_story_reply_without_keywords_answers_any_reply(world: World) -> None:
    await story_automation(world)
    trigger = await world.story(CUSTOMER, text_="Where is this cake from?")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.FIRED
    assert (await world.run_row())["matched_keyword"] == ""


async def test_a_reply_without_the_keyword_starts_nothing(world: World) -> None:
    await story_automation(world, "link")
    trigger = await world.story(CUSTOMER, text_="Where is this from?")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.NO_MATCH
    assert await world.rows("SELECT id FROM automation_runs") == []


async def test_a_story_reply_automation_ignores_plain_dms(world: World) -> None:
    await story_automation(world)
    dm = await world.dm(CUSTOMER, "link")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.NO_MATCH


async def test_a_chosen_story_answers_replies_to_that_story_only(world: World) -> None:
    await story_automation(world, post_scope="selected", story_ids=["story_a", "story_b"])
    elsewhere = await world.story("igsid_one", story_id="story_z")
    unreadable = await world.story("igsid_two", story_id=None)
    chosen = await world.story("igsid_three", story_id="story_b")
    assert elsewhere is not None
    assert unreadable is not None
    assert chosen is not None

    assert await world.run("dm", elsewhere) is Outcome.NO_MATCH
    assert await world.run("dm", unreadable) is Outcome.NO_MATCH
    assert await world.run("dm", chosen) is Outcome.FIRED
    assert [r["trigger_message_id"] for r in await world.rows("SELECT * FROM automation_runs")] == [
        chosen
    ]


async def test_a_chosen_story_falls_through_to_the_next_automation(world: World) -> None:
    await story_automation(world, post_scope="selected", story_ids=["story_a"], name="Story A")
    anything = await story_automation(world, name="Any story", priority=200)
    trigger = await world.story(CUSTOMER, story_id="story_z")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.FIRED
    assert (await world.run_row())["automation_id"] == anything


async def test_a_story_like_starts_no_story_reply_automation(world: World) -> None:
    await story_automation(world)
    like = await world.story(CUSTOMER, text_=HEART)
    assert like is not None

    assert await world.run("dm", like) is Outcome.NO_MATCH
    assert await world.rows("SELECT id FROM automation_runs") == []
    assert await outbound(world) == []


async def test_a_dm_keyword_automation_still_answers_a_story_reply(world: World) -> None:
    """Story replies used to be matched by DM keyword automations: they still are when no story
    reply automation takes the reply."""
    keyword = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
    )
    trigger = await world.story(CUSTOMER, text_="What's the price?")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.FIRED
    assert (await world.run_row())["automation_id"] == keyword


async def test_the_heart_goes_ahead_of_the_message_and_stays_out_of_the_run(world: World) -> None:
    await story_automation(world, "link", story_heart=True)
    trigger = await world.story(CUSTOMER, text_="link")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.FIRED

    run = await world.run_row()
    sent = await outbound(world)
    assert sorted(m["kind"] for m in sent) == ["sticker", "text"]
    [heart] = [m for m in sent if m["kind"] == "sticker"]
    [dm] = [m for m in sent if m["kind"] == "text"]
    assert (heart["text"], heart["source"], heart["automation_run_id"]) == (
        HEART,
        "automation",
        None,
    )
    assert run["private_reply_message_id"] == dm["id"]
    assert dm["automation_run_id"] == run["id"]


async def test_no_heart_unless_the_automation_asks_for_it(world: World) -> None:
    await story_automation(world, "link")
    trigger = await world.story(CUSTOMER, text_="link")
    assert trigger is not None

    await world.run("dm", trigger)

    assert [m["kind"] for m in await outbound(world)] == ["text"]


async def test_a_story_reply_respects_the_cooldown(world: World) -> None:
    await story_automation(world, "link", cooldown_hours=24)
    first = await world.story(CUSTOMER, text_="link")
    second = await world.story(CUSTOMER, text_="link again")
    assert first is not None
    assert second is not None

    assert await world.run("dm", first) is Outcome.FIRED
    assert await world.run("dm", second) is Outcome.SKIPPED

    assert sorted(r["result"] for r in await world.rows("SELECT * FROM automation_runs")) == [
        "sent",
        "skipped_cooldown",
    ]
    assert len(await outbound(world)) == 1


async def test_a_story_reply_saved_as_a_flow_starts_its_flow(world: World) -> None:
    flow = {
        "start": "hello",
        "steps": [{"type": "send", "id": "hello", "text": "Thanks for replying!"}],
    }
    automation_id = await story_automation(world, "link", flow_version=1)
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO automation_flows (workspace_id, automation_id, version, definition)"
                " VALUES (:w, :a, 1, CAST(:d AS jsonb))"
            ),
            {"w": world.wid, "a": automation_id, "d": json.dumps(flow)},
        )
    trigger = await world.story(CUSTOMER, text_="link")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.FIRED

    [dm] = await outbound(world)
    assert dm["text"] == "Thanks for replying!"
    run = await world.run_row()
    assert (run["flow_version"], run["step_id"]) == (1, "hello")


# ---------------------------------------------------------------- GR-07: story mentions


async def test_a_story_mention_gets_the_thank_you_and_is_recorded(world: World) -> None:
    automation_id = await story_automation(
        world,
        trigger="story_mention",
        name="Thank mentions",
        message_text="Thanks {first_name|friend}!",
    )
    trigger = await world.story(CUSTOMER, kind="story_mention")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.FIRED

    run = await world.run_row()
    assert (run["automation_id"], run["result"], run["trigger_message_id"]) == (
        automation_id,
        "sent",
        trigger,
    )
    [dm] = await outbound(world)
    assert dm["text"] == "Thanks friend!"  # no name known yet: the fallback
    [mention] = await world.rows("SELECT * FROM story_mentions")
    assert mention["message_id"] == trigger
    assert mention["media_url"].startswith("https://lookaside.fbsbx.com/")
    assert abs(mention["media_expires_at"] - (mention["mentioned_at"] + timedelta(hours=24))) < (
        timedelta(seconds=1)
    )


async def test_a_mention_starts_neither_story_reply_nor_keyword_automations(world: World) -> None:
    await story_automation(world)  # story reply, any reply
    await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, keywords=("link",)
    )
    trigger = await world.story(CUSTOMER, kind="story_mention")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.NO_MATCH
    assert len(await world.rows("SELECT id FROM story_mentions")) == 1  # still recorded


async def test_a_reply_does_not_start_a_story_mention_automation(world: World) -> None:
    await story_automation(world, trigger="story_mention")
    trigger = await world.story(CUSTOMER, text_="link")
    assert trigger is not None

    assert await world.run("dm", trigger) is Outcome.NO_MATCH
    assert await world.rows("SELECT id FROM story_mentions") == []


async def test_a_mention_with_an_expired_address_keeps_no_link(world: World) -> None:
    mentioned = datetime.now(UTC) - timedelta(days=2)
    assert await world.story(CUSTOMER, kind="story_mention", at=mentioned)

    [mention] = await world.rows("SELECT media_url, media_expires_at FROM story_mentions")
    assert mention["media_url"] is None
    assert mention["media_expires_at"] < datetime.now(UTC)


async def test_a_mention_address_with_its_own_expiry_keeps_it(world: World) -> None:
    soon = int((datetime.now(UTC) + timedelta(hours=5)).timestamp())
    url = f"https://scontent.cdninstagram.com/v/story.jpg?oe={soon:X}&oh=abc"
    assert await world.story(CUSTOMER, kind="story_mention", url=url)

    [mention] = await world.rows("SELECT media_url, media_expires_at FROM story_mentions")
    assert mention["media_url"] == url
    assert int(mention["media_expires_at"].timestamp()) == soon
