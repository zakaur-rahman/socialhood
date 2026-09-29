"""T6.5 (FR-ANL-01): the Instagram adapter's live counts, media insights and account insights
against responses shaped like Meta's documented ones (TR-TEST-01 contract layer). A value Instagram
does not give is None, never an error that stops the snapshot job; retryable errors and a dead
token still raise."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import AccountInsights, MediaCounts, MediaInsights
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram import insights, oauth
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH, fixture

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
)
V = f"{GRAPH}/{SETTINGS.ig_graph_version}"
IG = "17841400000000001"
MEDIA = "18100000000000003"


@pytest.fixture
async def adapter() -> AsyncIterator[InstagramAdapter]:
    async with httpx.AsyncClient() as http:
        yield InstagramAdapter(PlatformDeps(http, TokenCipher([new_key()]), SETTINGS))


def account(adapter: InstagramAdapter, *, insights_scope: bool = True) -> SocialAccount:
    scopes = [*oauth.BASE_SCOPES, *([oauth.INSIGHTS_SCOPE] if insights_scope else [])]
    return SocialAccount(
        platform="instagram",
        platform_account_id=IG,
        username="maple.bakery",
        access_token_enc=adapter.deps.cipher.encrypt("IGQVJlong"),
        scopes=scopes,
    )


def metrics_asked(route: respx.Route) -> list[list[str]]:
    return [call.request.url.params["metric"].split(",") for call in route.calls]


# ---------------------------------------------------------------- live counts


@respx.mock
async def test_live_counts_come_from_the_media_fields(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/{MEDIA}").respond(200, json=fixture("media_counts.json"))
    counts = await adapter.get_media_counts(account(adapter), MEDIA)
    assert counts == MediaCounts(like_count=57, comments_count=4)
    request = route.calls.last.request
    assert request.url.params["fields"] == "like_count,comments_count"
    assert request.headers["authorization"] == "Bearer IGQVJlong"


@respx.mock
async def test_a_hidden_like_count_is_unknown(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/{MEDIA}").respond(200, json={"comments_count": 4, "id": MEDIA})
    counts = await adapter.get_media_counts(account(adapter), MEDIA)
    assert counts == MediaCounts(like_count=None, comments_count=4)


@respx.mock
async def test_a_deleted_post_has_no_counts(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/{MEDIA}").respond(400, json=fixture("error_100_33_missing_media.json"))
    assert await adapter.get_media_counts(account(adapter), MEDIA) is None


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (400, "error_4_rate_limit.json", "platform_rate_limited"),
        (401, "error_190_expired.json", "account_needs_reconnect"),
    ],
    ids=["rate-limit", "dead-token"],
)
@respx.mock
async def test_rate_limits_and_dead_tokens_still_raise(
    adapter: InstagramAdapter, status: int, body: str, code: str
) -> None:
    respx.get(f"{V}/{MEDIA}").respond(status, json=fixture(body))
    with pytest.raises(PlatformError) as caught:
        await adapter.get_media_counts(account(adapter), MEDIA)
    assert caught.value.code == code


async def test_only_instagram_ids_reach_the_graph_path(adapter: InstagramAdapter) -> None:
    with pytest.raises(PlatformError):
        await adapter.get_media_counts(account(adapter), "../me/messages")


# ---------------------------------------------------------------- media insights


@respx.mock
async def test_feed_post_insights_ask_for_every_feed_metric(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/{MEDIA}/insights").respond(
        200, json=fixture("media_insights_feed.json")
    )
    got = await adapter.get_media_insights(account(adapter), MEDIA, media_type="carousel")
    assert metrics_asked(route) == [list(insights.FEED_METRICS)]
    assert "impressions" not in metrics_asked(route)[0]  # gone for media since July 2024
    assert got == MediaInsights(
        reach=1850,
        views=2400,
        likes=55,
        comments=4,
        shares=6,
        saves=21,  # Instagram's "saved"
        total_interactions=86,
        profile_visits=12,
        follows=3,
    )


@respx.mock
async def test_reel_insights_skip_what_reels_do_not_offer(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/{MEDIA}/insights").respond(
        200, json=fixture("media_insights_reel.json")
    )
    got = await adapter.get_media_insights(account(adapter), MEDIA, media_type="reel")
    assert set(metrics_asked(route)[0]) == set(insights.REELS_METRICS)
    assert {"profile_visits", "follows"}.isdisjoint(metrics_asked(route)[0])
    assert (got.reach, got.saves, got.total_interactions) == (5120, 64, 336)
    assert (got.profile_visits, got.follows) == (None, None)


@respx.mock
async def test_story_insights_skip_likes_comments_and_saves(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/{MEDIA}/insights").respond(200, json={"data": []})
    got = await adapter.get_media_insights(account(adapter), MEDIA, media_type="story")
    assert {"likes", "comments", "saved"}.isdisjoint(metrics_asked(route)[0])
    assert got == MediaInsights()  # insights not ready yet: an empty data set, never zeros


@respx.mock
async def test_an_incompatible_metric_is_read_one_by_one_and_left_unknown(
    adapter: InstagramAdapter,
) -> None:
    feed = {item["name"]: item for item in fixture("media_insights_feed.json")["data"]}
    refused = {"views", "follows"}

    def answer(request: httpx.Request) -> httpx.Response:
        names = request.url.params["metric"].split(",")
        if refused & set(names):
            return httpx.Response(400, json=fixture("error_100_incompatible_metric.json"))
        return httpx.Response(200, json={"data": [feed[n] for n in names]})

    route = respx.get(f"{V}/{MEDIA}/insights").mock(side_effect=answer)
    got = await adapter.get_media_insights(account(adapter), MEDIA, media_type="image")
    assert len(route.calls) == 1 + len(insights.FEED_METRICS)
    assert (got.views, got.follows) == (None, None)
    assert (got.reach, got.saves, got.profile_visits) == (1850, 21, 12)


@pytest.mark.parametrize(
    "body",
    ["error_10_insights_permission.json", "error_100_33_missing_media.json"],
    ids=["no-permission", "missing-media"],
)
@respx.mock
async def test_a_refused_insights_read_is_all_unknown(adapter: InstagramAdapter, body: str) -> None:
    route = respx.get(f"{V}/{MEDIA}/insights").respond(400, json=fixture(body))
    assert await adapter.get_media_insights(account(adapter), MEDIA, media_type="image") == (
        MediaInsights()
    )
    assert len(route.calls) == 1  # no metric-by-metric retry for a refusal of the whole post


@respx.mock
async def test_an_insights_outage_raises(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/{MEDIA}/insights").respond(
        500, json={"error": {"code": 2, "message": "Service temporarily unavailable"}}
    )
    with pytest.raises(PlatformError) as caught:
        await adapter.get_media_insights(account(adapter), MEDIA, media_type="image")
    assert caught.value.retryable


# ---------------------------------------------------------------- account insights


@respx.mock
async def test_account_day_reads_followers_and_that_days_insights(
    adapter: InstagramAdapter,
) -> None:
    me = respx.get(f"{V}/me").respond(200, json=fixture("me_followers.json"))

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("breakdown") == "follow_type":
            return httpx.Response(200, json=fixture("user_insights_follows.json"))
        return httpx.Response(200, json=fixture("user_insights_day.json"))

    route = respx.get(f"{V}/{IG}/insights").mock(side_effect=answer)
    got = await adapter.get_account_insights(account(adapter), date(2026, 9, 28), tz="Asia/Kolkata")
    assert me.calls.last.request.url.params["fields"] == "followers_count"
    assert got == AccountInsights(
        followers_count=1204,
        reach=5400,
        views=9100,
        accounts_engaged=310,
        total_interactions=480,
        follows=12,
        unfollows=3,
        profile_links_taps=25,
    )
    main, follows = (call.request.url.params for call in route.calls)
    assert main["metric"].split(",") == list(insights.ACCOUNT_METRICS)
    assert (main["period"], main["metric_type"]) == ("day", "total_value")
    assert "breakdown" not in main
    assert (follows["metric"], follows["breakdown"]) == ("follows_and_unfollows", "follow_type")
    # The workspace's day: midnight to midnight in Asia/Kolkata (UTC+05:30).
    start = datetime(2026, 9, 27, 18, 30, tzinfo=UTC)
    assert int(main["since"]) == int(start.timestamp())
    assert int(main["until"]) - int(main["since"]) == 24 * 3600


def test_day_bounds_follow_daylight_saving() -> None:
    since, until = insights.day_bounds(date(2026, 10, 25), "Europe/London")  # clocks go back
    assert until - since == 25 * 3600
    assert since == int(datetime(2026, 10, 24, 23, 0, tzinfo=UTC).timestamp())


@respx.mock
async def test_without_the_insights_scope_only_followers_are_read(
    adapter: InstagramAdapter,
) -> None:
    respx.get(f"{V}/me").respond(200, json=fixture("me_followers.json"))
    route = respx.get(f"{V}/{IG}/insights")
    got = await adapter.get_account_insights(
        account(adapter, insights_scope=False), date(2026, 9, 28), tz="UTC"
    )
    assert got == AccountInsights(followers_count=1204)
    assert got.metrics() == {}
    assert not route.called


@respx.mock
async def test_small_accounts_and_refused_metrics_are_unknown(adapter: InstagramAdapter) -> None:
    """Under 100 followers Meta leaves follows_and_unfollows out; an account metric still "in
    development" (views) may be refused, which is read around."""
    respx.get(f"{V}/me").respond(200, json=fixture("me_followers.json"))
    day = {item["name"]: item for item in fixture("user_insights_day.json")["data"]}

    def answer(request: httpx.Request) -> httpx.Response:
        names = request.url.params["metric"].split(",")
        if names == ["follows_and_unfollows"]:
            return httpx.Response(200, json={"data": []})
        if "views" in names:
            return httpx.Response(400, json=fixture("error_100_incompatible_metric.json"))
        return httpx.Response(200, json={"data": [day[n] for n in names]})

    respx.get(f"{V}/{IG}/insights").mock(side_effect=answer)
    got = await adapter.get_account_insights(account(adapter), date(2026, 9, 28), tz="UTC")
    assert (got.views, got.follows, got.unfollows) == (None, None, None)
    assert (got.reach, got.accounts_engaged, got.profile_links_taps) == (5400, 310, 25)


@respx.mock
async def test_a_day_without_follows_counts_zero(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/me").respond(200, json=fixture("me_followers.json"))

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("breakdown") == "follow_type":
            quiet = {"name": "follows_and_unfollows", "period": "day", "total_value": {"value": 0}}
            return httpx.Response(200, json={"data": [quiet]})
        return httpx.Response(200, json=fixture("user_insights_day.json"))

    respx.get(f"{V}/{IG}/insights").mock(side_effect=answer)
    got = await adapter.get_account_insights(account(adapter), date(2026, 9, 28), tz="UTC")
    assert (got.follows, got.unfollows) == (0, 0)


@respx.mock
async def test_refused_followers_and_insights_leave_the_day_unknown(
    adapter: InstagramAdapter,
) -> None:
    respx.get(f"{V}/me").respond(400, json=fixture("error_10_insights_permission.json"))
    respx.get(f"{V}/{IG}/insights").respond(400, json=fixture("error_10_insights_permission.json"))
    got = await adapter.get_account_insights(account(adapter), date(2026, 9, 28), tz="UTC")
    assert got == AccountInsights()
