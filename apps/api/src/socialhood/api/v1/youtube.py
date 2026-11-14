"""YouTube channels: connect (C-195). Start Google's consent, list the Google account's channels,
connect the one picked. The public callback is in api/v1/oauth.py; the code it parks is exchanged
here, for the member who started the connect only (X-1). 404 wherever YouTube isn't switched on
for the workspace (YOUTUBE_WORKSPACES)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from socialhood.auth.deps import CanManageChannels, Session
from socialhood.billing.plans import current_plan
from socialhood.platforms.deps import PlatformDeps, deps_from
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
