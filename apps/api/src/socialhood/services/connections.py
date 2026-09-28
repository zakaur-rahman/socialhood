"""Connecting, updating and disconnecting social accounts (F-03, F-05, F-16; FR-CON-01…06)."""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import entitlement
from socialhood.errors import ApiError
from socialhood.models.connections import AccountStatus, AiMode, Platform, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import oauth
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.sandbox.adapter import SANDBOX_PREFIX, is_sandbox
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.accounts import SocialAccountOut, SocialAccountPatch
from socialhood.services.notifications import notify_admins
from socialhood.services.sync import start_initial_sync

log = get_logger(__name__)

STATE_TTL_S = 600
REFRESH_WHEN_LEFT = timedelta(days=20)  # FR-CON-05
REFRESH_MIN_AGE = timedelta(hours=24)  # Instagram refuses to refresh younger tokens
SUBSCRIBE_FAILED = "Couldn't subscribe to messages. Try again."


# ---------------------------------------------------------------- read


def account_out(acct: SocialAccount, deps: PlatformDeps) -> SocialAccountOut:
    try:
        capabilities = sorted(adapter_for(acct, deps).capabilities_for(acct))
    except PlatformError:
        capabilities = []
    live = acct.status != AccountStatus.DISCONNECTED
    return SocialAccountOut.model_validate(
        {
            "id": acct.id,
            "platform": acct.platform,
            "display_name": acct.display_name,
            "username": acct.username,
            "profile_picture_url": acct.profile_picture_url,
            "phone_number": acct.phone_number,
            "status": acct.status,
            "last_error": acct.last_error,
            "ai_mode": acct.ai_mode,
            "ai_analysis_enabled": acct.ai_analysis_enabled,
            "auto_hide_spam": acct.auto_hide_spam,
            "connected_at": acct.connected_at,
            "token_expires_at": acct.token_expires_at,
            "capabilities": capabilities if live else [],
            "sandbox": is_sandbox(acct),
        }
    )


async def get_or_404(session: AsyncSession, account_id: uuid.UUID) -> SocialAccount:
    acct = await accounts.get(session, account_id)
    if acct is None:
        raise ApiError("not_found")
    return acct


# ---------------------------------------------------------------- connect (F-03)


async def _at_capacity(session: AsyncSession, platform: str, plan: str) -> int | None:
    """The plan's limit when the workspace already has that many live accounts, else None."""
    limit = entitlement(plan, "accounts_per_platform")
    if limit is not None and await accounts.count_live(session, platform) >= limit:
        return int(limit)
    return None


def _quota_error(limit: int, platform: str) -> ApiError:
    noun = "account" if limit == 1 else "accounts"
    return ApiError("quota_exceeded", f"Your plan includes {limit} {platform.capitalize()} {noun}.")


async def _check_capacity(session: AsyncSession, platform: str, plan: str) -> None:
    """At the start of a connect: refuse early unless an account could be reconnected. The
    callback decides exactly, once it knows which account came back."""
    limit = await _at_capacity(session, platform, plan)
    if limit is not None and not await accounts.count_reconnectable(session, platform):
        raise _quota_error(limit, platform)


async def start_instagram_connect(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    slug: str,
    user_id: uuid.UUID,
    plan: str,
) -> str:
    """Store a single-use OAuth state (TR-PL-08) and return Instagram's authorize URL."""
    if not deps.settings.ig_app_id or not deps.settings.ig_redirect_uri:
        raise ApiError("service_unavailable", "Instagram connections are not configured.")
    await _check_capacity(session, Platform.INSTAGRAM, plan)
    state = secrets.token_urlsafe(32)
    await redis.set(
        f"oauth:{state}",
        json.dumps(
            {
                "user_id": str(user_id),
                "workspace_id": str(workspace_id),
                "slug": slug,
                "platform": "instagram",
            }
        ),
        ex=STATE_TTL_S,
    )
    return oauth.authorize_url(deps.settings, state)


async def pop_state(redis: Redis, state: str | None) -> dict[str, str] | None:
    """Read and delete the state in one step, so a state works exactly once."""
    if not state:
        return None
    raw = await redis.getdel(f"oauth:{state}")
    return json.loads(raw) if raw else None


@dataclass(frozen=True)
class ConnectOutcome:
    error: str | None = None
    account_id: uuid.UUID | None = None
    limit: int | None = None  # with quota_exceeded, for the "Your plan includes …" copy


