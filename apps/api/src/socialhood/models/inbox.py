"""Contacts, conversations, messages and scheduled messages (§5.4, §5.5 enums)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.connections import AiMode
from socialhood.models.identity import _in


class AwareDateTime(TypeDecorator[datetime]):
    """timestamptz that always reads back timezone-aware. Postgres 'infinity' (an AI pause "until
    resumed", §5.4) comes back from asyncpg as a naive datetime.max, which cannot be compared
    with aware datetimes."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class ConversationStatus(StrEnum):
    OPEN = "open"
    ARCHIVED = "archived"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    SYSTEM = "system"


class MessageSource(StrEnum):
    CUSTOMER = "customer"
    HUMAN = "human"
    AI_AUTO = "ai_auto"
    AUTOMATION = "automation"
    NATIVE_APP = "native_app"  # sent from the Instagram app (FR-INB-09)
    SYSTEM = "system"


class MessageKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    STICKER = "sticker"
    STORY_MENTION = "story_mention"
    STORY_REPLY = "story_reply"
    SHARE = "share"
    TEMPLATE = "template"
    LOCATION = "location"
    UNSUPPORTED = "unsupported"
    SYSTEM = "system"


class MessageStatus(StrEnum):
    RECEIVED = "received"  # inbound
    QUEUED = "queued"  # outbound, in order of the lifecycle
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ScheduledStatus(StrEnum):
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELED = "canceled"
    EXPIRED = "expired"


class Contact(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "contacts"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    platform_user_id: Mapped[str] = mapped_column(Text)  # IGSID or WhatsApp wa_id
    username: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    profile_picture_url: Mapped[str | None] = mapped_column(Text)
    profile_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("social_account_id", "platform_user_id"),
        Index(
            "ix_contacts_search_trgm",
            sql("(coalesce(display_name, '') || ' ' || coalesce(username, '')) gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )


class Conversation(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "conversations"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'open'"))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_preview: Mapped[str | None] = mapped_column(Text)
    last_message_direction: Mapped[str | None] = mapped_column(Text)
    last_message_source: Mapped[str | None] = mapped_column(Text)
    last_message_kind: Mapped[str | None] = mapped_column(Text)
    unread_count: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    awaiting_reply: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    needs_human: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    needs_human_reason: Mapped[str | None] = mapped_column(Text)
    ai_mode_override: Mapped[str | None] = mapped_column(Text)
    ai_paused_until: Mapped[datetime | None] = mapped_column(AwareDateTime())
    last_intent: Mapped[str | None] = mapped_column(Text)
    last_sentiment: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text)
    lead_score: Mapped[int | None] = mapped_column(SmallInteger)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_next_step: Mapped[str | None] = mapped_column(Text)
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    messages_since_summary: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    platform_conversation_id: Mapped[str | None] = mapped_column(Text)
    window_reminder_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("social_account_id", "contact_id"),
        Index(
            "ix_conversations_list",
            "workspace_id",
            "status",
            sql("last_message_at DESC"),
            sql("id DESC"),
        ),
        Index(
            "ix_conversations_awaiting_reply",
            "workspace_id",
            sql("last_message_at DESC"),
            postgresql_where=sql("awaiting_reply"),
        ),
        Index(
            "ix_conversations_needs_human",
            "workspace_id",
            sql("last_message_at DESC"),
            postgresql_where=sql("needs_human"),
        ),
        Index(
            "ix_conversations_unread",
            "workspace_id",
            sql("last_message_at DESC"),
            postgresql_where=sql("unread_count > 0"),
        ),
        Index(
            "ix_conversations_leads",
            "workspace_id",
            sql("last_message_at DESC"),
            postgresql_where=sql("lead_score >= 60"),
        ),
        CheckConstraint(_in("status", ConversationStatus), name="status"),
        CheckConstraint(
            f"ai_mode_override IS NULL OR {_in('ai_mode_override', AiMode)}",
            name="ai_mode_override",
        ),
        CheckConstraint(
            "last_message_preview IS NULL OR char_length(last_message_preview) <= 200",
            name="preview_length",
        ),
    )


class Message(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    direction: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default=sql("'text'"))
    text: Mapped[str | None] = mapped_column(Text)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The customer unsent it: text and attachments are cleared, the bubble says so (Q-021).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sql("'[]'::jsonb")
    )
    template: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    platform_message_id: Mapped[str | None] = mapped_column(Text)
    client_id: Mapped[uuid.UUID | None] = mapped_column()
    status: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    human_agent_tag: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    sent_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # The suggestions table arrives in P5; its FK is added then.
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column()
    automation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("automation_runs.id", ondelete="SET NULL", use_alter=True)
    )
    scheduled_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scheduled_messages.id", ondelete="SET NULL", use_alter=True)
    )
    automation_handled: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    reply_to_platform_message_id: Mapped[str | None] = mapped_column(Text)
    reactions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sql("'[]'::jsonb")
    )
    search_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', coalesce(text, ''))", persisted=True),
    )

    __table_args__ = (
        UniqueConstraint("social_account_id", "platform_message_id"),
        UniqueConstraint("conversation_id", "client_id"),
        Index("ix_messages_thread", "conversation_id", sql("occurred_at DESC"), sql("id DESC")),
        Index(
            "ix_messages_in_flight",
            "status",
            "updated_at",
            postgresql_where=sql("status IN ('queued', 'sending')"),
        ),
        Index("ix_messages_search_tsv", "search_tsv", postgresql_using="gin"),
        CheckConstraint(_in("direction", Direction), name="direction"),
        CheckConstraint(_in("source", MessageSource), name="source"),
        CheckConstraint(_in("kind", MessageKind), name="kind"),
        CheckConstraint(f"status IS NULL OR {_in('status', MessageStatus)}", name="status"),
    )


class ScheduledMessage(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "scheduled_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    attachment_asset_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), server_default=sql("'{}'")
    )
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default=sql("'scheduled'"))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index(
            "ix_scheduled_messages_due",
            "send_at",
            postgresql_where=sql("status = 'scheduled'"),
        ),
        CheckConstraint(_in("status", ScheduledStatus), name="status"),
        CheckConstraint("char_length(text) BETWEEN 1 AND 2000", name="text_length"),
    )
