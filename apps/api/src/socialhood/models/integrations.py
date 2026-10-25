"""Outbound events and webhooks (GR-04): a workspace's endpoints and each delivery to them.

An event (services/webhooks/events.py has the catalogue) becomes one delivery row per active
endpoint subscribed to it, in the transaction that caused it; the deliver_webhook job posts it
signed (Standard Webhooks) and records each attempt.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class EndpointStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"  # turned off by a member
    DISABLED = "disabled"  # turned off after repeated failures


class DeliveryStatus(StrEnum):
    PENDING = "pending"  # waiting for its first or next attempt
    SUCCEEDED = "succeeded"
    FAILED = "failed"  # every attempt failed, or the endpoint is gone or off


class GoogleStatus(StrEnum):
    ACTIVE = "active"
    NEEDS_RECONNECT = "needs_reconnect"  # Google no longer accepts the saved access (GR-27)


class WebhookEndpoint(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "webhook_endpoints"

    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    # The event types it receives (services/webhooks/events.EVENTS).
    events: Mapped[list[str]] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(Text, server_default=sql("'active'"))
    # The signing secret ("whsec_" and a base64 key), encrypted like platform tokens (SEC-03).
    secret_enc: Mapped[bytes] = mapped_column(LargeBinary)
    # Deliveries that ran out of attempts since the last success; at the limit it's disabled.
    failing_deliveries: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # GR-26: the API key that subscribed it (a Zapier trigger's REST hook, services/api_hooks.py).
    # These endpoints go with the key, and don't count against the plan's webhook_endpoints.
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE")
    )

    __table_args__ = (
        Index(
            "ix_webhook_endpoints_api_key_id",
            "api_key_id",
            postgresql_where=sql("api_key_id IS NOT NULL"),
        ),
        CheckConstraint(_in("status", EndpointStatus), name="status"),
        CheckConstraint("char_length(url) BETWEEN 8 AND 2000", name="url_length"),
        CheckConstraint("cardinality(events) BETWEEN 1 AND 20", name="events"),
    )


class WebhookDelivery(IdMixin, TimestampMixin, TenantScoped, Base):
    """One event to one endpoint, with its last attempt. ``event_id`` is the same for every
    endpoint and every attempt (the receiver's idempotency key, ``webhook-id``); a replay is a
    new delivery of the same event."""

    __tablename__ = "webhook_deliveries"

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE")
    )
    event_id: Mapped[uuid.UUID] = mapped_column()
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'pending'"))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)  # why the last attempt failed
    replay_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("webhook_deliveries.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_webhook_deliveries_endpoint_created", "endpoint_id", sql("created_at DESC")),
        CheckConstraint(_in("status", DeliveryStatus), name="status"),
    )


class GoogleConnection(IdMixin, TimestampMixin, TenantScoped, Base):
    """A workspace's Google Sheets sync (GR-27): the connected Google account, the one sheet rows
    go to and how a captured lead maps to its columns. One per workspace. ``credential_enc`` is
    Google's refresh credential, encrypted like platform tokens (SEC-03); it never leaves the
    server. ``mapping`` is a list of ``{"field": …, "header": …}``, one per column in order."""

    __tablename__ = "google_connections"

    google_email: Mapped[str | None] = mapped_column(Text)
    credential_enc: Mapped[bytes] = mapped_column(LargeBinary)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'"))
    status: Mapped[str] = mapped_column(Text, server_default=sql("'active'"))
    last_error: Mapped[str | None] = mapped_column(Text)
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    spreadsheet_id: Mapped[str | None] = mapped_column(Text)
    spreadsheet_title: Mapped[str | None] = mapped_column(Text)
    spreadsheet_url: Mapped[str | None] = mapped_column(Text)
    sheet_tab: Mapped[str | None] = mapped_column(Text)
    # Amplychat made the sheet, so it may write the header row; a sheet the person already had is
    # never overwritten.
    sheet_created: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    mapping: Mapped[list[dict[str, str]]] = mapped_column(JSONB, server_default=sql("'[]'::jsonb"))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("workspace_id"),
        CheckConstraint(_in("status", GoogleStatus), name="status"),
    )


class SheetRow(IdMixin, TimestampMixin, TenantScoped, Base):
    """One captured lead on its way to the sheet (GR-27). ``event_id`` is the ``lead.captured``
    event's id (one row per event and connection). ``source`` is what the columns are made from
    when it is sent (see services/sheets.py): the person's name, @username, platform, email, phone,
    custom fields, the automation, when it was captured and their consent."""

    __tablename__ = "sheet_rows"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("google_connections.id", ondelete="CASCADE")
    )
    event_id: Mapped[uuid.UUID] = mapped_column()
    source: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'pending'"))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)  # why the last attempt failed, in plain words
    error_code: Mapped[str | None] = mapped_column(Text)  # services/sheets.py REASONS

    __table_args__ = (
        UniqueConstraint("connection_id", "event_id"),
        Index("ix_sheet_rows_connection_created", "connection_id", sql("created_at DESC")),
        CheckConstraint(_in("status", DeliveryStatus), name="status"),
    )
