"""YouTube channel connect shapes (C-195): the channels a Google account can connect, and the one
picked."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints

from socialhood.schemas.common import RequestModel, ResponseModel

ChannelId = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class YouTubeConnectStart(ResponseModel):
    authorize_url: str


class YouTubeChannelsRequest(RequestModel):
    """The nonce the OAuth callback put in the Connections page's URL (?youtube=…)."""

    nonce: str = Field(min_length=1, max_length=128)


class YouTubeConnectChannels(RequestModel):
    """The channel to connect, picked from the list the same nonce returned. One per workspace."""

    nonce: str = Field(min_length=1, max_length=128)
    channel_ids: list[ChannelId] = Field(min_length=1, max_length=1)


class YouTubeChannel(ResponseModel):
    channel_id: str
    title: str
    handle: str | None = None  # "@name"
    avatar_url: str | None = None
    # Already connected in this workspace (live): picking it reconnects it.
    connected: bool = False


class YouTubeChannelList(ResponseModel):
    items: list[YouTubeChannel]
