"""YT4: YouTube comments against a fake YouTube. The poll (the first one a backfill, later ones live
and stopping at the first page with nothing new, the channel's own comments skipped, the video
stored from YouTube), people's actions (reply under the thread, hide, unhide refused, delete
falling back to rejecting, the daily units), nothing automatic (no automation, no auto-hide, while
the analysis still runs), and the "important" filter, flag and count."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeCall, FakeProvider, comment_ids
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.platforms.buckets import YOUTUBE_QUOTA_REACHED, YouTubeQuota
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import NOT_RESTORABLE
from socialhood.platforms.youtube.fake import CHANNEL, FakeYouTube
from socialhood.platforms.youtube.publishing import Video
from socialhood.realtime.events import commit_and_publish
from socialhood.services import youtube_comments
from socialhood.services.automations import runtime
from socialhood.services.comments import actions, analysis, queries
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.comments import reading
from tests.support.ingest import jobs, stream
from tests.support.runtime import World, make_world, platform_deps
from tests.support.youtube import make_channel

VIDEO = "vidBread01"


@dataclass
class Tube:
    world: World
    fake: FakeYouTube
    channel: uuid.UUID

    @property
    def redis(self) -> Redis:
        return self.world.redis

    async def poll(self) -> youtube_comments.PollResult | None:
        return await youtube_comments.poll_account(
            self.world.maker,
            self.redis,
            self.world.deps,
            workspace_id=self.world.wid,
            account_id=self.channel,
        )

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        return await self.world.rows(sql, **params)

    async def comment_id(self, platform_comment_id: str) -> uuid.UUID:
        [row] = await self.rows(
            "SELECT id FROM comments WHERE platform_comment_id = :p", p=platform_comment_id
        )
        return uuid.UUID(str(row["id"]))

    async def act(self, name: str, comment_id: uuid.UUID, **kwargs: Any) -> Any:
        """A person's comment action, as the API runs it."""
        with workspace_scope(self.world.wid):
            async with self.world.maker() as session:
                out = await getattr(actions, name)(
                    session, self.redis, self.world.deps, comment_id, **kwargs
                )
                await commit_and_publish(session, self.redis)
                return out

    async def clear_events(self) -> None:
        await self.redis.delete(f"events:{self.world.wid}")


@pytest.fixture
async def tube(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    fake_youtube: FakeYouTube,
    clean_db: None,
    queue: None,
) -> AsyncIterator[Tube]:
    stale = [key async for key in redis.scan_iter("bucket:youtube_units:*")]
    if stale:
        await redis.delete(*stale)
    fake_youtube.videos[VIDEO] = Video(
        id=VIDEO,
        channel_id=CHANNEL.id,
        title="Sourdough in 60 seconds",
        description="How we fold the dough",
        privacy="public",
        upload_status="processed",
        processing="succeeded",
        published_at=datetime.now(UTC) - timedelta(days=2),
        views=40,
        likes=5,
        comments=4,
    )
    async with platform_deps(api_settings, monkeypatch) as deps:
        world = await make_world(engine, redis, deps)
        yield Tube(world, fake_youtube, await make_channel(engine, world.wid))


def seed(tube: Tube) -> dict[str, str]:
    """Three viewers' threads (one with a reply), and the channel's own reply (skipped)."""
    store = tube.fake.comment_threads
    now = datetime.now(UTC)
    first = store.add(VIDEO, "Lovely crumb", at=now - timedelta(hours=3))
    second = store.add(VIDEO, "What flour is this?", at=now - timedelta(hours=2), likes=14)
    reply = store.add(VIDEO, "Same question!", parent_id=second, author="UCben", name="Ben")
    own = store.add(VIDEO, "Thanks!", parent_id=first, author=CHANNEL.id, name=CHANNEL.title)
    third = store.add(VIDEO, "Too salty for me", at=now - timedelta(hours=1))
    return {"first": first, "second": second, "reply": reply, "own": own, "third": third}


# ---------------------------------------------------------------- the poll


