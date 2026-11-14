"""Connecting a YouTube channel through Google (C-195), modelled on Facebook Pages (GR-29).

Only where the operator switched YouTube on (YOUTUBE_WORKSPACES, platforms/youtube/switch.py):
elsewhere every step answers 404.

1. ``start``: store a single-use OAuth state and return Google's authorize URL (one scope,
   ``youtube.force-ssl``, offline, consent). 503 until the OAuth client is set up.
2. The public callback parks the code under a one-time nonce bound to the member and workspace
   (X-1: only the member who started the connect may finish it).
3. ``list_channels``: exchange the code (once) for a refresh token, read the Google account's
   channels, and keep both (encrypted) under the same nonce for ten minutes. Asking again returns
   the same list.
4. ``connect_channels``: connect the picked channel. ``platform_account_id`` is the channel id and
   the refresh token is the stored credential (``token_expires_at`` NULL: the adapter mints an
   access token per use). One channel per workspace on every plan (``youtube_accounts``), and it
   counts toward Free's channels in total. The nonce is spent only once the channel is connected.

Disconnecting revokes the grant with Google, best effort (``revoke``).
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, Platform, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.sandbox.adapter import is_sandbox
from socialhood.platforms.youtube import oauth
from socialhood.platforms.youtube.client import Channel
from socialhood.platforms.youtube.switch import youtube_enabled
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories import workspaces
from socialhood.schemas.youtube import YouTubeChannel, YouTubeChannelList
from socialhood.services.connections import (
    HELD_TTL_S,
    IN_USE,
    STATE_TTL_S,
    _at_capacity,
    _check_capacity,
    _held_key,
    _quota_error,
    _upsert,
)
from socialhood.services.sync import start_initial_sync
from socialhood.settings import Settings

log = get_logger(__name__)

CONNECT_EXPIRED = "That connection link expired. Connect YouTube again."
CONNECT_NOT_YOURS = (
    "This YouTube connection was started by someone else, so it wasn't added. To connect your "
    "own channel, use Connect YouTube."
)
CONNECT_FAILED = "Google didn't respond. Try again."
NOT_CONFIGURED = "YouTube connections are not configured."
NO_SCOPE = (
    "Amplychat needs permission to manage your YouTube videos. Connect YouTube again and allow it."
)
NO_CHANNELS = (
    "This Google account has no YouTube channel. Create one on YouTube, then connect again."
)
NOT_LISTED = "That channel wasn't in the list. Connect YouTube again."


def require_enabled(settings: Settings, workspace_id: uuid.UUID, slug: str) -> None:
    """404 where YouTube isn't switched on, as if the routes didn't exist."""
    if not youtube_enabled(settings, workspace_id, slug):
        raise ApiError("not_found")


async def start(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    slug: str,
    user_id: uuid.UUID,
    plan: str,
) -> str:
    """Store a single-use OAuth state (TR-PL-08) and return Google's authorize URL."""
    if not oauth.configured(deps):
        raise ApiError("service_unavailable", NOT_CONFIGURED)
    # A channel already connected can be reconnected, so only a plan with none free refuses here.
    await _check_capacity(session, Platform.YOUTUBE, plan)
    state = secrets.token_urlsafe(32)
    await redis.set(
        f"oauth:{state}",
        json.dumps(
            {
                "user_id": str(user_id),
                "workspace_id": str(workspace_id),
                "slug": slug,
                "platform": "youtube",
            }
        ),
        ex=STATE_TTL_S,
    )
    return oauth.youtube_for(deps).authorize_url(state)


