"""Notification settings (§2.15; FR-NOT-03, FR-NOT-04, TR-FE-09, F-19, UX-SCR-07): the member's
preferences, this browser's push subscription, the push configuration and the digest's one-click
unsubscribe. In-app notifications are in api/v1/notifications.py.

The P8 contract: each route keeps its ``openapi_extra`` marker until its task (T8.6, T8.7)
builds it. Push subscriptions belong to the user, not a workspace (§5.3): a browser gets the pushes
of every workspace its user is in, each filtered by that membership's preferences.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import AnyMember, CurrentUser, Session
from socialhood.schemas.notifications import (
    DigestUnsubscribed,
    NotificationPreferences,
    PushConfig,
    PushDevice,
    PushSubscriptionCreate,
)
from socialhood.settings import Settings

router = APIRouter(tags=["notifications"])


# ---------------------------------------------------------------- preferences (T8.6)


@router.get(
    "/v1/w/{wid}/notification-preferences",
    operation_id="get_notification_preferences",
    openapi_extra=pending("T8.6"),
)
async def get_notification_preferences(ctx: AnyMember, session: Session) -> NotificationPreferences:
    """The signed-in member's weekly digest switch and push switches in this workspace."""
    raise NotImplementedError("T8.6")


@router.put(
    "/v1/w/{wid}/notification-preferences",
    operation_id="update_notification_preferences",
    openapi_extra=pending("T8.6"),
)
async def update_notification_preferences(
    body: NotificationPreferences, ctx: AnyMember, session: Session
) -> NotificationPreferences:
    """Replace the member's preferences (their own only; any role)."""
    raise NotImplementedError("T8.6")


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


@router.post(
    "/v1/me/push-subscriptions",
    status_code=201,
    operation_id="create_push_subscription",
    openapi_extra=pending("T8.6"),
)
async def create_push_subscription(
    body: PushSubscriptionCreate, user: CurrentUser, session: Session
) -> PushDevice:
    """Register this browser (F-19), or refresh it: the endpoint is unique, so registering it
    again updates its keys, clears a failure count or disabled state, and gives it to the caller."""
    raise NotImplementedError("T8.6")


@router.delete(
    "/v1/me/push-subscriptions",
    status_code=204,
    operation_id="delete_push_subscription",
    openapi_extra=pending("T8.6"),
)
async def delete_push_subscription(
    user: CurrentUser,
    session: Session,
    endpoint: Annotated[str, Query(min_length=12, max_length=2000)],
) -> Response:
    """Remove this browser's subscription (push turned off). Only the caller's own row is
    removed; an unknown endpoint, or another user's, is 204 all the same and changes nothing."""
    raise NotImplementedError("T8.6")


# ---------------------------------------------------------------- digest (T8.7)


@router.post(
    "/v1/digest/unsubscribe",
    operation_id="unsubscribe_digest",
    openapi_extra=pending("T8.7"),
)
async def unsubscribe_digest(
    session: Session, token: Annotated[str, Query(min_length=1, max_length=100)]
) -> DigestUnsubscribed:
    """Public, no sign-in (FR-NOT-04 one click): the signed token (notify/unsubscribe.py) turns
    the weekly digest off for its member and workspace. Also the target of the email's
    List-Unsubscribe-Post (RFC 8058), whose form body is ignored. 404 not_found for a token that
    doesn't verify or a membership that no longer exists. Never a GET, so link scanners can't
    unsubscribe anyone: the email links to the web's /unsubscribe page, which posts here."""
    raise NotImplementedError("T8.7")