async def complete_instagram_connect(
    session: AsyncSession,
    deps: PlatformDeps,
    *,
    code: str,
    user_id: uuid.UUID,
    plan: str,
) -> ConnectOutcome:
    """Exchange the code, check the account, store it, subscribe it. Runs in the workspace scope."""
    http = PlatformHttp(deps.http, "instagram")
    try:
        short = await oauth.exchange_code(http, deps.settings, code)
        long = await oauth.long_lived(http, deps.settings, short.access_token)
        profile = await oauth.me(http, deps.settings, long.access_token)
    except PlatformError as error:
        log.warning(
            "instagram_connect_failed", error_code=error.code, platform_code=error.platform_code
        )
        return ConnectOutcome(error="connect_failed")
    if not profile.is_professional:
        return ConnectOutcome(error="ig_not_professional")
    existing = await accounts.find(session, Platform.INSTAGRAM, profile.user_id)
    reconnecting = existing is not None and existing.status != AccountStatus.DISCONNECTED
    limit = None if reconnecting else await _at_capacity(session, Platform.INSTAGRAM, plan)
    if limit is not None:
        return ConnectOutcome(error="quota_exceeded", limit=limit)

    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "app_scoped_id": profile.app_scoped_id,
        "username": profile.username,
        "display_name": profile.name or profile.username,
        "profile_picture_url": profile.profile_picture_url,
        "access_token_enc": deps.cipher.encrypt(long.access_token),
        "token_expires_at": long.expires_at,
        "token_refreshed_at": now,
        "scopes": list(short.permissions) or list(oauth.scopes(deps.settings)),
        "status": AccountStatus.ACTIVE,
        "last_error": None,
        "connected_at": now,
        "disconnected_at": None,
        "connected_by_user_id": user_id,
    }
    acct = await _upsert(session, Platform.INSTAGRAM, profile.user_id, values)
    if acct is None:
        return ConnectOutcome(error="account_in_use")
    await subscribe(session, acct, deps)
    await session.commit()
    await start_initial_sync(acct)  # FR-CON-01: recent posts and conversations
    return ConnectOutcome(account_id=acct.id)


async def _upsert(
    session: AsyncSession, platform: str, platform_account_id: str, values: dict[str, Any]
) -> SocialAccount | None:
    """Reconnect updates the existing row; otherwise insert. None when the account is live in
    another workspace (the partial unique index refuses it)."""
    try:
        async with session.begin_nested():
            existing = await accounts.find(session, platform, platform_account_id)
            if existing is not None:
                await accounts.update(session, existing.id, **values)
                await session.flush()
                await session.refresh(existing)
                return existing
            acct = SocialAccount(
                platform=platform, platform_account_id=platform_account_id, **values
            )
            session.add(acct)
            await session.flush()
            return acct
    except IntegrityError as error:
        if "uq_social_accounts_live_platform_account" in str(error.orig):
            return None
        raise


async def subscribe(session: AsyncSession, acct: SocialAccount, deps: PlatformDeps) -> bool:
    """Subscribe the account to webhooks; on failure the account shows the error with Retry."""
    try:
        await adapter_for(acct, deps).subscribe_webhooks(acct)
    except PlatformError as error:
        log.warning("webhook_subscribe_failed", account_id=str(acct.id), error_code=error.code)
        status = (
            AccountStatus.NEEDS_RECONNECT
            if error.code == "account_needs_reconnect"
            else AccountStatus.ERROR
        )
        await accounts.update(session, acct.id, status=status, last_error=SUBSCRIBE_FAILED)
        return False
    await accounts.update(
        session,
        acct.id,
        webhooks_subscribed_at=datetime.now(UTC),
        **(
            {"status": AccountStatus.ACTIVE, "last_error": None}
            if acct.status == AccountStatus.ERROR
            else {}
        ),
    )
    return True


async def connect_sandbox(
    session: AsyncSession, deps: PlatformDeps, *, user_id: uuid.UUID, plan: str
) -> SocialAccount:
    """A sandbox Instagram account for local development (TR-PL-07)."""
    if not deps.settings.sandbox_platform_enabled:
        raise ApiError("not_found")
    limit = await _at_capacity(session, Platform.INSTAGRAM, plan)
    if limit is not None:
        raise _quota_error(limit, Platform.INSTAGRAM)
    suffix = secrets.token_hex(4)
    now = datetime.now(UTC)
    acct = SocialAccount(
        platform=Platform.INSTAGRAM,
        platform_account_id=f"{SANDBOX_PREFIX}{suffix}",
        username=f"sandbox.shop.{suffix[:4]}",
        display_name="Sandbox shop",
        access_token_enc=deps.cipher.encrypt(f"sandbox-{secrets.token_hex(8)}"),
        token_expires_at=now + timedelta(days=60),
        token_refreshed_at=now,
        scopes=[*oauth.BASE_SCOPES, oauth.INSIGHTS_SCOPE],
        status=AccountStatus.ACTIVE,
        connected_at=now,
        webhooks_subscribed_at=now,
        connected_by_user_id=user_id,
    )
    session.add(acct)
    await session.commit()
    await session.refresh(acct)
    await start_initial_sync(acct)
    return acct


