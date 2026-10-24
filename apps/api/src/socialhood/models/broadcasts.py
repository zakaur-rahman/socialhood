"""WhatsApp broadcasts (GR-23): one approved template sent to a segment's opted-in contacts.

- ``broadcasts``: the message (an approved template, each variable mapped to a contact field or a
  fixed value), the audience (a saved segment, filtered to WhatsApp contacts of the chosen number
  with marketing consent granted), when it goes (now, or a time), and where it stands. The
  template's name, language, category and body are copied when the broadcast is made, so the
  preview and the cost estimate do not depend on a call to Meta. ``estimated_cost`` is Meta's rate
  card times the recipients, in INR; it is information, not a charge (the business pays Meta
  directly: PD-3).
- ``broadcast_recipients``: the audience, fixed when the broadcast starts. ``state`` is only what
  we know ourselves (``pending`` waiting its turn, ``dispatched`` handed to the send queue,
  ``skipped`` never sent, ``failed`` could not be handed over). What WhatsApp reports afterwards
  (sent, delivered, read, failed) is read from the message row, so there is one source of truth.
- ``whatsapp_number_health``: the number's quality rating and messaging limit as last heard from
  WhatsApp, which paces a broadcast and pauses it when quality drops.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class BroadcastStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"  # could not start (no one to send to, the number is gone)


class RecipientState(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    SKIPPED = "skipped"
    FAILED = "failed"


class SkipReason(StrEnum):
    OPTED_OUT = "opted_out"  # the latest marketing record is a withdrawal
    NO_CONSENT = "no_consent"  # no marketing record at all
    MISSING_VALUE = "missing_value"  # a variable has no value and no fallback
    CANCELLED = "cancelled"  # the broadcast was cancelled before this person's turn


class QualityRating(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


class Broadcast(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "broadcasts"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    # The segment is kept by reference (its name too, in case it is deleted later).
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contact_segments.id", ondelete="SET NULL")
    )
    segment_name: Mapped[str] = mapped_column(Text)
    template_name: Mapped[str] = mapped_column(Text)
    template_language: Mapped[str] = mapped_column(Text)
    template_category: Mapped[str] = mapped_column(Text)
    template_body: Mapped[str] = mapped_column(Text)
    # [{"source": "field" | "fixed", "field": "first_name", "value": None, "fallback": "there"}],
    # in the order of the template's {{1}}, {{2}}, ...
    variables: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sql("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, server_default=sql("'draft'"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Why it is paused (or failed): a short code and a plain sentence for the page.
    paused_code: Mapped[str | None] = mapped_column(Text)
    paused_reason: Mapped[str | None] = mapped_column(Text)
    # Fixed when it starts: the audience as it was and what Meta's rate card says it costs.
    audience_size: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    rate_per_message: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cost_currency: Mapped[str] = mapped_column(Text, server_default=sql("'INR'"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_broadcasts_listing", "workspace_id", sql("created_at DESC"), "id"),
        Index(
            "ix_broadcasts_active",
            "status",
            "scheduled_at",
            postgresql_where=sql("status IN ('scheduled', 'sending')"),
        ),
        CheckConstraint(_in("status", BroadcastStatus), name="status"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint("jsonb_typeof(variables) = 'array'", name="variables_array"),
    )


class BroadcastRecipient(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "broadcast_recipients"

    broadcast_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("broadcasts.id", ondelete="CASCADE"))
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)  # the order they go out in
    state: Mapped[str] = mapped_column(Text, server_default=sql("'pending'"))
    skip_reason: Mapped[str | None] = mapped_column(Text)
    # The template's body parameters for this person, worked out when the broadcast started.
    params: Mapped[list[str]] = mapped_column(JSONB, server_default=sql("'[]'::jsonb"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("broadcast_id", "contact_id"),
        Index("ix_broadcast_recipients_queue", "broadcast_id", "state", "position"),
        Index("ix_broadcast_recipients_contact", "contact_id"),
        Index("ix_broadcast_recipients_message", "message_id"),
        Index(
            "ix_broadcast_recipients_dispatched",
            "workspace_id",
            "dispatched_at",
            postgresql_where=sql("dispatched_at IS NOT NULL"),
        ),
        CheckConstraint(_in("state", RecipientState), name="state"),
        CheckConstraint(
            f"skip_reason IS NULL OR {_in('skip_reason', SkipReason)}", name="skip_reason"
        ),
    )


class WhatsAppNumberHealth(IdMixin, TimestampMixin, TenantScoped, Base):
    """What WhatsApp last said about a connected number: its quality rating and how many people
    it may message a day. One row per account."""

    __tablename__ = "whatsapp_number_health"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    quality_rating: Mapped[str] = mapped_column(Text, server_default=sql("'unknown'"))
    messaging_tier: Mapped[str | None] = mapped_column(Text)  # TIER_250, TIER_1K, ...
    daily_limit: Mapped[int | None] = mapped_column(Integer)  # people a day; null: not known
    source: Mapped[str] = mapped_column(Text, server_default=sql("'webhook'"))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("social_account_id"),
        CheckConstraint(_in("quality_rating", QualityRating), name="quality_rating"),
        CheckConstraint("daily_limit IS NULL OR daily_limit > 0", name="daily_limit"),
    )
