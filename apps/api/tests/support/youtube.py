"""YouTube test support (C-195): every test runs with a FakeYouTube (never Google); request
``fake_youtube`` to change the channels, revoke access or queue a failure. ``with_youtube`` switches
YouTube on for every workspace; the connect helpers run the API's steps."""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from socialhood.platforms.youtube.fake import FakeYouTube
from socialhood.platforms.youtube.oauth import use_youtube
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.instagram import redirect_query, state_from


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
