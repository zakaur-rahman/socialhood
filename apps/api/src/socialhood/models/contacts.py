"""Contacts as records a business can work with (GR-02): tags, custom fields and consent.

A contact is still one channel identity (``contacts``: an Instagram IGSID or a WhatsApp wa_id;
PD-10). These tables add:

- ``tags`` and ``contact_tags``: a workspace's labels and which contacts carry them;
- ``contact_field_definitions``: the custom fields a workspace defines (key, label, type). The
  values live on ``contacts.fields`` (JSONB, keyed by field key), validated against these;
- ``contact_consents``: an append-only history of marketing consent per channel. The latest row
  for (contact, channel, purpose) is the current state. Each row says where it came from (a
  platform opt-in, a flow question, a STOP reply, a member) with its evidence, so a broadcast
  (GR-23) can prove it was allowed;
- ``contact_segments`` (GR-17): a named, saved contact filter. It stores the filter, not the
  contacts, so a segment is always the people who match it now;
- ``lead_stage_changes`` (GR-18): the history of a contact's lead stage (the stage itself is on
  ``contacts``): from, to, who or what moved it, and why.
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
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, CreatedAtMixin, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class FieldType(StrEnum):
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    DATE = "date"
    CHOICE = "choice"


class ConsentChannel(StrEnum):
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class ConsentPurpose(StrEnum):
    MARKETING = "marketing"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"


class ConsentSource(StrEnum):
    PLATFORM_OPTIN = "platform_optin"  # Instagram messaging_optins (GR-01)
    FLOW = "flow"  # an automation's consent question (GR-14)
    STOP_REPLY = "stop_reply"  # a STOP or unsubscribe reply (GR-23)
    MEMBER = "member"  # recorded by a member, with a note
    IMPORT = "import"
    WIDGET = "widget"  # the website chat widget's consent box (GR-28)


class LeadStage(StrEnum):
    """Where a contact is as a lead (GR-18). The first three are open; won and lost are closed."""

    NEW = "new"
    QUALIFIED = "qualified"
    FOLLOW_UP = "follow_up"
    WON = "won"
    LOST = "lost"


class NameSource(StrEnum):
    """Who chose a contact's saved name (C-135): the platform's profile name, or a member. A
    name a member saved is never replaced by the profile name a platform sends later."""

    PLATFORM = "platform"
    TEAM = "team"


class StageActor(StrEnum):
    """Who moved a lead: a member, an automation's step, a rule of the product (lead score,
    intent, a captured email, going cold) or the system."""

    MEMBER = "member"
    AUTOMATION = "automation"
    RULE = "rule"
    SYSTEM = "system"


class Tag(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(Text)
    # An index into the identity palette (lib/ui/identity.ts), so tags never wear status colours.
    color: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))

    __table_args__ = (
        Index("uq_tags_workspace_name", "workspace_id", sql("lower(name)"), unique=True),
        CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="name_length"),
        CheckConstraint("color BETWEEN 0 AND 15", name="color"),
    )


class ContactTag(IdMixin, TimestampMixin, TenantScoped, Base):
    """An id like every table, so an account's purge (services/account_deletion) deletes these
    in batches with the contacts they belong to."""

    __tablename__ = "contact_tags"

    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"))
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("contact_id", "tag_id"),
        Index("ix_contact_tags_tag", "tag_id"),
    )


class ContactFieldDefinition(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "contact_field_definitions"

    key: Mapped[str] = mapped_column(Text)  # lower snake case; a message variable later (GR-14)
    label: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text, server_default=sql("'text'"))
    options: Mapped[list[str]] = mapped_column(JSONB, server_default=sql("'[]'::jsonb"))
    position: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))

    __table_args__ = (
        UniqueConstraint("workspace_id", "key"),
        CheckConstraint("key ~ '^[a-z][a-z0-9_]{0,39}$'", name="key_format"),
        CheckConstraint("char_length(label) BETWEEN 1 AND 60", name="label_length"),
        CheckConstraint(_in("type", FieldType), name="type"),
    )


class ContactConsent(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "contact_consents"

    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text, server_default=sql("'marketing'"))
    status: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    # What proves it: {"webhook_event_id": …} / {"message_id": …} / {"note": …, "user_id": …}.
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql("'{}'::jsonb"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_contact_consents_current",
            "contact_id",
            "channel",
            "purpose",
            sql("occurred_at DESC"),
        ),
        CheckConstraint(_in("channel", ConsentChannel), name="channel"),
        CheckConstraint(_in("purpose", ConsentPurpose), name="purpose"),
        CheckConstraint(_in("status", ConsentStatus), name="status"),
        CheckConstraint(_in("source", ConsentSource), name="source"),
    )


class ContactSegment(IdMixin, TimestampMixin, TenantScoped, Base):
    """A saved filter on the contacts page (and, from GR-23, a broadcast's audience). ``filter``
    holds the same keys as the list's query (schemas.contacts.ContactFilterSpec)."""

    __tablename__ = "contact_segments"

    name: Mapped[str] = mapped_column(Text)
    filter: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql("'{}'::jsonb"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index(
            "uq_contact_segments_workspace_name", "workspace_id", sql("lower(name)"), unique=True
        ),
        CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="name_length"),
    )


class LeadStageChange(IdMixin, CreatedAtMixin, TenantScoped, Base):
    """One move of a contact's lead stage; append-only. ``rule`` names the rule behind an
    automatic move (``lead_score``, ``intent``, ``email_captured``, ``gone_cold``) or the
    automation's id for ``actor_kind = automation``; ``reason`` is a plain sentence."""

    __tablename__ = "lead_stage_changes"

    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    from_stage: Mapped[str] = mapped_column(Text)
    to_stage: Mapped[str] = mapped_column(Text)
    actor_kind: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    rule: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_lead_stage_changes_contact", "contact_id", sql("created_at DESC")),
        CheckConstraint(_in("from_stage", LeadStage), name="from_stage"),
        CheckConstraint(_in("to_stage", LeadStage), name="to_stage"),
        CheckConstraint(_in("actor_kind", StageActor), name="actor_kind"),
        CheckConstraint("reason IS NULL OR char_length(reason) <= 300", name="reason_length"),
    )
