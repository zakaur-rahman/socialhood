"""Story insights from Instagram (C-131): replies, and the taps and swipes through a Story from
the ``navigation`` metric with its ``story_navigation_action_type`` breakdown. Responses are shaped
like Meta's documented ones; unverified until a real account publishes a Story."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.instagram import insights, oauth
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
)
V = f"{GRAPH}/{SETTINGS.ig_graph_version}"
STORY = "18100000000000009"


@pytest.fixture
async def adapter() -> AsyncIterator[InstagramAdapter]:
    async with httpx.AsyncClient() as http:
        yield InstagramAdapter(PlatformDeps(http, TokenCipher([new_key()]), SETTINGS))


def account(adapter: InstagramAdapter) -> SocialAccount:
    return SocialAccount(
        platform="instagram",
        platform_account_id="17841400000000001",
        username="maple.bakery",
        access_token_enc=adapter.deps.cipher.encrypt("IGQVJlong"),
        scopes=[*oauth.BASE_SCOPES, oauth.INSIGHTS_SCOPE],
    )


def lifetime(name: str, value: int) -> dict[str, object]:
    return {"name": name, "period": "lifetime", "values": [{"value": value}]}


def navigation(rows: dict[str, int]) -> dict[str, object]:
    return {
        "name": "navigation",
        "period": "lifetime",
        "total_value": {
            "value": sum(rows.values()),
            "breakdowns": [
                {
                    "dimension_keys": ["story_navigation_action_type"],
                    "results": [{"dimension_values": [k], "value": v} for k, v in rows.items()],
                }
            ],
        },
    }


def answer(request: httpx.Request) -> httpx.Response:
    names = request.url.params["metric"].split(",")
    if names == ["navigation"]:
        assert request.url.params["breakdown"] == "story_navigation_action_type"
        rows = {"tap_forward": 700, "tap_back": 80, "swipe_forward": 40, "tap_exit": 60}
        return httpx.Response(200, json={"data": [navigation(rows)]})
    values = {"reach": 900, "views": 1100, "shares": 7, "replies": 5, "total_interactions": 12}
    return httpx.Response(
        200, json={"data": [lifetime(n, values[n]) for n in names if n in values]}
    )


@respx.mock
async def test_a_story_reads_replies_and_its_taps_and_swipes(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/{STORY}/insights").mock(side_effect=answer)
    got = await adapter.get_media_insights(account(adapter), STORY, media_type="story")
    asked = [call.request.url.params["metric"].split(",") for call in route.calls]
    assert asked[0] == list(insights.STORY_METRICS)
    assert "replies" in asked[0]
    assert {"likes", "comments", "saved"}.isdisjoint(asked[0])
    assert asked[1] == ["navigation"]
    assert (got.reach, got.views, got.shares, got.replies) == (900, 1100, 7, 5)
    assert (got.taps_forward, got.taps_back, got.swipes_forward, got.exits) == (700, 80, 40, 60)
    assert (got.likes, got.comments, got.saves) == (None, None, None)


@respx.mock
async def test_a_missing_breakdown_row_means_none_of_that_kind(adapter: InstagramAdapter) -> None:
    def partial(request: httpx.Request) -> httpx.Response:
        if request.url.params["metric"] == "navigation":
            return httpx.Response(200, json={"data": [navigation({"tap_forward": 12})]})
        return httpx.Response(200, json={"data": []})

    respx.get(f"{V}/{STORY}/insights").mock(side_effect=partial)
    got = await adapter.get_media_insights(account(adapter), STORY, media_type="story")
    assert (got.taps_forward, got.taps_back, got.swipes_forward, got.exits) == (12, 0, 0, 0)


@respx.mock
async def test_navigation_that_is_refused_stays_unknown(adapter: InstagramAdapter) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        if request.url.params["metric"] == "navigation":
            error = {"message": "Bad", "type": "OAuthException", "code": 100}
            return httpx.Response(400, json={"error": error})
        return httpx.Response(200, json={"data": [lifetime("reach", 50)]})

    respx.get(f"{V}/{STORY}/insights").mock(side_effect=refuse)
    got = await adapter.get_media_insights(account(adapter), STORY, media_type="story")
    assert got.reach == 50
    assert (got.taps_forward, got.exits) == (None, None)  # a known unknown, never a zero