async def _held(
    redis: Redis, nonce: str, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    raw = await redis.get(_held_key(nonce))
    if raw is None:
        raise ApiError("not_found", CONNECT_EXPIRED)
    held: dict[str, Any] = json.loads(raw)
    if held.get("platform") != "youtube":
        raise ApiError("not_found", CONNECT_EXPIRED)
    if held["user_id"] != str(user_id) or held["workspace_id"] != str(workspace_id):
        log.warning(
            "youtube_connect_refused",
            reason="not_the_starter",
            started_in=held["workspace_id"],
            started_by=held["user_id"],
        )
        raise ApiError("forbidden", CONNECT_NOT_YOURS)
    return held


async def _grant_of(
    redis: Redis, deps: PlatformDeps, nonce: str, held: dict[str, Any]
) -> tuple[str, list[Channel]]:
    """The refresh token and the channels: from the code on the first call, then from what was
    kept."""
    if "grant" in held:
        kept = json.loads(deps.cipher.decrypt(held["grant"].encode()))
        return kept["refresh_token"], [Channel(**c) for c in kept["channels"]]
    google = oauth.youtube_for(deps)
    code = deps.cipher.decrypt(held["code"].encode())
    try:
        grant = await google.exchange_code(code)
        if oauth.SCOPE not in grant.scopes:
            raise ApiError("validation_error", NO_SCOPE)
        channels = await google.channels(grant.access_token)
    except PlatformError as error:
        log.warning(
            "youtube_connect_failed", error_code=error.code, platform_code=error.platform_code
        )
        raise ApiError("platform_error", CONNECT_FAILED) from error
    if not channels:
        raise ApiError("validation_error", NO_CHANNELS)
    keep = {
        "refresh_token": grant.refresh_token,
        "channels": [
            {"id": c.id, "title": c.title, "handle": c.handle, "avatar_url": c.avatar_url}
            for c in channels
        ],
    }
    # The code works once: keep what it gave under the same nonce, encrypted, for the pick.
    rest = {k: v for k, v in held.items() if k != "code"}
    rest["grant"] = deps.cipher.encrypt(json.dumps(keep)).decode()
    await redis.set(_held_key(nonce), json.dumps(rest), ex=HELD_TTL_S)
    return grant.refresh_token, channels


async def list_channels(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    nonce: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> YouTubeChannelList:
    held = await _held(redis, nonce, workspace_id=workspace_id, user_id=user_id)
    _, channels = await _grant_of(redis, deps, nonce, held)
    items: list[YouTubeChannel] = []
    for channel in channels:
        existing = await accounts.find(session, Platform.YOUTUBE, channel.id)
        items.append(
            YouTubeChannel(
                channel_id=channel.id,
                title=channel.title,
                handle=f"@{channel.handle}" if channel.handle else None,
                avatar_url=channel.avatar_url,
                connected=existing is not None and existing.status != AccountStatus.DISCONNECTED,
            )
        )
    return YouTubeChannelList(items=items)


async def connect_channels(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    nonce: str,
    channel_ids: list[str],
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
) -> list[SocialAccount]:
    held = await _held(redis, nonce, workspace_id=workspace_id, user_id=user_id)
    if "grant" not in held:
        raise ApiError("conflict", "List your channels first.")
    refresh_token, channels = await _grant_of(redis, deps, nonce, held)
    by_id = {c.id: c for c in channels}
    chosen = [by_id[i] for i in dict.fromkeys(channel_ids) if i in by_id]
    if len(chosen) != len(dict.fromkeys(channel_ids)):
        raise ApiError("validation_error", errors=[FieldError("channel_ids", NOT_LISTED)])

    # A deletion that began after the request was let in: nothing may be added to it (T9.6).
    if not await workspaces.is_active(session, workspace_id, lock=True):
        raise ApiError("not_found")
    now = datetime.now(UTC)
    connected: list[SocialAccount] = []
    for channel in chosen:
        existing = await accounts.find(session, Platform.YOUTUBE, channel.id)
        reconnecting = existing is not None and existing.status != AccountStatus.DISCONNECTED
        limit = None if reconnecting else await _at_capacity(session, Platform.YOUTUBE, plan)
        if limit is not None:
            raise _quota_error(limit, Platform.YOUTUBE)
        values: dict[str, Any] = {
            "username": channel.handle,
            "display_name": channel.title,
            "profile_picture_url": channel.avatar_url,
            "access_token_enc": deps.cipher.encrypt(refresh_token),
            "token_expires_at": None,  # a refresh token: access is minted per use
            "token_refreshed_at": now,
            "scopes": [oauth.SCOPE],
            "status": AccountStatus.ACTIVE,
            "last_error": None,
            "connected_at": now,
            "disconnected_at": None,
            "connected_by_user_id": user_id,
        }
        acct = await _upsert(session, Platform.YOUTUBE, channel.id, values)
        if acct is None:
            log.info("youtube_connect_refused", reason="account_in_use", channel_id=channel.id)
            raise ApiError("account_in_use", f"{channel.title}: {IN_USE}")
        connected.append(acct)
    await session.commit()
    await redis.delete(_held_key(nonce))
    for acct in connected:
        await session.refresh(acct)
        await start_initial_sync(acct)
    log.info("youtube_connected", channels=len(connected))
    return connected


async def revoke(acct: SocialAccount, deps: PlatformDeps, credential: bytes | None) -> None:
    """After a YouTube channel was disconnected (or its deletion began): revoke the grant it held
    (``credential``, its encrypted refresh token) with Google, best effort: the token is already
    deleted here. Any other account is left alone."""
    if acct.platform != Platform.YOUTUBE or is_sandbox(acct) or credential is None:
        return
    try:
        await oauth.youtube_for(deps).revoke(deps.cipher.decrypt(credential))
    except (PlatformError, ValueError):
        log.warning("youtube_revoke_failed", account_id=str(acct.id))
