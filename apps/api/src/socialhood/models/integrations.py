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
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
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

    __table_args__ = (
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
