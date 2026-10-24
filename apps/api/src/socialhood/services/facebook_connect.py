"""Connecting Facebook Pages through Facebook Login (GR-29; F-03).

1. ``start``: store a single-use OAuth state and return Facebook's authorize URL. Refused (503)
   unless META_APP_ID, META_APP_SECRET and FB_REDIRECT_URI are set.
2. The public callback parks the code under a one-time nonce bound to the member and workspace
   (X-1: only the member who started the connect may finish it), exactly as for Instagram.
3. ``list_pages``: exchange the code for a long-lived user token, read the Pages the person
   manages, and keep their Page tokens (encrypted) under the same nonce for ten minutes. Returns
   the Pages for the picker. Calling it again returns the same list.
4. ``connect_pages``: connect the Pages the person picked. Each Page is an account:
   ``platform_account_id`` is the Page id, ``app_scoped_id`` the person's Facebook id (so Meta's
   deauthorize and data-deletion callbacks find every Page they connected), and the Page token
   is stored encrypted. The plan's ``accounts_per_platform`` is checked for all the picked Pages
   before any is added. Webhooks are subscribed per Page; the first sync starts. The nonce is
   spent only when the Pages are connected, so a refusal (the plan, a Page in use) lets the person
   choose again.

Page tokens come from a long-lived user token and do not expire (unverified, docs/verification.md).
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, Platform, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.facebook import oauth
from socialhood.platforms.http import PlatformHttp
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories import workspaces
from socialhood.schemas.facebook import FacebookPageList, FacebookPageOption
from socialhood.services.connections import (
    HELD_TTL_S,
    IN_USE,
    STATE_TTL_S,
    _check_capacity,
    _held_key,
    _quota_error,
    _upsert,
    subscribe,
)
from socialhood.services.sync import start_initial_sync

log = get_logger(__name__)

CONNECT_EXPIRED = "That connection link expired. Connect Facebook again."
CONNECT_NOT_YOURS = (
    "This Facebook connection was started by someone else, so it wasn't added. To connect your "
    "own Pages, use Connect Facebook."
)
CONNECT_FAILED = "Facebook didn't respond. Try again."
NOT_CONFIGURED = "Facebook connections are not configured."
NO_MESSAGING = (
    "You can't answer messages for this Page. Ask a Page admin to give you access to messages, "
    "then connect again."
)
NO_PAGES = "Facebook didn't list any Pages you manage. Check your access, then connect again."
NOT_LISTED = "That Page wasn't in the list. Connect Facebook again."


def configured(deps: PlatformDeps) -> bool:
    s = deps.settings
    return bool(s.meta_app_id and s.meta_app_secret and s.fb_redirect_uri)


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
    """Store a single-use OAuth state (TR-PL-08) and return Facebook's authorize URL."""
    if not configured(deps):
        raise ApiError("service_unavailable", NOT_CONFIGURED)
    # A Page already connected can be reconnected, so only a plan with none free refuses here.
    await _check_capacity(session, Platform.FACEBOOK, plan)
    state = secrets.token_urlsafe(32)
    await redis.set(
        f"oauth:{state}",
        json.dumps(
            {
                "user_id": str(user_id),
                "workspace_id": str(workspace_id),
                "slug": slug,
                "platform": "facebook",
            }
        ),
        ex=STATE_TTL_S,
    )
    return oauth.authorize_url(deps.settings, state)