async def test_the_first_poll_is_a_backfill_and_later_polls_stop_early(tube: Tube) -> None:
    ids = seed(tube)
    tube.fake.comment_threads.page_size = 2

    first = await tube.poll()

    assert first == youtube_comments.PollResult(pages=2, stored=4, backfill=True)
    calls = tube.fake.named("comment_threads")
    assert [(c["channel_id"], c["video_id"]) for c in calls] == [(CHANNEL.id, None)] * 2
    stored = {r["platform_comment_id"]: r for r in await tube.rows("SELECT * FROM comments")}
    assert set(stored) == {ids["first"], ids["second"], ids["reply"], ids["third"]}  # not "own"
    assert stored[ids["reply"]]["parent_platform_comment_id"] == ids["second"]
    assert stored[ids["second"]]["like_count"] == 14
    [post] = await tube.rows(
        "SELECT * FROM media_items WHERE social_account_id = :a", a=tube.channel
    )
    assert (post["platform_media_id"], post["media_type"]) == (VIDEO, "video")  # read from YouTube
    assert post["permalink"] == f"https://www.youtube.com/watch?v={VIDEO}"
    assert post["comment_stats"]["total"] == 4
    kinds = [kind for kind, _ in await stream(tube.redis, tube.world.wid)]
    assert "comment.created" not in kinds  # a backfill publishes the post only
    assert "post.updated" in kinds
    assert await jobs("run_automation") == []
    await tube.clear_events()

    # Live: one new thread on the first page; the second page holds nothing new, so it stops.
    tube.fake.comment_threads.add(VIDEO, "Can I order a loaf?")
    second = await tube.poll()
    assert second == youtube_comments.PollResult(pages=2, stored=1, backfill=False)
    kinds = [kind for kind, _ in await stream(tube.redis, tube.world.wid)]
    assert kinds == ["comment.created", "post.updated"]

    # Nothing new: one page.
    third = await tube.poll()
    assert third == youtube_comments.PollResult(pages=1, stored=0, backfill=False)


async def test_polling_skips_once_the_day_s_units_pass_8000(tube: Tube) -> None:
    seed(tube)
    now = datetime.now(UTC)
    await YouTubeQuota(tube.redis).take(8_000, ceiling=10_000, now=now)

    assert await tube.poll() is None
    assert tube.fake.named("comment_threads") == []


async def test_a_poll_failure_is_logged_and_the_next_poll_tries_again(tube: Tube) -> None:
    seed(tube)
    tube.fake.fail_on("comment_threads", PlatformError("platform_unavailable"))
    assert await tube.poll() == youtube_comments.PollResult(pages=0, stored=0, backfill=True)
    assert (await tube.poll() or youtube_comments.PollResult()).stored == 4


async def test_the_dispatcher_queues_one_poll_per_youtube_channel(tube: Tube) -> None:
    from socialhood.jobs.tasks import youtube_comments as poll_jobs

    assert await poll_jobs.dispatch_polls(tube.world.maker) == 1
    assert await poll_jobs.dispatch_polls(tube.world.maker) == 0  # still waiting: not again

    [job] = await jobs("poll_youtube_comments")
    assert job["queueing_lock"] == f"ytcomments:{tube.channel}"
    assert (job["queue_name"], job["args"]["account_id"]) == ("bulk", str(tube.channel))


# ---------------------------------------------------------------- people's actions


async def test_people_reply_hide_and_delete_youtube_comments(tube: Tube) -> None:
    ids = seed(tube)
    await tube.poll()
    reply_id = await tube.comment_id(ids["reply"])

    out = await tube.act("reply", reply_id, text="It's stoneground rye", now=datetime.now(UTC))

    [call] = tube.fake.named("reply_comment")
    assert call["parent_id"] == ids["second"]  # under the thread's top-level comment
    assert out.public_reply.platform_id.startswith(f"{ids['second']}.")

    second_id = await tube.comment_id(ids["second"])
    hidden = await tube.act("set_hidden", second_id, hidden=True)
    assert hidden.hidden is True
    assert tube.fake.comment_threads.items[ids["second"]].status == "rejected"

    tube.fake.fail_on(
        "moderate_comment", PlatformError("platform_rejected", platform_code="processingFailure")
    )
    with pytest.raises(ApiError) as refused:
        await tube.act("set_hidden", second_id, hidden=False)
    assert (refused.value.code, refused.value.detail) == ("capability_unavailable", NOT_RESTORABLE)

    third_id = await tube.comment_id(ids["third"])
    await tube.act("delete", third_id, now=datetime.now(UTC))
    assert [c["comment_id"] for c in tube.fake.named("delete_comment")] == [ids["third"]]
    assert tube.fake.comment_threads.items[ids["third"]].status == "rejected"  # the fallback
    [row] = await tube.rows("SELECT deleted_at FROM comments WHERE id = :id", id=third_id)
    assert row["deleted_at"] is not None
    # 4 writes of 50 units (the refused unhide counted too: Google counts the call).
    assert await YouTubeQuota(tube.redis).used(datetime.now(UTC)) >= 200


async def test_writes_stop_when_the_day_s_units_are_nearly_used(tube: Tube) -> None:
    ids = seed(tube)
    await tube.poll()
    await YouTubeQuota(tube.redis).take(9_460, ceiling=10_000, now=datetime.now(UTC))

    with pytest.raises(ApiError) as refused:
        await tube.act(
            "reply", await tube.comment_id(ids["first"]), text="Thanks!", now=datetime.now(UTC)
        )

    assert (refused.value.code, refused.value.detail) == ("rate_limited", YOUTUBE_QUOTA_REACHED)
    assert int(refused.value.headers["Retry-After"]) > 0
    assert tube.fake.named("reply_comment") == []


