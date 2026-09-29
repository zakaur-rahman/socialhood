"""Notifications (§5.9, FR-NOT-01…04): in-app rows, and the email, push and digest plumbing of
P8 (T8.5…T8.7).

- ``notifications``: one row per recipient. ``channels`` says where it goes: always ``in_app``;
  ``email`` for the types in EMAIL_TYPES (FR-NOT-02); ``push`` for the types in
  PUSH_EVENT_OF_TYPE (FR-NOT-03), subject to the member's preferences. ``emailed_at`` and
  ``pushed_at`` record delivery, so a sweeper can find what a lost job never sent.
- ``email_deliveries``: the email outbox. One row per email, unique per (workspace, dedupe_key),
  inserted in the same transaction as what caused it, sent by deliver_email; the dedupe key is
  also Resend's Idempotency-Key, so an email goes out once per event (T8.5).
- ``push_subscriptions``: one row per browser (§5.3, user-scoped, not tenant): a device gets the
  pushes of every workspace its user belongs to, filtered by that member's preferences. 404 or
  410 from the push service deletes the row (TR-FE-09); other failures count up and disable it.
- ``weekly_digests``: one row per workspace per ISO week (the Monday it covers, in the workspace
  time zone), so send_weekly_digests sends once per week however often it runs (T8.7).

Preferences are ``workspace_members.notification_prefs`` (§5.3, DEFAULT_NOTIFICATION_PREFS in
models/identity.py): the weekly digest switch and one push switch per PushEvent. In-app
notifications are always on (FR-NOT-01); account and payment emails (FR-NOT-02) are not optional.
Unsubscribe links carry a signed token (notify/unsubscribe.py), so they need no table.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"


class NotificationType(StrEnum):
    """Every notification type. Producers and the email and push rules share these names."""

    ACCOUNT_NEEDS_RECONNECT = "account_needs_reconnect"  # F-05
    ACCOUNT_DISCONNECTED = "account_disconnected"  # F-16 Meta deauthorize
    POST_FAILED = "post_failed"  # F-13
    SCHEDULED_MESSAGE_EXPIRED = "scheduled_message_expired"
    AI_CREDITS_80 = "ai_credits_80"  # FR-BIL-05
    AI_CREDITS_100 = "ai_credits_100"
    AI_ESCALATED = "ai_escalated"  # "Needs you" (F-09)
    WINDOW_CLOSING = "window_closing"  # F-18
    AUTOMATION_ENDED = "automation_ended"  # FR-AUT-17
    NEW_LEAD = "new_lead"  # lead score reaches 70 (FR-NOT-03; T8.6)
    PAYMENT_PROBLEM = "payment_problem"  # subscription on hold or a failed payment (FR-BIL-06)
    PLAN_ACTIVATED = "plan_activated"  # "We'll email you when Pro is active" (F-15)
    PLAN_DOWNGRADED = "plan_downgraded"  # expired: what the downgrade changed (FR-BIL-07)


class PushEvent(StrEnum):
    """The push switches (FR-NOT-03, F-19, UX-SCR-07): keys of notification_prefs["push"]."""

    NEEDS_YOU = "needs_you"
    NEW_LEAD = "new_lead"
    WINDOW_CLOSING = "window_closing"
    ACCOUNT = "account"


# Which notification types push, and under which switch (FR-NOT-03).
PUSH_EVENT_OF_TYPE: dict[str, PushEvent] = {
    NotificationType.AI_ESCALATED: PushEvent.NEEDS_YOU,
    NotificationType.NEW_LEAD: PushEvent.NEW_LEAD,
    NotificationType.WINDOW_CLOSING: PushEvent.WINDOW_CLOSING,
    NotificationType.ACCOUNT_NEEDS_RECONNECT: PushEvent.ACCOUNT,
    NotificationType.ACCOUNT_DISCONNECTED: PushEvent.ACCOUNT,
}

# Which notification types are also emailed (FR-NOT-02, F-15). Not optional for the member.
EMAIL_TYPES: frozenset[str] = frozenset(
    {
        NotificationType.ACCOUNT_NEEDS_RECONNECT,
        NotificationType.PAYMENT_PROBLEM,
        NotificationType.PLAN_ACTIVATED,
        NotificationType.PLAN_DOWNGRADED,
        NotificationType.POST_FAILED,
    }
)


class Notification(IdMixin, CreatedAtMixin, TenantScoped, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text, server_default=text("'info'"))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{in_app}'"))
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # T8.6

    __table_args__ = (
        Index(
            "uq_notifications_user_id_dedupe_key",
            "user_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
        Index("ix_notifications_user_id_created_at", "user_id", text("created_at DESC")),
        CheckConstraint(_in("severity", Severity), name="severity"),
        CheckConstraint("channels <@ ARRAY['in_app', 'email', 'push']::text[]", name="channels"),
    )


class PushSubscription(IdMixin, TimestampMixin, Base):
    """A browser's Web Push subscription (§5.3; TR-FE-09). User-scoped, not tenant: the
    endpoint is unique, so a browser is one row whichever workspace registered it."""

    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)  # shown as the device name
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("endpoint ~ '^https://'", name="endpoint"),
        CheckConstraint("failure_count >= 0", name="failure_count"),
    )


# Consecutive failures (not 404 or 410, which delete the row) before a subscription is disabled.
PUSH_MAX_FAILURES = 5


class EmailStatus(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"  # nothing to send: no address, unsubscribed, or the reason in ``error``


class EmailTemplate(StrEnum):
    """Email templates (notify/templates/, T8.5 and T8.7). A notification email uses the
    template named after its type; the digest has its own."""

    ACCOUNT_NEEDS_RECONNECT = "account_needs_reconnect"
    PAYMENT_PROBLEM = "payment_problem"
    PLAN_ACTIVATED = "plan_activated"
    PLAN_DOWNGRADED = "plan_downgraded"
    POST_FAILED = "post_failed"
    WEEKLY_DIGEST = "weekly_digest"


class EmailDelivery(IdMixin, TimestampMixin, TenantScoped, Base):
    """The email outbox (T8.5, FR-NOT-02, FR-NOT-04). ``dedupe_key`` examples:
    ``notification:{notification_id}``, ``digest:{week_start}:{user_id}``."""

    __tablename__ = "email_deliveries"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL")
    )
    template: Mapped[str] = mapped_column(Text)
    to_email: Mapped[str] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)  # set when rendered
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    dedupe_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    provider_message_id: Mapped[str | None] = mapped_column(Text)  # Resend's email id
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("workspace_id", "dedupe_key"),
        Index(
            "ix_email_deliveries_queued",
            "created_at",
            postgresql_where=text("status = 'queued'"),
        ),
        # ``template`` is checked in code (EmailTemplate), so a new template needs no migration.
        CheckConstraint(_in("status", EmailStatus), name="status"),
        CheckConstraint("status <> 'sent' OR sent_at IS NOT NULL", name="sent_at"),
    )


class DigestStatus(StrEnum):
    PENDING = "pending"  # claimed by send_weekly_digests, emails being queued
    SENT = "sent"  # one email_deliveries row per opted-in member was queued
    SKIPPED = "skipped"  # nobody opted in, or nothing happened that week
    FAILED = "failed"


class WeeklyDigest(IdMixin, TimestampMixin, TenantScoped, Base):
    """One weekly digest per workspace per ISO week (FR-NOT-04, T8.7). ``week_start`` is the
    Monday (workspace time zone) the digest is sent on; it covers the 7 days before it."""

    __tablename__ = "weekly_digests"

    week_start: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    recipients: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # the numbers as sent
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("workspace_id", "week_start"),
        CheckConstraint(_in("status", DigestStatus), name="status"),
        CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="week_start"),
        CheckConstraint("recipients >= 0", name="recipients"),
    )
