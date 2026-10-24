"""Facebook Page post insights (C-131) without a database: the permission gate, the calls and
bodies, the known unknowns, and a Page Story with none. Meta's shapes are unverified until a real
Page returns them (docs/verification.md)."""

from __future__ import annotations

import httpx
import pytest

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import MediaInsights
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.facebook import insights, oauth
from socialhood.settings import AppEnv, Settings
from tests.unit.test_facebook_publishing import PAGE, Recorder, account, adapter

POST = f"{PAGE}_555"


def granted() -> SocialAccount:
    return account([*oauth.SCOPES, oauth.INSIGHTS_SCOPE])


def metric(name: str, value: int) -> dict[str, object]:
    return {"name": name, "period": "lifetime", "values": [{"value": value}]}


def test_post_insights_need_the_read_insights_permission() -> None:
    page = adapter(Recorder())
    assert Capability.POST_INSIGHTS in page.capabilities_for(granted())
    assert Capability.POST_INSIGHTS not in page.capabilities_for(account())
    assert Capability.ACCOUNT_INSIGHTS not in page.capabilities_for(granted())


def test_the_scope_is_asked_for_only_when_switched_on() -> None:
    off = Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        database_url="postgresql+asyncpg://x:x@127.0.0.1/x",
        database_url_direct="postgresql://x:x@127.0.0.1/x",
        redis_url="redis://127.0.0.1:6379/14",
    )
    on = off.model_copy(update={"fb_request_insights_scope": True})
    assert oauth.INSIGHTS_SCOPE not in oauth.scopes(off)
    assert oauth.scopes(on) == (*oauth.SCOPES, oauth.INSIGHTS_SCOPE)
    assert oauth.INSIGHTS_SCOPE == "read_insights"


async def test_a_posts_views_reach_clicks_and_shares_are_read() -> None:
    recorder = Recorder(
        {
            "data": [
                metric("post_media_view", 4100),
                metric("post_total_media_view_unique", 2900),
                metric("post_clicks", 61),
            ]
        },
        {"id": POST, "shares": {"count": 14}},
    )
    got = await adapter(recorder).get_media_insights(granted(), POST, media_type="image")
    assert got == MediaInsights(views=4100, reach=2900, clicks=61, shares=14)
    first = recorder.requests[0]
    assert first.url.path.endswith(f"/{POST}/insights")
    assert set(first.url.params["metric"].split(",")) == set(insights.POST_METRIC_KEYS)
    assert first.url.params["period"] == "lifetime"
    assert first.headers["authorization"] == "Bearer page-token"
    assert recorder.requests[1].url.params["fields"] == "shares"


async def test_a_post_nobody_shared_has_zero_shares_and_a_refusal_leaves_it_unknown() -> None:
    quiet = Recorder({"data": []}, {"id": POST})
    got = await adapter(quiet).get_media_insights(granted(), POST, media_type="image")
    assert got.shares == 0
    assert (got.views, got.reach, got.clicks) == (None, None, None)  # never zeros

    refused = Recorder(
        {
            "error": {
                "code": 100,
                "message": "Unsupported get request",
                "type": "GraphMethodException",
            }
        },
        status=400,
    )
    got = await adapter(refused).get_media_insights(granted(), POST, media_type="image")
    assert got == MediaInsights()


async def test_an_incompatible_metric_is_read_alone_and_left_unknown() -> None:
    class Router(Recorder):
        def handler(self, request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            names = request.url.params.get("metric", "").split(",")
            if len(names) > 1 or names == ["post_clicks"]:
                return httpx.Response(400, json={"error": {"code": 100, "message": "Incompatible"}})
            if names == ["post_media_view"]:
                return httpx.Response(200, json={"data": [metric("post_media_view", 77)]})
            if names == ["post_total_media_view_unique"]:
                return httpx.Response(200, json={"data": []})
            return httpx.Response(200, json={"id": POST, "shares": {"count": 1}})

    got = await adapter(Router()).get_media_insights(granted(), POST, media_type="video")
    assert (got.views, got.clicks, got.shares) == (77, None, 1)


async def test_a_page_story_has_no_insights_and_a_page_without_the_permission_says_so() -> None:
    recorder = Recorder()
    got = await adapter(recorder).get_media_insights(granted(), POST, media_type="story")
    assert got == MediaInsights()
    assert recorder.requests == []
    with pytest.raises(PlatformError) as raised:
        await adapter(Recorder()).get_media_insights(account(), POST, media_type="image")
    assert raised.value.code == "capability_unavailable"


async def test_a_dead_token_still_raises() -> None:
    expired = Recorder(
        {"error": {"code": 190, "message": "Session expired", "type": "OAuthException"}},
        status=401,
    )
    with pytest.raises(PlatformError) as raised:
        await adapter(expired).get_media_insights(granted(), POST, media_type="image")
    assert raised.value.code == "account_needs_reconnect"
