"""Contacts as records a business can work with (GR-02): tags, custom fields and consent.

A contact is still one channel identity (``contacts``: an Instagram IGSID or a WhatsApp wa_id;
PD-10). These tables add:

- ``tags`` and ``contact_tags``: a workspace's labels and which contacts carry them;
- ``contact_field_definitions``: the custom fields a workspace defines (key, label, type). The
  values live on ``contacts.fields`` (JSONB, keyed by field key), validated against these;
- ``contact_consents``: an append-only history of marketing consent per channel. The latest row
  for (contact, channel, purpose) is the current state. Each row says where it came from (a
  platform opt-in, a flow question, a STOP reply, a member) with its evidence, so a broadcast
  (GR-23) can prove it was allowed.
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

from socialhood.db.base import Base, IdMixin, TimestampMixin
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
