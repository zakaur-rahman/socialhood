"""YouTube channels: connect (C-195). Start Google's consent, list the Google account's channels,
connect the one picked. The public callback is in api/v1/oauth.py; the code it parks is exchanged
here, for the member who started the connect only (X-1). 404 wherever YouTube isn't switched on
for the workspace (YOUTUBE_WORKSPACES).

``dev_router`` (C-196, sandbox only): the sandbox channel's upload address. A browser PUTs a
direct upload's pieces to it as it would to YouTube's session (``Content-Range``; 308 with
``Range`` to go on, 200 with the video when the last byte arrived; ``bytes */total`` asks what
arrived). Like YouTube's, the address itself is the permission (no sign-in), and it answers 404
unless SANDBOX_PLATFORM_ENABLED. What arrived is counted in this process only; the bytes are
dropped. Left out of the API contract.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from socialhood.auth.deps import CanManageChannels, Session
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.youtube.publishing import SANDBOX_VIDEO
from socialhood.schemas.accounts import SocialAccountList
from socialhood.schemas.youtube import (
    YouTubeChannelList,
    YouTubeChannelsRequest,
    YouTubeConnectChannels,
    YouTubeConnectStart,
)
from socialhood.services import youtube_connect
from socialhood.services.connections import account_out

router = APIRouter(prefix="/v1/w/{wid}", tags=["youtube"])


def _deps(request: Request, ctx: CanManageChannels) -> PlatformDeps:
    settings = request.app.state.settings
    youtube_connect.require_enabled(settings, ctx.workspace_id, ctx.workspace.slug)
    return deps_from(request.app.state.http, settings)


@router.post("/social-accounts/youtube/connect", operation_id="start_youtube_connect")
async def start_youtube_connect(
    request: Request, ctx: CanManageChannels, session: Session
) -> YouTubeConnectStart:
    """Google's authorize URL (youtube.force-ssl, offline, consent). 503 until YouTube connections
    are configured, 402 over youtube_accounts or Free's channels in total."""
    deps = _deps(request, ctx)
    url = await youtube_connect.start(
        session,
        request.app.state.redis,
        deps,
        workspace_id=ctx.workspace_id,
        slug=ctx.workspace.slug,
        user_id=ctx.user.id,
        plan=await current_plan(session),
    )
    return YouTubeConnectStart(authorize_url=url)


@router.post("/social-accounts/youtube/channels", operation_id="list_youtube_channels")
async def list_youtube_channels(
    request: Request, body: YouTubeChannelsRequest, ctx: CanManageChannels, session: Session
) -> YouTubeChannelList:
    """The channels of the Google account that consented, from the nonce the OAuth callback
    redirected with. Only that member, in that workspace, can read it (403 otherwise); 404 when it
    expired (10 minutes), 422 when the account has no channel or the permission was not given,
    502 when Google fails. Asking again returns the same list."""
    deps = _deps(request, ctx)
    return await youtube_connect.list_channels(
        session,
        request.app.state.redis,
        deps,
        nonce=body.nonce,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
    )


@router.post(
    "/social-accounts/youtube/connect-channels",
    status_code=201,
    operation_id="connect_youtube_channels",
)
async def connect_youtube_channels(
    request: Request, body: YouTubeConnectChannels, ctx: CanManageChannels, session: Session
) -> SocialAccountList:
    """Connect the picked channel. 422 channel_ids for a channel that wasn't listed, 409
    account_in_use when it is connected to another workspace, 402 over youtube_accounts (one per
    workspace) or Free's channels in total (nothing is added, the nonce stays valid), 404 when it
    expired."""
    deps = _deps(request, ctx)
    accts = await youtube_connect.connect_channels(
        session,
        request.app.state.redis,
        deps,
        nonce=body.nonce,
        channel_ids=list(body.channel_ids),
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        plan=await current_plan(session),
    )
    return SocialAccountList(items=[account_out(a, deps) for a in accts])


# ---------------------------------------------------------------- the sandbox's upload address

dev_router = APIRouter(tags=["youtube"])
_RANGE = re.compile(r"bytes (?:(\d+)-(\d+)|\*)/(\d+)")
_RECEIVED: dict[str, int] = {}  # upload token -> bytes arrived (this process only)
_KEEP = 1000


def _so_far(received: int) -> Response:
    headers = {"Range": f"bytes=0-{received - 1}"} if received else {}
    return Response(status_code=308, headers=headers)


@dev_router.put("/v1/dev/sandbox/youtube-uploads/{token}", include_in_schema=False)
async def sandbox_youtube_upload(request: Request, token: str) -> Response:
    if not request.app.state.settings.sandbox_platform_enabled or not token.isalnum():
        raise ApiError("not_found")
    match = _RANGE.fullmatch(request.headers.get("content-range", "").strip())
    if match is None:
        raise ApiError("bad_request", "Send Content-Range: bytes first-last/total.")
    first, last, total = match.group(1), match.group(2), int(match.group(3))
    received = _RECEIVED.get(token, 0)
    if first is not None and last is not None:
        await request.body()  # read and dropped
        if int(first) == received and int(last) >= int(first):
            received = min(total, int(last) + 1)
            if len(_RECEIVED) >= _KEEP and token not in _RECEIVED:
                _RECEIVED.pop(next(iter(_RECEIVED)))
            _RECEIVED[token] = received
    if received < total:
        return _so_far(received)
    return JSONResponse(
        {
            "kind": "youtube#video",
            "id": f"{SANDBOX_VIDEO}{token}",
            "status": {"uploadStatus": "uploaded", "privacyStatus": "private"},
        },
        status_code=200,
    )
