"""Platform plumbing (§5.9): stored webhook events.

Not tenant-scoped; an event is routed to its workspace when processed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin
from socialhood.models.identity import _in


class WebhookProvider(StrEnum):
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    DODO = "dodo"
    CLERK = "clerk"


class WebhookStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


class WebhookEvent(IdMixin, Base):
    __tablename__ = "webhook_events"

    provider: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    platform_account_id: Mapped[str | None] = mapped_column(Text)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column()
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=text("'received'"))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("provider", "dedupe_key"),
        Index("ix_webhook_events_status_received_at", "status", "received_at"),
        CheckConstraint(_in("provider", WebhookProvider), name="provider"),
        CheckConstraint(_in("status", WebhookStatus), name="status"),
    )