# ---------------------------------------------------------------- nothing automatic


def spam_for(text: str) -> Any:
    def respond(call: FakeCall) -> dict[str, Any]:
        lines = dict(
            line.split(": ", 1)
            for line in call.contents[0].text.splitlines()
            if line[:1].isdigit() and ": " in line
        )
        return {
            "items": [
                reading(n, intent="spam", spam=True)
                if text in lines.get(n, "")
                else reading(n, intent="pricing")
                for n in comment_ids(call)
            ]
        }

    return respond


async def test_no_automation_or_auto_hide_ever_acts_on_a_youtube_comment(
    tube: Tube, fake_ai: FakeProvider
) -> None:
    await make_automation(
        tube.world.engine,
        workspace_id=tube.world.wid,
        account_id=tube.channel,
        trigger="comment_any",
        keywords=(),
        public_reply_texts=["Thanks!"],
    )
    async with tube.world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET auto_hide_spam = true WHERE id = :id"),
            {"id": tube.channel},
        )
    seed(tube)
    await tube.poll()  # the backfill
    spam = tube.fake.comment_threads.add(VIDEO, "FREE subscribers at my channel")
    await tube.poll()  # live

    spam_id = await tube.comment_id(spam)
    assert await jobs("run_automation") == []
    assert await tube.world.run("comment", spam_id) == runtime.Outcome.IGNORED

    fake_ai.respond("comment_analysis", spam_for("FREE"))
    with workspace_scope(tube.world.wid):
        run = await analysis.analyze_comments(
            tube.world.maker,
            tube.redis,
            tube.world.deps.settings,
            tube.world.deps,
            workspace_id=tube.world.wid,
            account_id=tube.channel,
        )
    assert (run.analysed, run.hidden) == (5, 0)  # analysed, never hidden
    [row] = await tube.rows(
        "SELECT c.hidden, a.is_spam FROM comments c JOIN comment_analyses a ON a.comment_id = c.id"
        " WHERE c.id = :id",
        id=spam_id,
    )
    assert (row["hidden"], row["is_spam"]) == (False, True)
    assert tube.fake.named("moderate_comment") == []
    assert tube.fake.named("reply_comment") == []


# ---------------------------------------------------------------- important (every platform)


async def test_important_comments_are_flagged_filtered_and_counted(
    tube: Tube, fake_ai: FakeProvider
) -> None:
    ids = seed(tube)
    await tube.poll()
    [post] = await tube.rows(
        "SELECT id FROM media_items WHERE social_account_id = :a", a=tube.channel
    )
    post_id = uuid.UUID(str(post["id"]))
    now = datetime.now(UTC)

    async def important() -> set[str]:
        with workspace_scope(tube.world.wid):
            async with tube.world.maker() as session:
                page = await queries.list_comments(
                    session, post_id, comment_filter="important", cursor=None, limit=30, now=now
                )
        assert all(c.important for c in page.items)
        return {c.platform_comment_id for c in page.items}

    # Before analysis: only the 14-like comment.
    assert await important() == {ids["second"]}
    [stats] = await tube.rows("SELECT comment_stats FROM media_items WHERE id = :id", id=post_id)
    assert stats["comment_stats"]["important"] == 1

    def respond(call: FakeCall) -> dict[str, Any]:
        lines = dict(
            line.split(": ", 1)
            for line in call.contents[0].text.splitlines()
            if line[:1].isdigit() and ": " in line
        )
        rules: dict[str, dict[str, Any]] = {
            "salty": {"sentiment": "negative"},
            "Same question": {"intent": "product_inquiry"},
        }
        return {
            "items": [
                reading(n, **next((r for k, r in rules.items() if k in lines.get(n, "")), {}))
                for n in comment_ids(call)
            ]
        }

    fake_ai.respond("comment_analysis", respond)
    with workspace_scope(tube.world.wid):
        await analysis.analyze_comments(
            tube.world.maker,
            tube.redis,
            tube.world.deps.settings,
            tube.world.deps,
            workspace_id=tube.world.wid,
            account_id=tube.channel,
        )
    assert await important() == {ids["second"], ids["reply"], ids["third"]}
    [stats] = await tube.rows("SELECT comment_stats FROM media_items WHERE id = :id", id=post_id)
    assert stats["comment_stats"]["important"] == 3

    # Answered: no longer important, and the post's count follows.
    await tube.act("reply", await tube.comment_id(ids["third"]), text="Sorry!", now=now)
    assert await important() == {ids["second"], ids["reply"]}
    [stats] = await tube.rows("SELECT comment_stats FROM media_items WHERE id = :id", id=post_id)
    assert stats["comment_stats"]["important"] == 2
