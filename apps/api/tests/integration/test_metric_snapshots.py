"""T6.5 (FR-ANL-01): the snapshot jobs' work, against a respx Graph shaped like Meta's documented
responses and against the sandbox, with the clock moved by time-machine.

Done when: each window is captured once per post (1 h and 6 h with the live counts only, insights
from 24 h, the 72 h run marking the earlier ones final), and one account row is written per day in
the workspace time zone. Both are idempotent and safe to re-run.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
import time_machine
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.tasks.insights import queue_account_days, queue_post_snapshots
from socialhood.platforms.buckets import Bucket, TokenBuckets
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.services.analytics.account_daily import due_day, snapshot_account_day
from socialhood.services.analytics.snapshots import snapshot_account_posts
from socialhood.settings import Settings
from tests.support.analytics import make_account_day
from tests.support.inbox import make_account, make_workspace
from tests.support.ingest import jobs, rows, sessions
from tests.support.instagram import GRAPH, fixture
from tests.support.post_metrics import (
    IG_USER,
    cipher,
    make_instagram_account,
    make_post,
    set_timezone,
)

T0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
FEED = {item["name"]: item for item in fixture("media_insights_feed.json")["data"]}


@dataclass
class FakeGraph:
    """Instagram's media fields and insights on respx: plain attributes a test changes."""

    base: str
    likes: dict[str, int] = field(default_factory=dict)  # media id -> like_count
    reach: dict[str, int] = field(default_factory=dict)  # media id -> reach
    gone: set[str] = field(default_factory=set)
    refuse: dict[str, str] = field(default_factory=dict)  # media id -> error fixture
    refuse_insights: dict[str, str] = field(default_factory=dict)  # insights only
    followers: int = 1204
    calls: list[str] = field(default_factory=list)
    insight_days: list[tuple[int, int]] = field(default_factory=list)

    def _error(self, media: str) -> httpx.Response | None:
        if media in self.refuse:
            return httpx.Response(400, json=fixture(self.refuse[media]))
        if media in self.gone:
            return httpx.Response(400, json=fixture("error_100_33_missing_media.json"))
        return None

    def media(self, request: httpx.Request, media: str) -> httpx.Response:
        self.calls.append(f"counts:{media}")
        likes = self.likes.get(media, 10)
        return self._error(media) or httpx.Response(
            200, json={"like_count": likes, "comments_count": likes // 10, "id": media}
        )

    def media_insights(self, request: httpx.Request, media: str) -> httpx.Response:
        self.calls.append(f"insights:{media}")
        if media in self.refuse_insights:
            return httpx.Response(400, json=fixture(self.refuse_insights[media]))
        if (error := self._error(media)) is not None:
            return error
        names = request.url.params["metric"].split(",")
        data = [dict(FEED[n]) for n in names if n in FEED]
        for item in data:
            if item["name"] == "reach":
                item["values"] = [{"value": self.reach.get(media, 1000)}]
        return httpx.Response(200, json={"data": data})

    def me(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("followers")
        return httpx.Response(200, json={"followers_count": self.followers, "id": "26000"})

    def user_insights(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if params.get("breakdown") == "follow_type":
            return httpx.Response(200, json=fixture("user_insights_follows.json"))
        self.calls.append("account_insights")
        self.insight_days.append((int(params["since"]), int(params["until"])))
        return httpx.Response(200, json=fixture("user_insights_day.json"))


@pytest.fixture
def graph(api_settings: Settings) -> Iterator[FakeGraph]:
    base = f"{GRAPH}/{api_settings.ig_graph_version}"
    fake = FakeGraph(base)
    with respx.mock(assert_all_called=False) as router:
        # The account's own insights first: its id looks like a media id.
        router.get(url__regex=rf"^{re.escape(base)}/{IG_USER}/insights").mock(
            side_effect=fake.user_insights
        )
        router.get(url__regex=rf"^{re.escape(base)}/(?P<media>\d+)/insights").mock(
            side_effect=fake.media_insights
        )
        router.get(url__regex=rf"^{re.escape(base)}/me(\?|$)").mock(side_effect=fake.me)
        router.get(url__regex=rf"^{re.escape(base)}/(?P<media>\d+)(\?|$)").mock(
            side_effect=fake.media
        )
        yield fake


@pytest.fixture
async def deps(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with httpx.AsyncClient() as http:
        yield PlatformDeps(http=http, cipher=cipher(), settings=api_settings)


@dataclass(frozen=True)
class Acct:
    workspace_id: uuid.UUID
    account_id: uuid.UUID


@pytest.fixture
async def ig(engine: AsyncEngine, clean_db: None) -> Acct:
    wid = await make_workspace(engine)
    return Acct(wid, await make_instagram_account(engine, wid))


SNAPSHOTS = (
    'SELECT media_item_id, "window", metrics, insights_final, captured_at'
    " FROM post_metric_snapshots"
)


async def snapshots(engine: AsyncEngine, post_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    if post_id is None:
        return await rows(engine, SNAPSHOTS + " ORDER BY captured_at")
    return await rows(
        engine, SNAPSHOTS + " WHERE media_item_id = :p ORDER BY captured_at", p=post_id
    )


async def run_posts(
    engine: AsyncEngine, deps: PlatformDeps, acct: Acct, **kwargs: Any
) -> list[tuple[uuid.UUID, str]] | None:
    done = await snapshot_account_posts(
        sessions(engine), deps, workspace_id=acct.workspace_id, account_id=acct.account_id, **kwargs
    )
    return None if done is None else done.captured


# ---------------------------------------------------------------- posts


async def test_each_window_is_captured_once_through_a_posts_life(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    post = await make_post(
        engine, workspace_id=ig.workspace_id, account_id=ig.account_id, posted_at=T0
    )
    media = (await rows(engine, "SELECT platform_media_id FROM media_items"))[0][
        "platform_media_id"
    ]
    timeline = [
        (timedelta(minutes=50), []),
        (timedelta(hours=1, minutes=5), ["1h"]),
        (timedelta(hours=1, minutes=20), []),  # 1 h already taken
        (timedelta(hours=6, minutes=1), ["6h"]),
        (timedelta(hours=24, minutes=15), ["24h"]),
        (timedelta(hours=25), []),
        (timedelta(hours=72, minutes=15), ["72h"]),
        (timedelta(days=7, hours=1), ["7d"]),
        (timedelta(days=30, hours=2), ["30d"]),
        (timedelta(days=31), []),
        (timedelta(days=40), []),
    ]
    for after, expected in timeline:
        graph.likes[media] = 10 + int(after.total_seconds() // 3600)
        with time_machine.travel(T0 + after, tick=False):
            captured = await run_posts(engine, deps, ig)
        assert captured == [(post, w) for w in expected], after

    stored = {s["window"]: s for s in await snapshots(engine, post)}
    assert list(stored) == ["1h", "6h", "24h", "72h", "7d", "30d"]
    # 1 h and 6 h: live counts only. From 24 h: insights too, likes from the live counts.
    assert stored["1h"]["metrics"] == {"likes": 11, "comments": 1}
    assert stored["6h"]["metrics"] == {"likes": 16, "comments": 1}
    assert stored["24h"]["metrics"] == {
        "likes": 34,
        "comments": 3,
        "reach": 1000,
        "views": 2400,
        "shares": 6,
        "saves": 21,
        "total_interactions": 86,
        "profile_visits": 12,
        "follows": 3,
    }
    # The 72 h run marked the earlier ones final; rows from 72 h on are final when written.
    assert all(s["insights_final"] for s in stored.values())
    assert stored["24h"]["captured_at"] == T0 + timedelta(hours=24, minutes=15)
    assert graph.calls.count(f"insights:{media}") == 4  # 24 h, 72 h, 7 d, 30 d
    assert graph.calls.count(f"counts:{media}") == 6
    [item] = await rows(engine, "SELECT like_count, comments_count FROM media_items")
    assert item == {"like_count": 10 + 30 * 24 + 2, "comments_count": (10 + 30 * 24 + 2) // 10}


async def test_24h_stays_provisional_until_the_72h_run(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    post = await make_post(
        engine, workspace_id=ig.workspace_id, account_id=ig.account_id, posted_at=T0
    )
    for after in (timedelta(hours=1), timedelta(hours=24)):
        with time_machine.travel(T0 + after, tick=False):
            await run_posts(engine, deps, ig)
    assert [s["insights_final"] for s in await snapshots(engine, post)] == [False, False]
    with time_machine.travel(T0 + timedelta(hours=72), tick=False):
        await run_posts(engine, deps, ig)
    assert [s["insights_final"] for s in await snapshots(engine, post)] == [True, True, True]


async def test_windows_passed_before_connecting_are_never_filled(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    """A post synced ten days after it was published only gets the windows still ahead of it."""
    old = await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0 - timedelta(days=10),
    )
    for after in (timedelta(0), timedelta(days=5), timedelta(days=20, hours=1)):
        with time_machine.travel(T0 + after, tick=False):
            await run_posts(engine, deps, ig)
    assert [s["window"] for s in await snapshots(engine, old)] == ["30d"]


async def test_without_insights_only_live_counts_are_kept(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, clean_db: None
) -> None:
    wid = await make_workspace(engine)
    acct = Acct(wid, await make_instagram_account(engine, wid, insights=False))
    post = await make_post(engine, workspace_id=wid, account_id=acct.account_id, posted_at=T0)
    for after in (timedelta(hours=24), timedelta(hours=72)):
        with time_machine.travel(T0 + after, tick=False):
            await run_posts(engine, deps, acct)
    stored = await snapshots(engine, post)
    assert [s["metrics"] for s in stored] == [{"likes": 10, "comments": 1}] * 2
    assert not [c for c in graph.calls if c.startswith("insights:")]


async def test_a_deleted_post_gets_an_empty_snapshot_once(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    post = await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0,
        platform_media_id="18100000000000009",
    )
    graph.gone.add("18100000000000009")
    with time_machine.travel(T0 + timedelta(hours=24), tick=False):
        assert await run_posts(engine, deps, ig) == [(post, "24h")]
        assert await run_posts(engine, deps, ig) == []
    [stored] = await snapshots(engine, post)
    assert stored["metrics"] == {}
    assert graph.calls == ["counts:18100000000000009"]  # no insights for a post that is gone


async def test_a_refused_insights_read_keeps_the_live_counts(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    """Media posted before the account became professional, or a permission Instagram withdrew:
    the window is captured with what is known, never an error that stops the job."""
    post = await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0,
        platform_media_id="18100000000000011",
    )
    graph.likes["18100000000000011"] = 40
    graph.refuse_insights["18100000000000011"] = "error_10_insights_permission.json"
    with time_machine.travel(T0 + timedelta(hours=24), tick=False):
        assert await run_posts(engine, deps, ig) == [(post, "24h")]
    [stored] = await snapshots(engine, post)
    assert stored["metrics"] == {"likes": 40, "comments": 4}


async def test_a_rate_limit_ends_the_pass_and_keeps_what_was_captured(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    first = await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0 - timedelta(minutes=10),
        platform_media_id="18100000000000021",
    )
    second = await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0,
        platform_media_id="18100000000000022",
    )
    graph.refuse["18100000000000022"] = "error_4_rate_limit.json"
    with time_machine.travel(T0 + timedelta(hours=1, minutes=1), tick=False):
        with pytest.raises(PlatformError) as caught:
            await run_posts(engine, deps, ig)
        assert caught.value.is_rate_limit  # the job's retry strategy waits, then runs again
        assert [s["media_item_id"] for s in await snapshots(engine)] == [first]
        graph.refuse.clear()
        assert await run_posts(engine, deps, ig) == [(second, "1h")]


async def test_a_dead_token_ends_the_pass_quietly(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0,
        platform_media_id="18100000000000031",
    )
    graph.refuse["18100000000000031"] = "error_190_expired.json"
    with time_machine.travel(T0 + timedelta(hours=1), tick=False):
        assert await run_posts(engine, deps, ig) == []
    assert await snapshots(engine) == []


async def test_accounts_without_posts_to_measure_are_skipped(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, clean_db: None
) -> None:
    wid = await make_workspace(engine)
    whatsapp = await make_account(engine, wid, platform="whatsapp", platform_account_id="10987")
    gone = await make_instagram_account(engine, wid, status="disconnected")
    for account_id in (whatsapp, gone, uuid.uuid4()):
        assert await run_posts(engine, deps, Acct(wid, account_id)) is None
    assert graph.calls == []


async def test_stories_are_not_measured(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0,
        media_type="story",
    )
    with time_machine.travel(T0 + timedelta(hours=1), tick=False):
        assert await run_posts(engine, deps, ig) == []


async def test_a_sandbox_post_grows_between_windows(
    engine: AsyncEngine, deps: PlatformDeps, clean_db: None
) -> None:
    wid = await make_workspace(engine)
    acct = Acct(wid, await make_account(engine, wid))
    post = await make_post(
        engine,
        workspace_id=wid,
        account_id=acct.account_id,
        posted_at=T0,
        media_type="reel",
        platform_media_id=f"sandbox_reel_{uuid.uuid4().hex[:6]}",
    )
    for after in (timedelta(hours=1), timedelta(hours=24), timedelta(hours=72)):
        with time_machine.travel(T0 + after, tick=False):
            assert await run_posts(engine, deps, acct) == [(post, after_window(after))]
    stored = {s["window"]: s["metrics"] for s in await snapshots(engine, post)}
    assert set(stored["1h"]) == {"likes", "comments"}
    assert stored["72h"]["reach"] >= stored["24h"]["reach"] > 0
    assert "profile_visits" not in stored["72h"]  # Reels have none


def after_window(after: timedelta) -> str:
    return {1: "1h", 24: "24h", 72: "72h"}[int(after.total_seconds() // 3600)]


async def test_the_insights_bucket_paces_the_calls(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct, redis: Redis
) -> None:
    """TR-PL-09: an empty bucket waits briefly, then hands the job back to the retry strategy
    with the seconds until a token is free (not counted as a failure)."""
    await make_post(engine, workspace_id=ig.workspace_id, account_id=ig.account_id, posted_at=T0)
    buckets = TokenBuckets(redis)
    await buckets.take_many(Bucket.IG_INSIGHTS, str(ig.account_id), 10)
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    with (
        time_machine.travel(T0 + timedelta(hours=1), tick=False),
        pytest.raises(PlatformError) as caught,
    ):
        await run_posts(engine, deps, ig, buckets=buckets, sleep=sleep)
    assert caught.value.is_rate_limit
    assert caught.value.retry_after_s
    assert waits
    assert sum(waits) <= 2.0
    assert graph.calls == []


# ---------------------------------------------------------------- the tick


def test_the_snapshot_jobs_are_periodic_bulk_jobs() -> None:
    """Job catalogue: posts every 15 minutes (agent-architecture §10), accounts hourly, both in
    the bulk lane with a lock so a slow run never overlaps the next tick (TR-JOB-02)."""
    periodic = {p.task.name: p for p in jobs_app.periodic_registry.periodic_tasks.values()}
    assert periodic["snapshot_post_metrics"].cron == "*/15 * * * *"
    assert periodic["snapshot_account_daily"].cron == "5 * * * *"
    for name in (
        "snapshot_post_metrics",
        "snapshot_account_posts",
        "snapshot_account_daily",
        "snapshot_account_day",
    ):
        assert jobs_app.tasks[name].queue == "bulk", name
    assert jobs_app.tasks["snapshot_post_metrics"].queueing_lock == "snapshot_post_metrics"


async def test_the_tick_queues_each_account_with_a_window_due_once(
    engine: AsyncEngine, graph: FakeGraph, ig: Acct, queue: None
) -> None:
    other = await make_workspace(engine)
    quiet = await make_instagram_account(engine, other, platform_account_id="17841400000000002")
    await make_post(engine, workspace_id=ig.workspace_id, account_id=ig.account_id, posted_at=T0)
    await make_post(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        posted_at=T0 - timedelta(hours=5),
    )
    await make_post(  # not due: 3 hours old
        engine, workspace_id=other, account_id=quiet, posted_at=T0 - timedelta(hours=2)
    )
    now = T0 + timedelta(hours=1)
    assert await queue_post_snapshots(sessions(engine), now) == 1
    assert await queue_post_snapshots(sessions(engine), now) == 0  # already waiting
    [job] = await jobs("snapshot_account_posts")
    assert job["queue_name"] == "bulk"
    assert job["queueing_lock"] == f"snap:{ig.account_id}"
    assert job["args"] == {"workspace_id": str(ig.workspace_id), "account_id": str(ig.account_id)}


# ---------------------------------------------------------------- account days


async def account_days(engine: AsyncEngine) -> list[dict[str, Any]]:
    return await rows(
        engine,
        "SELECT date, followers_count, metrics FROM account_daily_metrics ORDER BY date",
    )


async def test_one_account_row_per_day_in_the_workspace_time_zone(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    await set_timezone(engine, ig.workspace_id, "Asia/Kolkata")
    day = date(2026, 9, 28)
    ids = {"workspace_id": ig.workspace_id, "account_id": ig.account_id}
    assert await snapshot_account_day(sessions(engine), deps, day=day, **ids) is True
    assert await snapshot_account_day(sessions(engine), deps, day=day, **ids) is False
    [row] = await account_days(engine)
    assert row["date"] == day
    assert row["followers_count"] == 1204
    assert row["metrics"] == {
        "reach": 5400,
        "views": 9100,
        "accounts_engaged": 310,
        "total_interactions": 480,
        "follows": 12,
        "unfollows": 3,
        "profile_links_taps": 25,
    }
    # The day is Kolkata's: from 18:30 UTC the evening before, 24 hours long.
    since, until = graph.insight_days[0]
    assert since == int(datetime(2026, 9, 27, 18, 30, tzinfo=UTC).timestamp())
    assert until - since == 24 * 3600
    assert graph.calls.count("followers") == 1  # the second run read nothing


async def test_the_day_before_yesterday_is_re_read_once_the_lag_has_passed(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    day = date(2026, 9, 28)
    earlier = day - timedelta(days=2)
    await make_account_day(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        day=earlier,
        followers_count=1150,
        metrics={"reach": 4000, "follows": 1},
    )
    ids = {"workspace_id": ig.workspace_id, "account_id": ig.account_id}
    assert await snapshot_account_day(sessions(engine), deps, day=day, **ids) is True
    first, second = await account_days(engine)
    assert first["date"] == earlier
    assert first["followers_count"] == 1150  # followers stay as read that day
    assert first["metrics"]["reach"] == 5400
    assert first["metrics"]["follows"] == 12
    assert second["date"] == day
    assert len(graph.insight_days) == 2
    assert graph.insight_days[1][0] == int(datetime(2026, 9, 26, tzinfo=UTC).timestamp())


async def test_without_insights_a_day_has_followers_only(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, clean_db: None
) -> None:
    wid = await make_workspace(engine)
    account_id = await make_instagram_account(engine, wid, insights=False)
    day = date(2026, 9, 28)
    await snapshot_account_day(
        sessions(engine), deps, workspace_id=wid, account_id=account_id, day=day
    )
    assert await account_days(engine) == [{"date": day, "followers_count": 1204, "metrics": {}}]
    assert "account_insights" not in graph.calls


async def test_the_hourly_tick_queues_yesterday_from_2am_local(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct, queue: None
) -> None:
    await set_timezone(engine, ig.workspace_id, "Asia/Kolkata")
    await make_account(engine, ig.workspace_id, platform="whatsapp", platform_account_id="10987")
    await make_account_day(
        engine,
        workspace_id=ig.workspace_id,
        account_id=ig.account_id,
        day=date(2026, 9, 27),
    )
    before = datetime(2026, 9, 28, 20, 29, tzinfo=UTC)  # 01:59 on the 29th in Kolkata
    assert await queue_account_days(sessions(engine), deps, before) == 0
    at_two = datetime(2026, 9, 28, 20, 30, tzinfo=UTC)  # 02:00
    assert await queue_account_days(sessions(engine), deps, at_two) == 1
    assert await queue_account_days(sessions(engine), deps, at_two) == 0
    [job] = await jobs("snapshot_account_day")
    assert job["queue_name"] == "bulk"
    assert job["queueing_lock"] == f"acctday:{ig.account_id}:2026-09-28"
    assert job["args"]["day"] == "2026-09-28"


async def test_days_accumulate_one_row_each(
    engine: AsyncEngine, deps: PlatformDeps, graph: FakeGraph, ig: Acct
) -> None:
    """Three nights of the tick's due day, each run twice: one row per day."""
    start = datetime(2026, 9, 29, 2, 30, tzinfo=UTC)
    for night in range(3):
        with time_machine.travel(start + timedelta(days=night), tick=False):
            day = due_day("UTC", datetime.now(UTC))
            for _ in range(2):
                await snapshot_account_day(
                    sessions(engine),
                    deps,
                    workspace_id=ig.workspace_id,
                    account_id=ig.account_id,
                    day=day,
                )
    assert [r["date"] for r in await account_days(engine)] == [
        date(2026, 9, 28),
        date(2026, 9, 29),
        date(2026, 9, 30),
    ]