async def _held(
    redis: Redis, nonce: str, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    raw = await redis.get(_held_key(nonce))
    if raw is None:
        raise ApiError("not_found", CONNECT_EXPIRED)
    held: dict[str, Any] = json.loads(raw)
    if held.get("platform") != "facebook":
        raise ApiError("not_found", CONNECT_EXPIRED)
    if held["user_id"] != str(user_id) or held["workspace_id"] != str(workspace_id):
        log.warning(
            "facebook_connect_refused",
            reason="not_the_starter",
            started_in=held["workspace_id"],
            started_by=held["user_id"],
        )
        raise ApiError("forbidden", CONNECT_NOT_YOURS)
    return held


async def _pages_of(
    redis: Redis, deps: PlatformDeps, nonce: str, held: dict[str, Any]
) -> tuple[oauth.FacebookUser, list[oauth.FacebookPage]]:
    """The person and their Pages: from the code on the first call, then from what was kept."""
    if "pages" in held:
        stored = json.loads(deps.cipher.decrypt(held["pages"].encode()))
        user = oauth.FacebookUser(id=stored["user"]["id"], name=stored["user"].get("name"))
        pages = [
            oauth.FacebookPage(
                id=p["id"],
                name=p.get("name"),
                username=p.get("username"),
                picture_url=p.get("picture_url"),
                access_token=p["access_token"],
                tasks=tuple(p.get("tasks") or ()),
            )
            for p in stored["pages"]
        ]
        return user, pages
    http = PlatformHttp(deps.http, "facebook")
    code = deps.cipher.decrypt(held["code"].encode())
    try:
        short = await oauth.exchange_code(http, deps.settings, code)
        long = await oauth.long_lived(http, deps.settings, short)
        user = await oauth.me(http, deps.settings, long.access_token)
        pages = await oauth.pages(http, deps.settings, long.access_token)
    except PlatformError as error:
        log.warning(
            "facebook_connect_failed", error_code=error.code, platform_code=error.platform_code
        )
        raise ApiError("platform_error", CONNECT_FAILED) from error
    if not pages:
        raise ApiError("validation_error", NO_PAGES)
    keep = {
        "user": {"id": user.id, "name": user.name},
        "pages": [
            {
                "id": p.id,
                "name": p.name,
                "username": p.username,
                "picture_url": p.picture_url,
                "access_token": p.access_token,
                "tasks": list(p.tasks),
            }
            for p in pages
        ],
    }
    # The code works once: keep what it gave under the same nonce, encrypted, for the pick.
    rest = {k: v for k, v in held.items() if k != "code"}
    rest["pages"] = deps.cipher.encrypt(json.dumps(keep)).decode()
    await redis.set(_held_key(nonce), json.dumps(rest), ex=HELD_TTL_S)
    return user, pages


async def list_pages(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    nonce: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> FacebookPageList:
    held = await _held(redis, nonce, workspace_id=workspace_id, user_id=user_id)
    _, pages = await _pages_of(redis, deps, nonce, held)
    items: list[FacebookPageOption] = []
    for page in pages:
        existing = await accounts.find(session, Platform.FACEBOOK, page.id)
        items.append(
            FacebookPageOption(
                id=page.id,
                name=page.name,
                username=page.username,
                picture_url=page.picture_url,
                connected=existing is not None and existing.status != AccountStatus.DISCONNECTED,
                can_connect=page.can_message,
                problem=None if page.can_message else NO_MESSAGING,
            )
        )
    return FacebookPageList(items=items)


async def connect_pages(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    nonce: str,
    page_ids: list[str],
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
) -> list[SocialAccount]:
    held = await _held(redis, nonce, workspace_id=workspace_id, user_id=user_id)
    if "pages" not in held:
        raise ApiError("conflict", "List your Pages first.")
    user, pages = await _pages_of(redis, deps, nonce, held)
    by_id = {p.id: p for p in pages}
    chosen: list[oauth.FacebookPage] = []
    errors: list[FieldError] = []
    for page_id in dict.fromkeys(page_ids):
        page = by_id.get(page_id)
        if page is None:
            errors.append(FieldError("page_ids", NOT_LISTED))
        elif not page.can_message:
            errors.append(FieldError("page_ids", f"{page.name or page.id}: {NO_MESSAGING}"))
        else:
            chosen.append(page)
    if errors:
        raise ApiError("validation_error", errors=errors)

    # A deletion that began after the request was let in: nothing may be added to it (T9.6).
    if not await workspaces.is_active(session, workspace_id, lock=True):
        raise ApiError("not_found")
    await _check_room(session, chosen, plan)

    now = datetime.now(UTC)
    connected: list[SocialAccount] = []
    for page in chosen:
        values: dict[str, Any] = {
            "app_scoped_id": user.id,
            "username": page.username,
            "display_name": page.name or page.username,
            "profile_picture_url": page.picture_url,
            "access_token_enc": deps.cipher.encrypt(page.access_token),
            "token_expires_at": None,  # a Page token made from a long-lived user token
            "token_refreshed_at": now,
            "scopes": list(oauth.SCOPES),
            "status": AccountStatus.ACTIVE,
            "last_error": None,
            "connected_at": now,
            "disconnected_at": None,
            "connected_by_user_id": user_id,
        }
        acct = await _upsert(session, Platform.FACEBOOK, page.id, values)
        if acct is None:
            log.info("facebook_connect_refused", reason="account_in_use", page_id=page.id)
            raise ApiError("account_in_use", f"{page.name or page.id}: {IN_USE}")
        await subscribe(session, acct, deps)
        connected.append(acct)
    await session.commit()
    await redis.delete(_held_key(nonce))
    for acct in connected:
        await session.refresh(acct)
        await start_initial_sync(acct)  # FR-CON-01: recent posts and conversations
    log.info("facebook_connected", pages=len(connected))
    return connected


async def _check_room(session: AsyncSession, chosen: list[oauth.FacebookPage], plan: str) -> None:
    """The plan's accounts_per_platform for all the picked Pages at once: a Page that is already
    live uses its own slot."""
    limit = entitlement(plan, "accounts_per_platform")
    if limit is None:
        return
    new = 0
    for page in chosen:
        existing = await accounts.find(session, Platform.FACEBOOK, page.id)
        if existing is None or existing.status == AccountStatus.DISCONNECTED:
            new += 1
    if new and await accounts.count_live(session, Platform.FACEBOOK) + new > int(limit):
        raise _quota_error(int(limit), Platform.FACEBOOK)
