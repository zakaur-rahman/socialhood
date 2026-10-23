"""GR-10: the Live scope of comment automations. A comment on a Live is answered by automations on
the Live scope (or both), with a private reply sent while the Live is on air; a Live comment that
comes late is recorded as skipped (the Live ended) and nothing is sent. Live-only automations go
ahead of the rest in the private-reply queue."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.sandbox import outbox
from socialhood.services.automations.actions import LIVE_REPLY_WINDOW
from socialhood.services.automations.runtime import Outcome
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

LIVE_MEDIA = "sandbox_live_1"


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


async def comment_automation(world: World, surface: str, **values: Any) -> Any:
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        trigger=values.pop("trigger", "comment_keyword"),
        comment_surface=surface,
        message_text="Here's the link, {username}!",
        **values,
    )


async def live_comment(world: World, text: str = "LINK please", **values: Any) -> Any:
    comment_id = await world.comment(text, live=True, media_ref=LIVE_MEDIA, **values)
    assert comment_id is not None
    return comment_id


async def test_a_live_comment_with_the_keyword_gets_a_private_reply(world: World) -> None:
    await comment_automation(world, "live")
    comment_id = await live_comment(world)

    assert await world.run("comment", comment_id) is Outcome.FIRED
    assert (await world.run_row())["result"] == "queued"
    drained = await world.drain()

    assert drained.sent == 1
    assert len(outbox.PRIVATE_REPLIES) == 1
    assert (await world.run_row())["result"] == "sent"


async def test_a_live_automation_ignores_post_comments_and_a_posts_one_ignores_lives(
    world: World,
) -> None:
    await comment_automation(world, "live", name="Live link")
    on_post = await world.comment("LINK please")
    assert on_post is not None
    assert await world.run("comment", on_post) is Outcome.SKIPPED

    await comment_automation(world, "posts", name="Post link", priority=1)
    on_live = await live_comment(world)
    assert await world.run("comment", on_live) is Outcome.FIRED
    [run] = await world.rows(
        "SELECT a.name FROM automation_runs r JOIN automations a ON a.id = r.automation_id"
    )
    assert run["name"] == "Live link"


async def test_both_answers_posts_and_lives(world: World) -> None:
    await comment_automation(world, "both", cooldown_hours=0)
    assert await world.run("comment", await live_comment(world)) is Outcome.FIRED
    on_post = await world.comment("LINK please")
    assert on_post is not None
    assert await world.run("comment", on_post) is Outcome.FIRED


async def test_a_live_comment_that_arrives_after_the_broadcast_is_skipped(world: World) -> None:
    await comment_automation(world, "live")
    late_at = datetime.now(UTC) - LIVE_REPLY_WINDOW - timedelta(minutes=5)
    late = await live_comment(world, at=late_at)

    assert await world.run("comment", late) is Outcome.SKIPPED

    run = await world.run_row()
    assert (run["result"], run["error_code"], run["error_message"]) == (
        "skipped_expired",
        "live_ended",
        "The Live had ended",
    )
    assert (await world.drain()).sent == 0
    assert not outbox.PRIVATE_REPLIES


async def test_a_queued_live_reply_is_skipped_once_the_live_is_over(world: World) -> None:
    await comment_automation(world, "live")
    comment_id = await live_comment(world)
    assert await world.run("comment", comment_id) is Outcome.FIRED

    drained = await world.drain(now=datetime.now(UTC) + LIVE_REPLY_WINDOW + timedelta(minutes=1))

    assert (drained.sent, drained.expired) == (0, 1)
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("skipped_expired", "live_ended")
    assert not outbox.PRIVATE_REPLIES


async def test_live_replies_go_ahead_of_older_post_replies(world: World) -> None:
    await comment_automation(world, "posts", name="Post link", priority=1)
    on_post = await world.comment("LINK please", at=datetime.now(UTC) - timedelta(hours=1))
    assert on_post is not None
    assert await world.run("comment", on_post) is Outcome.FIRED
    await comment_automation(world, "live", name="Live link", priority=50)
    on_live = await live_comment(world)
    assert await world.run("comment", on_live) is Outcome.FIRED

    assert (await world.drain()).sent == 2

    [live_row] = await world.rows("SELECT platform_comment_id FROM comments WHERE is_live")
    assert outbox.PRIVATE_REPLIES[0].recipient_ref == live_row["platform_comment_id"]