# ---------------------------------------------------------------- update and disconnect


async def update_account(
    session: AsyncSession, acct: SocialAccount, patch: SocialAccountPatch, *, plan: str
) -> SocialAccount:
    values = patch.model_dump(exclude_unset=True, exclude_none=True)
    if "ai_mode" in values and values["ai_mode"] not in entitlement(plan, "ai_modes"):
        raise ApiError("entitlement_required", "Auto mode is part of Pro.")
    if acct.status == AccountStatus.DISCONNECTED:
        raise ApiError("conflict", "Reconnect this account before changing its settings.")
    if values:
        await accounts.update(session, acct.id, **values)
        await session.commit()
        await session.refresh(acct)
    return acct


async def disconnect(
    session: AsyncSession, redis: Redis, acct: SocialAccount, *, delete_data: bool
) -> None:
    """Delete the token at once and stop processing the account's webhooks (FR-CON-06).

    Deleting the account's conversations and comments arrives with those tables (P3, P6); until
    then there is nothing else stored for it.
    """
    await accounts.update(
        session,
        acct.id,
        access_token_enc=None,
        status=AccountStatus.DISCONNECTED,
        disconnected_at=datetime.now(UTC),
        last_error=None,
    )
    await session.commit()
    await _clear_caches(redis, acct.id)
    log.info("account_disconnected", account_id=str(acct.id), delete_data=delete_data)


async def _clear_caches(redis: Redis, account_id: uuid.UUID) -> None:
    try:
        keys = [key async for key in redis.scan_iter(match=f"profile:{account_id}:*", count=500)]
        if keys:
            await redis.delete(*keys)
    except Exception:  # a cache is never worth failing a disconnect over
        log.warning("cache_clear_failed", account_id=str(account_id))


# ---------------------------------------------------------------- token refresh (FR-CON-05, F-05)


def refresh_due(acct: SocialAccount, now: datetime) -> bool:
    if acct.status != AccountStatus.ACTIVE or acct.token_expires_at is None:
        return False
    old_enough = acct.token_refreshed_at is None or now - acct.token_refreshed_at >= REFRESH_MIN_AGE
    return old_enough and acct.token_expires_at - now < REFRESH_WHEN_LEFT


async def refresh_account(session: AsyncSession, acct: SocialAccount, deps: PlatformDeps) -> bool:
    """Refresh one account's token; a failure asks the owners to reconnect (once)."""
    try:
        grant = await adapter_for(acct, deps).refresh_token(acct)
    except PlatformError as error:
        if error.retryable:
            raise
        await mark_needs_reconnect(session, acct, "Instagram stopped accepting this connection.")
        await session.commit()
        return False
    await accounts.update(
        session,
        acct.id,
        access_token_enc=deps.cipher.encrypt(grant.access_token),
        token_expires_at=grant.expires_at,
        token_refreshed_at=datetime.now(UTC),
    )
    await session.commit()
    return True


async def mark_needs_reconnect(session: AsyncSession, acct: SocialAccount, reason: str) -> None:
    """F-05: status, plain-language error, and one notification per broken connection."""
    await accounts.update(session, acct.id, status=AccountStatus.NEEDS_RECONNECT, last_error=reason)
    handle = f"@{acct.username}" if acct.username else "An account"
    since = (acct.token_refreshed_at or acct.connected_at or datetime.now(UTC)).isoformat()
    await notify_admins(
        session,
        type="account_needs_reconnect",
        severity="critical",
        title=f"Reconnect {handle}",
        body=f"{handle} needs reconnecting to keep receiving messages.",
        link="/settings/connections",
        dedupe_key=f"reconnect:{acct.id}:{since}",
    )


async def mark_disconnected_by_platform(session: AsyncSession, acct: SocialAccount) -> None:
    """The user removed our app on the platform (Meta deauthorize): drop the token and tell the
    owners."""
    if acct.status == AccountStatus.DISCONNECTED:
        return
    await accounts.update(
        session,
        acct.id,
        access_token_enc=None,
        status=AccountStatus.DISCONNECTED,
        disconnected_at=datetime.now(UTC),
        last_error="Social Hood was removed from this account in Instagram.",
    )
    handle = f"@{acct.username}" if acct.username else "An account"
    await notify_admins(
        session,
        type="account_disconnected",
        severity="warning",
        title=f"{handle} was disconnected",
        body=(
            f"Social Hood was removed from {handle} in Instagram. "
            "Connect it again to keep receiving messages."
        ),
        link="/settings/connections",
        dedupe_key=f"deauthorized:{acct.id}:{(acct.connected_at or datetime.now(UTC)).isoformat()}",
    )


def default_ai_mode(plan: str) -> str:
    return AiMode.SUGGEST if AiMode.SUGGEST in entitlement(plan, "ai_modes") else AiMode.OFF
