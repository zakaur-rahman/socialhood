"""Notification settings (§2.15; FR-NOT-03, FR-NOT-04, TR-FE-09, F-19, UX-SCR-07): the member's
preferences, this browser's push subscription, the push configuration and the digest's one-click
unsubscribe. In-app notifications are in api/v1/notifications.py.

Push subscriptions belong to the user, not a workspace (§5.3): a browser gets the pushes of every
workspace its user is in, each filtered by that membership's preferences. Only browser push
services are accepted as endpoints (notify/push_webpush.is_push_service), because the API later
POSTs to them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.api import ratelimit
from socialhood.auth.deps import AnyMember, CurrentUser, Session
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError, FieldError
from socialhood.models.identity import Workspace
from socialhood.notify import preferences
from socialhood.notify.push_webpush import is_push_service
from socialhood.notify.unsubscribe import read_token
from socialhood.observability.logging import get_logger
from socialhood.repositories import push_subscriptions
from socialhood.schemas.notifications import (
    DigestUnsubscribed,
    NotificationPreferences,
    PushConfig,
    PushDevice,
    PushSubscriptionCreate,
)
from socialhood.settings import Settings

router = APIRouter(tags=["notifications"])
log = get_logger(__name__)

MAX_DEVICES = 10  # per user; registering an eleventh forgets the least recently used


# ---------------------------------------------------------------- preferences (T8.6)


@router.get("/v1/w/{wid}/notification-preferences", operation_id="get_notification_preferences")
async def get_notification_preferences(ctx: AnyMember, session: Session) -> NotificationPreferences:
    """The signed-in member's weekly digest switch and push switches in this workspace."""
    prefs = await preferences.load(session, ctx.user.id)
    if prefs is None:  # pragma: no cover - workspace_ctx found the membership
        raise ApiError("not_found")
    return NotificationPreferences.model_validate(prefs)


@router.put("/v1/w/{wid}/notification-preferences", operation_id="update_notification_preferences")
async def update_notification_preferences(
    body: NotificationPreferences, ctx: AnyMember, session: Session
) -> NotificationPreferences:
    """Replace the member's preferences (their own only; any role)."""
    prefs = await preferences.save(session, ctx.user.id, body.model_dump())
    if prefs is None:  # pragma: no cover - workspace_ctx found the membership
        raise ApiError("not_found")
    await session.commit()
    return NotificationPreferences.model_validate(prefs)


# ---------------------------------------------------------------- push (T8.6)


@router.get("/v1/push/config", operation_id="get_push_config")
async def get_push_config(request: Request, user: CurrentUser) -> PushConfig:
    """The VAPID public key the browser subscribes with (TR-FE-09); ``enabled`` is false when
    the API has no VAPID keys, and the page shows push as unavailable."""
    settings: Settings = request.app.state.settings
    private = settings.vapid_private_key
    enabled = (
        bool(settings.vapid_public_key) and private is not None and bool(private.get_secret_value())
    )
    return PushConfig(
        enabled=enabled, vapid_public_key=settings.vapid_public_key if enabled else None
    )


@router.post("/v1/me/push-subscriptions", status_code=201, operation_id="create_push_subscription")
async def create_push_subscription(
    body: PushSubscriptionCreate, user: CurrentUser, session: Session
) -> PushDevice:
    """Register this browser (F-19), or refresh it: the endpoint is unique, so registering it
    again updates its keys, clears a failure count or disabled state, and gives it to the caller.
    422 for an endpoint that isn't a browser push service. A user keeps their 10 most recently
    used browsers."""
    if not is_push_service(body.endpoint):
        raise ApiError(
            "validation_error",
            "This browser's push service isn't supported.",
            errors=[FieldError("endpoint", "Use the endpoint the browser's PushManager gave.")],
        )
    row = await push_subscriptions.upsert(
        session,
        user_id=user.id,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        user_agent=body.user_agent,
    )
    await push_subscriptions.trim(session, user.id, keep=MAX_DEVICES)
    await session.commit()
    return PushDevice.model_validate(row, from_attributes=True)


@router.delete(
    "/v1/me/push-subscriptions", status_code=204, operation_id="delete_push_subscription"
)
async def delete_push_subscription(
    user: CurrentUser,
    session: Session,
    endpoint: Annotated[str, Query(min_length=12, max_length=2000)],
) -> Response:
    """Remove this browser's subscription (push turned off). Only the caller's own row is
    removed; an unknown endpoint, or another user's, is 204 all the same and changes nothing."""
    await push_subscriptions.delete_for_user(session, user_id=user.id, endpoint=endpoint)
    await session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- digest (T8.7)


@router.post(
    "/v1/digest/unsubscribe", operation_id="unsubscribe_digest", dependencies=[ratelimit.PUBLIC]
)
async def unsubscribe_digest(
    request: Request, session: Session, token: Annotated[str, Query(min_length=1, max_length=100)]
) -> DigestUnsubscribed:
    """Public, no sign-in (FR-NOT-04 one click): the signed token (notify/unsubscribe.py) turns
    the weekly digest off for its member and workspace. Also the target of the email's
    List-Unsubscribe-Post (RFC 8058), whose form body is ignored. 404 not_found for a token that
    doesn't verify or a membership that no longer exists. Never a GET, so link scanners can't
    unsubscribe anyone: the email links to the web's /unsubscribe page, which posts here."""
    settings: Settings = request.app.state.settings
    claim = read_token(token, settings.token_encryption_keys)
    if claim is None:
        raise ApiError("not_found", "This unsubscribe link isn't valid.")
    with workspace_scope(claim.workspace_id):
        workspace = await session.get(Workspace, claim.workspace_id)
        if workspace is None or not await preferences.turn_off_digest(session, claim.user_id):
            raise ApiError("not_found", "This unsubscribe link isn't valid.")
        await session.commit()
    log.info("digest_unsubscribed", workspace_id=str(claim.workspace_id))
    return DigestUnsubscribed(workspace_name=workspace.name, email_digest=False)
