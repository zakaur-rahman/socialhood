"""C-195: connecting a YouTube channel - the feature switch, Google's consent with one scope, the
parked code (X-1), the channel list, the connect, one channel per workspace on every plan, Free's
channels in total, revoking on disconnect, sandbox channels and the workspace's ``features``."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.deps import deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.client import Channel
from socialhood.platforms.youtube.fake import CHANNEL, FakeYouTube
from socialhood.platforms.youtube.oauth import SCOPE, HttpYouTubeOAuth
from socialhood.security.crypto import TokenCipher
from socialhood.services.youtube_connect import CONNECT_NOT_YOURS, NO_SCOPE
from socialhood.settings import Settings
from tests.support.api import TOKEN_KEY, WEB, Clerk, sign_in
from tests.support.automation_api import set_plan
from tests.support.inbox import make_account
from tests.support.instagram import redirect_query, state_from
from tests.support.youtube import (
    connect,
    connect_channels,
    list_channels,
    nonce_for,
    start_connect,
    with_youtube,
)

OTHER = Channel(id="UCotherChannel000000000002", title="Maple Cafe", handle=None, avatar_url=None)


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_youtube(api_settings)


async def owner(
    client: httpx.AsyncClient, clerk: Clerk, email: str = "o@example.com"
) -> tuple[str, dict[str, Any]]:
    clerk_id, me = await sign_in(client, clerk, email=email)
    return clerk_id, me["workspaces"][0]


async def rows(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM social_accounts WHERE platform = 'youtube' ORDER BY created_at")
        )
        return [dict(r._mapping) for r in result]


# ---------------------------------------------------------------- the switch and features


async def test_youtube_is_404_where_it_is_not_switched_on(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, ws = await owner(client, clerk)
    app.state.settings = with_youtube(app.state.settings, "")
    headers = clerk.headers(clerk_id)
    base = f"/v1/w/{ws['id']}/social-accounts/youtube"
    assert (await client.post(f"{base}/connect", headers=headers)).status_code == 404
    listed = await client.post(f"{base}/channels", json={"nonce": "n"}, headers=headers)
    assert listed.status_code == 404
    picked = await client.post(
        f"{base}/connect-channels", json={"nonce": "n", "channel_ids": ["UC1"]}, headers=headers
    )
    assert picked.status_code == 404
    workspace = (await client.get(f"/v1/w/{ws['id']}", headers=headers)).json()
    assert workspace["features"] == []
    me = (await client.get("/v1/me", headers=headers)).json()
    assert me["workspaces"][0]["features"] == []


async def test_features_list_youtube_by_slug_id_or_star(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, ws = await owner(client, clerk)
    headers = clerk.headers(clerk_id)
    for switch in ("*", ws["slug"], f"other, {ws['id']}"):
        app.state.settings = with_youtube(app.state.settings, switch)
        assert (await client.get(f"/v1/w/{ws['id']}", headers=headers)).json()["features"] == [
            "youtube"
        ]
        listed = (await client.get("/v1/workspaces", headers=headers)).json()["items"]
        assert listed[0]["features"] == ["youtube"]
    app.state.settings = with_youtube(app.state.settings, "someone-else")
    assert (await client.get(f"/v1/w/{ws['id']}", headers=headers)).json()["features"] == []


# ---------------------------------------------------------------- the connect


async def test_start_asks_google_for_force_ssl_offline_with_consent(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, redis: Redis
) -> None:
    clerk_id, ws = await owner(client, clerk)
    started = await start_connect(client, clerk, clerk_id, ws["id"])
    assert started.status_code == 200, started.text
    url = started.json()["authorize_url"]
    assert 0 < await redis.ttl(f"oauth:{state_from(url)}") <= 600

    # The real client's URL (the fake's points straight back).
    real = HttpYouTubeOAuth(deps_from(app.state.http, app.state.settings)).authorize_url("s")
    query = {k: v[0] for k, v in parse_qs(urlparse(real).query).items()}
    assert (query["scope"], query["access_type"], query["prompt"]) == (SCOPE, "offline", "consent")
    assert query["include_granted_scopes"] == "false"


async def test_the_callback_parks_the_code_and_a_state_works_once(
    client: httpx.AsyncClient, clerk: Clerk, fake_youtube: FakeYouTube, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    started = await start_connect(client, clerk, clerk_id, ws["id"])
    state = state_from(started.json()["authorize_url"])
    first = await client.get("/v1/oauth/youtube/callback", params={"code": "c", "state": state})
    query = redirect_query(first)
    assert query["_path"] == f"/w/{ws['slug']}/settings/connections"
    assert set(query) == {"youtube", "_path"}
    assert first.headers["location"].startswith(WEB)
    assert fake_youtube.calls == []  # X-1: the callback exchanges nothing
    assert await rows(engine) == []
    again = await client.get("/v1/oauth/youtube/callback", params={"code": "c", "state": state})
    assert redirect_query(again) == {"error": "state_invalid", "_path": "/app"}


async def test_a_declined_consent_goes_back_with_the_reason(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, ws = await owner(client, clerk)
    started = await start_connect(client, clerk, clerk_id, ws["id"])
    state = state_from(started.json()["authorize_url"])
    response = await client.get(
        "/v1/oauth/youtube/callback", params={"error": "access_denied", "state": state}
    )
    query = redirect_query(response)
    assert (query["error"], query["platform"]) == ("access_denied", "youtube")


async def test_the_channel_list_exchanges_the_code_once(
    client: httpx.AsyncClient, clerk: Clerk, fake_youtube: FakeYouTube, engine: AsyncEngine
) -> None:
    fake_youtube.channel_list = [CHANNEL, OTHER]
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    listed = await list_channels(client, clerk, clerk_id, ws["id"], nonce)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == [
        {
            "channel_id": CHANNEL.id,
            "title": "Maple Bakery",
            "handle": "@maplebakery",
            "avatar_url": "https://yt.test/maple.jpg",
            "connected": False,
        },
        {
            "channel_id": OTHER.id,
            "title": "Maple Cafe",
            "handle": None,
            "avatar_url": None,
            "connected": False,
        },
    ]
    again = await list_channels(client, clerk, clerk_id, ws["id"], nonce)
    assert again.json() == listed.json()
    assert [name for name, _ in fake_youtube.calls].count("exchange_code") == 1
    assert await rows(engine) == []


async def test_connecting_a_channel_stores_the_refresh_token(
    client: httpx.AsyncClient,
    clerk: Clerk,
    fake_youtube: FakeYouTube,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    done = await connect(client, clerk, clerk_id, ws["id"])
    assert done.status_code == 201, done.text
    [account] = done.json()["items"]
    assert (account["platform"], account["username"], account["display_name"]) == (
        "youtube",
        "maplebakery",
        "Maple Bakery",
    )
    assert sorted(account["capabilities"]) == ["post_insights", "publish"]
    assert account["token_expires_at"] is None

    [row] = await rows(engine)
    assert (row["platform_account_id"], row["status"], row["scopes"]) == (
        CHANNEL.id,
        "active",
        [SCOPE],
    )
    assert row["profile_picture_url"] == "https://yt.test/maple.jpg"
    refresh = TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"])
    assert refresh.startswith("fake-yt-refresh:")
    assert refresh.encode() not in bytes(row["access_token_enc"])

    listed = (
        await client.get(f"/v1/w/{ws['id']}/social-accounts", headers=clerk.headers(clerk_id))
    ).json()["items"]
    assert [a["platform"] for a in listed] == ["youtube"]
    overview = await client.get(f"/v1/w/{ws['id']}/overview", headers=clerk.headers(clerk_id))
    assert overview.status_code == 200, overview.text
    assert overview.json()["platforms_connected"] == ["youtube"]


async def test_a_victim_cannot_finish_an_attackers_connect(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    attacker, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, attacker, ws["id"])
    victim, victim_ws = await owner(client, clerk, "victim@example.com")
    refused = await list_channels(client, clerk, victim, victim_ws["id"], nonce)
    assert (refused.status_code, refused.json()["detail"]) == (403, CONNECT_NOT_YOURS)


async def test_a_grant_without_the_scope_is_refused(
    client: httpx.AsyncClient, clerk: Clerk, fake_youtube: FakeYouTube
) -> None:
    fake_youtube.scopes = ()
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    refused = await list_channels(client, clerk, clerk_id, ws["id"], nonce)
    assert (refused.status_code, refused.json()["detail"]) == (422, NO_SCOPE)


async def test_an_invalid_grant_on_the_exchange_is_a_platform_error(
    client: httpx.AsyncClient, clerk: Clerk, fake_youtube: FakeYouTube
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    fake_youtube.fail_next(PlatformError("account_needs_reconnect", platform_code="invalid_grant"))
    failed = await list_channels(client, clerk, clerk_id, ws["id"], nonce)
    assert (failed.status_code, failed.json()["code"]) == (502, "platform_error")


async def test_a_channel_that_was_not_listed_is_refused(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    await list_channels(client, clerk, clerk_id, ws["id"], nonce)
    refused = await connect_channels(client, clerk, clerk_id, ws["id"], nonce, ["UCnope"])
    assert refused.status_code == 422, refused.text
    two = await connect_channels(client, clerk, clerk_id, ws["id"], nonce, [CHANNEL.id, OTHER.id])
    assert two.status_code == 422  # one channel at a time


# ---------------------------------------------------------------- plans


async def test_one_channel_per_workspace_even_on_business(
    client: httpx.AsyncClient,
    clerk: Clerk,
    fake_youtube: FakeYouTube,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await set_plan(engine, ws["id"], "max")
    fake_youtube.channel_list = [CHANNEL, OTHER]
    first = await nonce_for(client, clerk, clerk_id, ws["id"])
    second = await nonce_for(client, clerk, clerk_id, ws["id"])
    for nonce in (first, second):
        assert (await list_channels(client, clerk, clerk_id, ws["id"], nonce)).status_code == 200
    connected = await connect_channels(client, clerk, clerk_id, ws["id"], first, [CHANNEL.id])
    assert connected.status_code == 201, connected.text

    over = await connect_channels(client, clerk, clerk_id, ws["id"], second, [OTHER.id])
    assert over.status_code == 402, over.text
    body = over.json()
    assert (body["code"], body["entitlement"], body["limit"]) == (
        "quota_exceeded",
        "youtube_accounts",
        1,
    )
    assert body["detail"] == "Your plan includes 1 YouTube account."
    started = await start_connect(client, clerk, clerk_id, ws["id"])
    assert (started.status_code, started.json()["entitlement"]) == (402, "youtube_accounts")
    # Reconnecting the connected channel keeps its slot.
    again = await connect_channels(client, clerk, clerk_id, ws["id"], second, [CHANNEL.id])
    assert again.status_code == 201, again.text
    assert len(await rows(engine)) == 1

    billing = (
        await client.get(f"/v1/w/{ws['id']}/billing", headers=clerk.headers(clerk_id))
    ).json()
    meters = {m["metric"]: m for m in billing["usage"]}
    assert (meters["youtube_accounts"]["used"], meters["youtube_accounts"]["limit"]) == (1, 1)


async def test_youtube_counts_toward_frees_channels_in_total(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await make_account(engine, ws["id"], platform="instagram", platform_account_id="ig-1")
    await make_account(engine, ws["id"], platform="facebook", platform_account_id="fb-1")
    refused = await start_connect(client, clerk, clerk_id, ws["id"])
    assert refused.status_code == 402, refused.text
    assert (refused.json()["code"], refused.json()["entitlement"], refused.json()["limit"]) == (
        "quota_exceeded",
        "channels_total",
        2,
    )
    await set_plan(engine, ws["id"], "pro")  # Creator has no total
    assert (await start_connect(client, clerk, clerk_id, ws["id"])).status_code == 200


# ---------------------------------------------------------------- disconnect and sandbox


async def test_disconnecting_revokes_the_grant_with_google(
    client: httpx.AsyncClient,
    clerk: Clerk,
    fake_youtube: FakeYouTube,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    [account] = (await connect(client, clerk, clerk_id, ws["id"])).json()["items"]
    [row] = await rows(engine)
    refresh = TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"])

    gone = await client.delete(
        f"/v1/w/{ws['id']}/social-accounts/{account['id']}", headers=clerk.headers(clerk_id)
    )
    assert gone.status_code == 204, gone.text
    assert ("revoke", {"token": refresh}) in fake_youtube.calls
    assert refresh in fake_youtube.revoked
    [row] = await rows(engine)
    assert (row["status"], row["access_token_enc"]) == ("disconnected", None)


async def test_a_failed_revoke_still_disconnects(
    client: httpx.AsyncClient,
    clerk: Clerk,
    fake_youtube: FakeYouTube,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    [account] = (await connect(client, clerk, clerk_id, ws["id"])).json()["items"]
    fake_youtube.fail_next(PlatformError("platform_unavailable"))
    gone = await client.delete(
        f"/v1/w/{ws['id']}/social-accounts/{account['id']}", headers=clerk.headers(clerk_id)
    )
    assert gone.status_code == 204, gone.text
    [row] = await rows(engine)
    assert row["status"] == "disconnected"


async def test_a_sandbox_channel_can_be_made(
    client: httpx.AsyncClient, clerk: Clerk, queue: None
) -> None:
    clerk_id, ws = await owner(client, clerk)
    made = await client.post(
        f"/v1/w/{ws['id']}/dev/sandbox/accounts",
        json={"platform": "youtube"},
        headers=clerk.headers(clerk_id),
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert (body["platform"], body["sandbox"], body["token_expires_at"]) == ("youtube", True, None)
    assert sorted(body["capabilities"]) == ["post_insights", "publish"]
