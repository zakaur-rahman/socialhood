"""Sequences (GR-24): timed follow-up messages after an entry event.

- ``sequences``: one per follow-up plan. It belongs to one connected account (so one channel), has
  an entry event (a lead captured, a tag added, a broadcast replied to), stop rules (a reply, a
  tag, a lead stage) and a status (draft, active, paused).
- ``sequence_steps``: the messages, in order. A step waits ``delay_seconds`` from the contact's
  entry or from the previous step, then sends a text, or on WhatsApp outside the 24-hour window an
  approved template (copied when the step is saved, like a broadcast's). An optional send window
  keeps it inside business hours (GR-22).
- ``sequence_enrolments``: a contact in a sequence: the step they are on, when it is due, how it
  ended. At most one active enrolment per contact and sequence (a partial unique index).
- ``sequence_step_runs``: what happened at each step for each enrolment (sent, skipped with a
  reason, failed). One row per (enrolment, step position): the guard that makes a retry or a second
  worker send a step once.
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
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class SequenceStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class EntryType(StrEnum):
    CAPTURED = "captured"  # a lead was captured (GR-14): an email, a phone or a field
    TAGGED = "tagged"  # a tag was added (GR-02)
    BROADCAST_REPLIED = "broadcast_replied"  # they answered a WhatsApp broadcast (GR-23)
    LEAD_STAGE = "lead_stage"  # their lead moved into a stage (GR-18)


class DelayFrom(StrEnum):
    ENTRY = "entry"  # counted from when the contact entered
    PREVIOUS = "previous"  # counted from when the step before ran


class EnrolmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    STOPPED = "stopped"


class StopReason(StrEnum):
    REPLY = "reply"  # the contact wrote
    TAG = "tag"  # a stop tag was added
    TAG_REMOVED = "tag_removed"  # a tag they needed was taken off
    STAGE = "stage"  # their lead stage became a stop stage
    MEMBER = "member"  # someone took them out
    ENDED = "ended"  # the sequence has no step to run (its steps were removed)


class RunStatus(StrEnum):
    SENT = "sent"  # handed to the send queue
    SKIPPED = "skipped"  # not sent, with the reason
    FAILED = "failed"  # the send was refused, with the reason


class Sequence(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "sequences"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'draft'"))
    # The entry event. ``entry_tag_id`` is for ``tagged``; ``entry_broadcast_id`` narrows
    # ``broadcast_replied`` to one broadcast (null: any); ``entry_capture_kind`` narrows
    # ``captured`` to an email, a phone or a field (null: any).
    entry_type: Mapped[str] = mapped_column(Text)
    entry_tag_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tags.id", ondelete="SET NULL")
    )
    entry_broadcast_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="SET NULL")
    )
    entry_capture_kind: Mapped[str | None] = mapped_column(Text)
    # ``entry_stage`` is the lead stage that starts a ``lead_stage`` sequence.
    entry_stage: Mapped[str | None] = mapped_column(Text)
    # Stop rules: any customer reply (default on), a tag from the list, a lead stage from the list,
    # a tag from ``stop_removed_tag_ids`` being taken off.
    stop_on_reply: Mapped[bool] = mapped_column(server_default=sql("true"))
    stop_tag_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), server_default=sql("'{}'")
    )
    stop_stages: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'"))
    stop_removed_tag_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), server_default=sql("'{}'")
    )
    # Whether a contact who finished (or was stopped) can enter again.
    allow_reentry: Mapped[bool] = mapped_column(server_default=sql("false"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_sequences_listing", "workspace_id", sql("created_at DESC"), "id"),
        Index(
            "ix_sequences_active", "social_account_id", postgresql_where=sql("status = 'active'")
        ),
        CheckConstraint(_in("status", SequenceStatus), name="status"),
        CheckConstraint(_in("entry_type", EntryType), name="entry_type"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint(
            "entry_capture_kind IS NULL OR entry_capture_kind IN ('email', 'phone', 'field')",
            name="entry_capture_kind",
        ),
        CheckConstraint(
            "entry_stage IS NULL "
            "OR entry_stage IN ('new', 'qualified', 'follow_up', 'won', 'lost')",
            name="entry_stage",
        ),
        CheckConstraint("cardinality(stop_tag_ids) <= 20", name="stop_tag_ids_length"),
        CheckConstraint(
            "cardinality(stop_removed_tag_ids) <= 20", name="stop_removed_tag_ids_length"
        ),
        CheckConstraint("cardinality(stop_stages) <= 5", name="stop_stages_length"),
    )


class SequenceStep(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "sequence_steps"

    sequence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sequences.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)  # 0, 1, 2, ... in order
    delay_seconds: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    delay_from: Mapped[str] = mapped_column(Text, server_default=sql("'previous'"))
    # The message. WhatsApp outside the 24-hour window sends the template, which needs the
    # contact's marketing consent; inside the window (and on Instagram and Facebook, which have no
    # templates) the text is sent. Either may be missing, not both.
    text: Mapped[str | None] = mapped_column(Text)
    template_name: Mapped[str | None] = mapped_column(Text)
    template_language: Mapped[str | None] = mapped_column(Text)
    template_category: Mapped[str | None] = mapped_column(Text)
    template_body: Mapped[str | None] = mapped_column(Text)
    # The mapping of the template's {{1}}, {{2}}... as in a broadcast (broadcasts/variables).
    variables: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sql("'[]'::jsonb")
    )
    # Hold the step until the account is open (business hours, GR-22).
    respect_hours: Mapped[bool] = mapped_column(server_default=sql("false"))

    __table_args__ = (
        UniqueConstraint("sequence_id", "position"),
        CheckConstraint(_in("delay_from", DelayFrom), name="delay_from"),
        CheckConstraint("delay_seconds BETWEEN 0 AND 2592000", name="delay_seconds"),
        CheckConstraint("text IS NOT NULL OR template_name IS NOT NULL", name="has_content"),
        CheckConstraint("jsonb_typeof(variables) = 'array'", name="variables_array"),
    )


class SequenceEnrolment(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "sequence_enrolments"

    sequence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sequences.id", ondelete="CASCADE"))
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, server_default=sql("'active'"))
    # The position of the step to run next, and when it is due (null once finished).
    current_step: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_event: Mapped[str] = mapped_column(Text)  # what brought them in, in plain words
    stop_reason: Mapped[str | None] = mapped_column(Text)
    stop_detail: Mapped[str | None] = mapped_column(Text)  # the tag or stage, in words

    __table_args__ = (
        Index(
            "uq_sequence_enrolments_active",
            "sequence_id",
            "contact_id",
            unique=True,
            postgresql_where=sql("status = 'active'"),
        ),
        Index(
            "ix_sequence_enrolments_due",
            "next_due_at",
            postgresql_where=sql("status = 'active'"),
        ),
        Index("ix_sequence_enrolments_contact", "contact_id"),
        Index("ix_sequence_enrolments_sequence", "sequence_id", "status", sql("enrolled_at DESC")),
        CheckConstraint(_in("status", EnrolmentStatus), name="status"),
        CheckConstraint(
            f"stop_reason IS NULL OR {_in('stop_reason', StopReason)}", name="stop_reason"
        ),
        CheckConstraint("current_step >= 0", name="current_step"),
    )


class SequenceStepRun(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "sequence_step_runs"

    enrolment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequence_enrolments.id", ondelete="CASCADE")
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sequences.id", ondelete="CASCADE"))
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    # A short code and the plain sentence for a skipped or failed step.
    reason_code: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    sent_as: Mapped[str | None] = mapped_column(Text)  # text or template
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("enrolment_id", "position"),
        Index("ix_sequence_step_runs_contact", "contact_id", sql("ran_at DESC")),
        Index("ix_sequence_step_runs_account_sent", "social_account_id", "ran_at"),
        CheckConstraint(_in("status", RunStatus), name="status"),
        CheckConstraint("sent_as IS NULL OR sent_as IN ('text', 'template')", name="sent_as"),
    )
