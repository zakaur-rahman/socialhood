"""Notification settings (P8: FR-NOT-03, FR-NOT-04, TR-FE-09, F-19, UX-SCR-07): the member's
preferences, this browser's push subscription, the push configuration and the digest's one-click
unsubscribe. In-app notifications (the list and read state) are in schemas/accounts.py."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel


class PushPreferences(RequestModel):
    """One switch per push event (models/notifications.PushEvent); all on by default
    (models/identity.DEFAULT_NOTIFICATION_PREFS)."""

    needs_you: bool  # a conversation escalated to "Needs you"
    new_lead: bool  # lead score reaches 70
    window_closing: bool  # a lead's reply window is closing (FR-INB-14)
    account: bool  # an account needs reconnecting or was disconnected


class NotificationPreferences(RequestModel):
    """GET and PUT …/notification-preferences: the signed-in member's settings in this
    workspace (workspace_members.notification_prefs). PUT sends the whole object and gets it
    back. Fields are required both ways, so the request and response share one schema."""

    email_digest: bool
    push: PushPreferences


class PushKeys(RequestModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscriptionCreate(RequestModel):
    """POST /v1/me/push-subscriptions: the browser's ``PushSubscription.toJSON()`` (endpoint and
    keys) plus the user agent, shown as the device name. Registering an endpoint again updates it
    (and moves it to the caller if another user had it: the browser now belongs to them)."""

    endpoint: str = Field(min_length=12, max_length=2000, pattern=r"^https://")
    keys: PushKeys
    user_agent: str | None = Field(default=None, max_length=500)


class PushDevice(ResponseModel):
    """A registered browser; never its keys."""

    id: uuid.UUID
    user_agent: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None


class PushConfig(ResponseModel):
    """GET /v1/push/config: what the browser needs to subscribe. The web reads the VAPID public
    key here rather than from a build-time variable, so one deploy serves any key."""

    enabled: bool  # false when the API has no VAPID keys: the page shows push as unavailable
    vapid_public_key: str | None = None  # base64url, the applicationServerKey


class DigestUnsubscribed(ResponseModel):
    """POST /v1/digest/unsubscribe?token=…: the digest is off for that member of that workspace
    (idempotent). The page names the workspace and links to Settings → Notifications."""

    workspace_name: str
    email_digest: bool  # always false after the call
