"""GR-38: visual answers in Ask Amplychat (docs/architecture/generative-ui). The tools build
their visuals from the same service numbers they return (compare_periods, metric_trend, top_posts,
sentiment_distribution, comment_topics), nothing is built with the setting off, and a run exposes
its stored visuals the way it exposes action cards: in step order, at most three, invalid ones
dropped, only for the run's owner (or an owner or admin), and not at all with the flag off."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.agent import visuals
from socialhood.agent.tools.analytics import SUMMED_NOTE, TODAY_NOTE
from socialhood.errors import ApiError
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps
from socialhood.schemas.agent import (
    MAX_VISUAL_BYTES,
    MetricComparisonVisual,
    RankedPostsVisual,
    SentimentSummaryVisual,
)
from socialhood.settings import Settings
from tests.support.agent import make_agent_run
from tests.support.agent_tools import Shop, make_shop, tool_platform
from tests.support.analytics import make_account_day, make_comment_analysis
from tests.support.api import Clerk, sign_in
from tests.support.automations import make_comment
from tests.support.inbox import make_workspace
from tests.support.post_metrics import make_instagram_account, make_post, make_windows

# Friday 23 Oct 2026, 17:30 in Kolkata: 22 Oct is the latest complete day.
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
async def platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    """Tools with AGENT_VISUALS_ENABLED on."""
    async with tool_platform(api_settings.model_copy(update={"agent_visuals_enabled": True})) as d:
        yield d


@pytest.fixture
async def quiet_platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    """Tools with it off (the default)."""
    async with tool_platform(api_settings) as deps:
        yield deps


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


@pytest.fixture
async def quiet(engine: AsyncEngine, clean_db: None, quiet_platform: PlatformDeps) -> Shop:
    return await make_shop(engine, quiet_platform)


async def seed(
    shop: Shop,
    first: str,
    last: str,
    values: Callable[[date], dict[str, int]],
    *,
    skip: tuple[str, ...] = (),
    account: uuid.UUID | None = None,
    followers: Callable[[date], int | None] = lambda day: 1000 + day.day,
) -> None:
    """One account_daily_metrics row per day first..last (ISO dates) except ``skip``."""
    day = date.fromisoformat(first)
    while day <= date.fromisoformat(last):
        if day.isoformat() not in skip:
            await make_account_day(
                shop.engine,
                workspace_id=shop.wid,
                account_id=account or shop.account_id,
                day=day,
                followers_count=followers(day),
                metrics=values(day),
            )
        day += timedelta(days=1)


async def comment_on(shop: Shop, post: uuid.UUID, at: datetime, **analysis: Any) -> uuid.UUID:
    comment = await make_comment(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        media_item_id=post,
        commented_at=at,
    )
    if analysis:
        await make_comment_analysis(
            shop.engine, workspace_id=shop.wid, comment_id=comment, **analysis
        )
    return comment


# ---------------------------------------------------------------- compare_periods


async def october(shop: Shop) -> None:
    """Reach 100 a day in Oct 1-22 except the 5th (no reading), 80 a day through September."""
    await seed(shop, "2026-10-01", "2026-10-22", lambda d: {"reach": 100}, skip=("2026-10-05",))
    await seed(shop, "2026-09-01", "2026-09-30", lambda d: {"reach": 80})
    post = await make_post(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        posted_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    for at in (
        datetime(2026, 10, 3, 9, tzinfo=UTC),
        datetime(2026, 10, 4, 9, tzinfo=UTC),
        datetime(2026, 9, 3, 9, tzinfo=UTC),
        datetime(2026, 9, 28, 9, tzinfo=UTC),  # outside the matched days
        datetime(2026, 10, 23, 9, tzinfo=UTC),  # today: not counted
    ):
        await comment_on(shop, post, at)


def metric(result: Any, name: str) -> Any:
    return next(m for m in result.metrics if m.metric == name)


async def test_this_month_against_last_month_compares_the_same_days(shop: Shop) -> None:
    await october(shop)
    result = await shop.call(
        "compare_periods",
        {
            "range": "this month",
            "compare_to": "last month",
            "metrics": ["reach", "comments"],
        },
        now=NOW,
    )
    assert (result.current.since, result.current.until) == (date(2026, 10, 1), date(2026, 10, 22))
    assert (result.previous.since, result.previous.until) == (date(2026, 9, 1), date(2026, 9, 22))
    assert result.comparable
    assert result.note is not None
    assert "same 22 days" in result.note

    reach = metric(result, "reach")
    assert (reach.current, reach.previous) == (2100, 1760)  # 21 of 22 days against 22
    assert (reach.change_pct, reach.direction) == (19.3, "up")  # (2100 - 1760) / 1760
    assert (reach.current_days, reach.previous_days) == ("21 of 22 days", None)
    comments = metric(result, "comments")
    assert (comments.current, comments.previous, comments.change_pct) == (2, 1, 100.0)

    assert TODAY_NOTE in result.caveats
    assert SUMMED_NOTE in result.caveats
    assert any("Reach has readings for 21 of 22 days" in c for c in result.caveats)

    # The visual is the same numbers: nothing in it is the model's.
    visual = result.visual
    assert isinstance(visual, MetricComparisonVisual)
    assert [(m.key, m.current, m.previous, m.change_pct) for m in visual.metrics] == [
        (m.metric, m.current, m.previous, m.change_pct) for m in result.metrics
    ]
    assert (visual.current.days, visual.previous.days) == (22, 22)
    assert visual.metrics[0].current_coverage == "21 of 22 days"
    assert visuals.size_of(visual) <= MAX_VISUAL_BYTES


async def test_followers_are_the_latest_reading_of_each_period(shop: Shop) -> None:
    await seed(
        shop, "2026-09-01", "2026-10-22", lambda d: {}, followers=lambda d: 5000 + d.toordinal()
    )
    result = await shop.call(
        "compare_periods",
        {"range": "this month", "compare_to": "last month", "metrics": ["followers"]},
        now=NOW,
    )
    followers = metric(result, "followers")
    assert (followers.current, followers.previous) == (
        5000 + date(2026, 10, 22).toordinal(),
        5000 + date(2026, 9, 22).toordinal(),
    )


async def test_without_insights_the_figure_says_why_and_is_not_zero(shop: Shop) -> None:
    denied = await make_instagram_account(shop.engine, shop.wid, insights=False)
    result = await shop.call(
        "compare_periods",
        {
            "range": "this month",
            "compare_to": "last month",
            "metrics": ["reach"],
            "account": str(denied),
        },
        now=NOW,
    )
    reach = metric(result, "reach")
    assert (reach.current, reach.previous, reach.change_pct) == (None, None, None)
    reason = "Insights aren't granted for @maple.bakery, so this isn't available."
    assert reach.unavailable == reason
    assert reason in result.caveats
    assert isinstance(result.visual, MetricComparisonVisual)
    assert result.visual.metrics[0].unavailable == reason  # one string for both


async def test_periods_of_different_length_show_no_change(shop: Shop) -> None:
    await seed(shop, "2026-08-01", "2026-09-30", lambda d: {"reach": 10})
    result = await shop.call(
        "compare_periods",
        {"range": "1-30 Sep 2026", "compare_to": "1-7 Aug 2026", "metrics": ["reach"]},
        now=NOW,
    )
    assert not result.comparable
    reach = metric(result, "reach")
    assert (reach.current, reach.previous) == (300, 70)
    assert (reach.change_pct, reach.direction) == (None, None)
    assert isinstance(result.visual, MetricComparisonVisual)
    assert not result.visual.comparable
    assert result.visual.metrics[0].tone == "neutral"


async def test_without_compare_to_the_period_before_is_as_long(shop: Shop) -> None:
    # Mon 19 to Fri 23 Oct, minus today: 4 days, against the 4 days before.
    result = await shop.call(
        "compare_periods", {"range": "this week", "metrics": ["views"]}, now=NOW
    )
    assert (result.current.since, result.current.until) == (date(2026, 10, 19), date(2026, 10, 22))
    assert (result.previous.since, result.previous.until) == (
        date(2026, 10, 15),
        date(2026, 10, 18),
    )
    assert result.comparable


async def test_a_period_that_starts_today_has_no_complete_day(shop: Shop) -> None:
    with pytest.raises(ApiError) as caught:
        await shop.call("compare_periods", {"range": "today"}, now=NOW)
    assert caught.value.code == "validation_error"


async def test_nothing_is_built_with_the_setting_off(quiet: Shop) -> None:
    await october(quiet)
    result = await quiet.call(
        "compare_periods",
        {"range": "this month", "compare_to": "last month", "metrics": ["reach"]},
        now=NOW,
    )
    assert metric(result, "reach").change_pct == 19.3  # the answer is the same
    assert result.visual is None


async def test_any_member_can_compare_periods(shop: Shop) -> None:
    result = await shop.call("compare_periods", {"metrics": ["reach"]}, role=Role.AGENT, now=NOW)
    assert result.metrics


# ---------------------------------------------------------------- metric_trend


async def test_a_trend_has_a_point_a_day_with_gaps_as_none(shop: Shop) -> None:
    await seed(
        shop,
        "2026-10-01",
        "2026-10-22",
        lambda d: {"reach": 300 if d.day == 12 else 100},
        skip=("2026-10-05",),
    )
    result = await shop.call("metric_trend", {"metric": "reach", "range": "this month"}, now=NOW)
    assert result.granularity == "day"
    assert len(result.points) == 22
    assert result.points[4].value is None  # 5 Oct: a gap, not a zero
    assert (result.known_points, result.first.day, result.last.day) == (
        21,
        date(2026, 10, 1),
        date(2026, 10, 22),
    )
    assert (result.highest.value, result.highest.day) == (300, date(2026, 10, 12))
    assert (result.change_pct, result.direction) == (0.0, "flat")
    assert any("1 of 22 days have no reading" in c for c in result.caveats)


async def test_a_long_trend_is_weekly(shop: Shop) -> None:
    await seed(shop, "2026-07-01", "2026-10-22", lambda d: {"reach": 10})
    result = await shop.call(
        "metric_trend", {"metric": "reach", "range": "the last 90 days"}, now=NOW
    )
    assert result.granularity == "week"
    assert len(result.points) <= 14
    assert 70 in {p.value for p in result.points}  # a full Monday-Sunday week


async def test_a_trend_without_readings_says_why(shop: Shop) -> None:
    denied = await make_instagram_account(shop.engine, shop.wid, insights=False)
    result = await shop.call(
        "metric_trend", {"metric": "reach", "range": "this month", "account": str(denied)}, now=NOW
    )
    assert (result.known_points, result.first, result.change_pct) == (0, None, None)
    assert "Insights aren't granted for @maple.bakery" in " ".join(result.caveats)


# ---------------------------------------------------------------- top_posts and sentiment


async def two_posts(shop: Shop) -> tuple[uuid.UUID, uuid.UUID]:
    posted = NOW - timedelta(days=5)
    low = await make_post(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        posted_at=posted,
        caption="Quiet one",
    )
    high = await make_post(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        posted_at=posted + timedelta(hours=1),
        caption="<img src=x onerror=alert(1)> Summer sale",
    )
    for post, reach in ((low, 500), (high, 2400)):
        await make_windows(
            shop.engine,
            workspace_id=shop.wid,
            post_id=post,
            posted_at=posted,
            windows={"24h": {"reach": reach, "views": reach * 2, "likes": 10, "comments": 1}},
        )
    return low, high


async def test_top_posts_draws_the_ranking_it_returns(shop: Shop) -> None:
    low, high = await two_posts(shop)
    result = await shop.call(
        "top_posts", {"metric": "reach", "range": "the last 30 days", "at_age": "24 hours"}, now=NOW
    )
    assert [i.post_id for i in result.items] == [high, low]
    visual = result.visual
    assert isinstance(visual, RankedPostsVisual)
    assert [(i.post_id, i.value) for i in visual.items] == [
        (i.post_id, i.value) for i in result.items
    ]
    assert (visual.metric_key, visual.considered, visual.age_label) == (
        "reach",
        2,
        "Figures at 24 hours",
    )
    assert visual.items[0].caption is not None
    assert visual.items[0].caption.startswith("<img")  # customer text kept as text, never HTML
    assert visual.items[0].thumbnail_url == "https://scontent.cdninstagram.com/v/post.jpg"
    assert visuals.size_of(visual) <= MAX_VISUAL_BYTES


async def test_a_ranking_with_no_posts_has_no_visual(shop: Shop) -> None:
    result = await shop.call("top_posts", {"metric": "reach"}, now=NOW)
    assert (result.items, result.visual) == ([], None)


async def test_top_posts_builds_nothing_with_the_setting_off(quiet: Shop) -> None:
    await two_posts(quiet)
    result = await quiet.call("top_posts", {"metric": "reach", "at_age": "24 hours"}, now=NOW)
    assert len(result.items) == 2
    assert result.visual is None


async def test_sentiment_and_topics_draw_the_split_with_the_topics(shop: Shop) -> None:
    post = await make_post(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        posted_at=NOW - timedelta(days=3),
    )
    at = NOW - timedelta(days=1)
    await comment_on(shop, post, at, sentiment="negative", topic="price")
    await comment_on(shop, post, at, sentiment="negative", topic="price")
    await comment_on(shop, post, at, sentiment="positive", topic="colours")
    await comment_on(shop, post, at, sentiment="neutral", topic="shipping")
    await comment_on(shop, post, at)  # not analysed yet

    split = await shop.call("sentiment_distribution", {"range": "the last 30 days"}, now=NOW)
    plain = split.visual
    assert isinstance(plain, SentimentSummaryVisual)
    assert (plain.total, plain.positive, plain.neutral, plain.negative) == (5, 1, 1, 2)
    assert (plain.not_analysed, plain.topics) == (1, [])
    assert plain.positive == split.positive
    assert plain.not_analysed == split.not_analysed

    topics = await shop.call("comment_topics", {"range": "the last 30 days"}, now=NOW)
    full = topics.visual
    assert isinstance(full, SentimentSummaryVisual)
    assert (full.total, full.positive, full.negative) == (5, 1, 2)
    assert (full.topics[0].label, full.topics[0].count) == ("price", 2)
    # The split on screen is one a tool returned (the eval checks every figure the same way).
    assert topics.split is not None
    assert (topics.split.positive, topics.split.neutral, topics.split.negative) == (1, 1, 2)
    assert full.scope == plain.scope  # the run shows the one with topics (agent_runs._visuals)

    # A sentiment filter is a slice of the split: no visual.
    negative = await shop.call(
        "comment_topics", {"range": "the last 30 days", "sentiment": "negative"}, now=NOW
    )
    assert negative.visual is None


async def test_no_comments_no_sentiment_visual(shop: Shop) -> None:
    assert (await shop.call("sentiment_distribution", {}, now=NOW)).visual is None
    assert (await shop.call("comment_topics", {}, now=NOW)).visual is None


# ---------------------------------------------------------------- the run exposes its visuals


def ranking(label: str = "Reel of 1 Oct") -> dict[str, Any]:
    return visuals.ranked_posts(
        metric="reach",
        period=None,
        age_label=None,
        considered=1,
        rows=[visuals.RankedInput(uuid.uuid4(), label, "reel", "A caption", None, 120.0)],
    ).model_dump(mode="json")


def tool_step(visual: Any = None, *, status: str = "succeeded", **result: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"summary": "Ranked 1 posts", "refs": [], "caveats": [], **result}
    if visual is not None:
        body["visual"] = visual
    return {"kind": "tool", "tool": "top_posts", "tier": "read", "status": status, "result": body}


REPORT = {"kind": "report", "args": {}, "result": {"summary": "Wrote the answer"}}


@pytest.fixture
async def desk(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> dict[str, Any]:
    owner, me = await sign_in(client, clerk, email="owner@example.com")
    member_clerk = clerk.add(email="member@example.com", first_name="Ben", last_name="Das")
    member_me = (await client.get("/v1/me", headers=clerk.headers(member_clerk))).json()
    wid = me["workspaces"][0]["id"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'agent')"
            ),
            {"w": wid, "u": member_me["id"]},
        )
    return {
        "app": app,
        "client": client,
        "clerk": clerk,
        "engine": engine,
        "wid": wid,
        "owner": owner,
        "owner_id": me["id"],
        "member": member_clerk,
        "member_id": member_me["id"],
    }


async def fetch(desk: dict[str, Any], path: str, who: str | None = None) -> httpx.Response:
    response: httpx.Response = await desk["client"].get(
        f"/v1/w/{desk['wid']}{path}", headers=desk["clerk"].headers(who or desk["owner"])
    )
    return response


async def run_with(desk: dict[str, Any], steps: list[dict[str, Any]], **values: Any) -> str:
    values.setdefault("requested_by_user_id", desk["owner_id"])
    made = await make_agent_run(
        desk["engine"], workspace_id=desk["wid"], steps=[*steps, REPORT], **values
    )
    return str(made.id)


async def test_a_run_lists_its_visuals_in_step_order(
    desk: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(desk["app"].state.settings, "agent_visuals_enabled", True)
    first, second = ranking("Reel of 1 Oct"), ranking("Reel of 2 Oct")
    run = await run_with(desk, [tool_step(first), tool_step(), tool_step(second)])
    detail = (await fetch(desk, f"/agent/runs/{run}")).json()
    assert [v["items"][0]["label"] for v in detail["visuals"]] == ["Reel of 1 Oct", "Reel of 2 Oct"]
    assert detail["visuals"][0]["kind"] == "ranked_posts"
    # The steps don't carry the visual a second time.
    assert all("visual" not in (s["result"] or {}) for s in detail["steps"])
    listed = (await fetch(desk, "/agent/runs")).json()["items"]
    assert listed[0]["visuals"] == detail["visuals"]


async def test_the_flag_off_leaves_the_api_without_visuals(desk: dict[str, Any]) -> None:
    run = await run_with(desk, [tool_step(ranking())])
    detail = (await fetch(desk, f"/agent/runs/{run}")).json()
    assert detail["visuals"] == []
    assert all("visual" not in (s["result"] or {}) for s in detail["steps"])
    assert (await fetch(desk, "/agent/runs")).json()["items"][0]["visuals"] == []


async def test_at_most_three_visuals_and_bad_ones_are_dropped(
    desk: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(desk["app"].state.settings, "agent_visuals_enabled", True)
    steps = [
        tool_step({"kind": "ranked_posts"}),  # missing fields
        tool_step({"kind": "from_a_newer_version", "title": "x"}),
        tool_step("not an object"),
        *[tool_step(ranking(f"Reel of {n} Oct")) for n in range(1, 6)],
    ]
    run = await run_with(desk, steps)
    visuals_shown = (await fetch(desk, f"/agent/runs/{run}")).json()["visuals"]
    assert [v["items"][0]["label"] for v in visuals_shown] == [
        "Reel of 1 Oct",
        "Reel of 2 Oct",
        "Reel of 3 Oct",
    ]


async def test_a_failed_step_shows_no_visual(
    desk: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(desk["app"].state.settings, "agent_visuals_enabled", True)
    run = await run_with(desk, [tool_step(ranking(), status="failed")], status="partial")
    assert (await fetch(desk, f"/agent/runs/{run}")).json()["visuals"] == []


async def test_visuals_follow_the_runs_visibility(
    desk: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(desk["app"].state.settings, "agent_visuals_enabled", True)
    mine = await run_with(desk, [tool_step(ranking())], requested_by_user_id=desk["member_id"])
    # The team member sees their own run's visual; another member's run is a 404 for them.
    assert (await fetch(desk, f"/agent/runs/{mine}", desk["member"])).json()["visuals"]
    owners = await run_with(desk, [tool_step(ranking())])
    hidden = await fetch(desk, f"/agent/runs/{owners}", desk["member"])
    assert hidden.status_code == 404
    assert "visuals" not in hidden.text
    # The owner sees every run, the member's included.
    assert (await fetch(desk, f"/agent/runs/{mine}")).json()["visuals"]
    listed = (await fetch(desk, "/agent/runs", desk["member"])).json()["items"]
    assert [r["id"] for r in listed] == [mine]


async def test_another_workspaces_runs_never_show_their_visuals(
    desk: dict[str, Any], monkeypatch: pytest.MonkeyPatch, engine: AsyncEngine
) -> None:
    monkeypatch.setattr(desk["app"].state.settings, "agent_visuals_enabled", True)
    other = await make_workspace(engine)
    theirs = await make_agent_run(engine, workspace_id=other, steps=[tool_step(ranking()), REPORT])
    response = await fetch(desk, f"/agent/runs/{theirs.id}")
    assert response.status_code == 404
    assert (await fetch(desk, "/agent/runs")).json()["items"] == []
