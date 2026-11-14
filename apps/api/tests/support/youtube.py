"""YouTube test support (C-195): every test runs with a FakeYouTube (never Google); request
``fake_youtube`` to change the channels, revoke access or queue a failure. ``with_youtube`` switches
YouTube on for every workspace; the connect helpers run the API's steps."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import SocialAccount
from socialhood.platforms.buckets import YOUTUBE_UPLOADS
from socialhood.platforms.youtube.fake import CHANNEL, REFRESH_PREFIX, FakeYouTube
from socialhood.platforms.youtube.oauth import SCOPE, use_youtube
from socialhood.security.crypto import TokenCipher
from socialhood.settings import Settings
from tests.support.api import TOKEN_KEY, Clerk
from tests.support.instagram import redirect_query, state_from

# C-196: a YouTube channel's choices as the composer sends them.
OPTIONS: dict[str, Any] = {
    "title": "Sourdough in 60 seconds",
    "privacy": "public",
    "made_for_kids": False,
    "synthetic_media": False,
}


@pytest.fixture(autouse=True)
def fake_youtube() -> Iterator[FakeYouTube]:
    fake = FakeYouTube()
    with use_youtube(fake):
        yield fake


def with_youtube(settings: Settings, workspaces: str = "*") -> Settings:
    return settings.model_copy(update={"youtube_workspaces": workspaces})


def _base(wid: str) -> str:
    return f"/v1/w/{wid}/social-accounts/youtube"


async def start_connect(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str
) -> httpx.Response:
    return await client.post(f"{_base(wid)}/connect", headers=clerk.headers(clerk_id))


async def callback(client: httpx.AsyncClient, state: str, code: str) -> str:
    """Google sends the browser back; returns the nonce the callback redirected with."""
    response = await client.get("/v1/oauth/youtube/callback", params={"code": code, "state": state})
    query = redirect_query(response)
    assert "youtube" in query, query
    return query["youtube"]


async def list_channels(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str, nonce: str
) -> httpx.Response:
    return await client.post(
        f"{_base(wid)}/channels", json={"nonce": nonce}, headers=clerk.headers(clerk_id)
    )


async def connect_channels(
    client: httpx.AsyncClient,
    clerk: Clerk,
    clerk_id: str,
    wid: str,
    nonce: str,
    channel_ids: list[str],
) -> httpx.Response:
    return await client.post(
        f"{_base(wid)}/connect-channels",
        json={"nonce": nonce, "channel_ids": channel_ids},
        headers=clerk.headers(clerk_id),
    )


async def nonce_for(client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str) -> str:
    """Start, then follow the fake's authorize URL (it points straight back with a code)."""
    started = await start_connect(client, clerk, clerk_id, wid)
    assert started.status_code == 200, started.text
    url = started.json()["authorize_url"]
    return await callback(client, state_from(url), parse_qs(urlparse(url).query)["code"][0])


async def connect(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str
) -> httpx.Response:
    """The whole connect (start, Google's callback, the list, the pick of the first channel)."""
    nonce = await nonce_for(client, clerk, clerk_id, wid)
    listed = await list_channels(client, clerk, clerk_id, wid, nonce)
    assert listed.status_code == 200, listed.text
    first = listed.json()["items"][0]["channel_id"]
    return await connect_channels(client, clerk, clerk_id, wid, nonce, [first])


# ---------------------------------------------------------------- publishing (C-196)


async def make_channel(
    engine: AsyncEngine, workspace_id: uuid.UUID | str, *, refresh: str = "test"
) -> uuid.UUID:
    """The fake's channel, connected with a refresh token the fake accepts (no connect flow)."""
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            acct = SocialAccount(
                platform="youtube",
                platform_account_id=CHANNEL.id,
                username=CHANNEL.handle,
                display_name=CHANNEL.title,
                status="active",
                scopes=[SCOPE],
                access_token_enc=TokenCipher([TOKEN_KEY]).encrypt(REFRESH_PREFIX + refresh),
                connected_at=datetime.now(UTC),
            )
            session.add(acct)
            await session.commit()
            return acct.id


async def clear_upload_quota(redis: Redis) -> None:
    """YouTube's daily upload count starts empty (it is shared by the whole project)."""
    stale = [key async for key in redis.scan_iter(f"bucket:{YOUTUBE_UPLOADS}:*")]
    if stale:
        await redis.delete(*stale)
