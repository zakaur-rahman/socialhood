"""Keyword automations (§5.6; FR-AUT-01…20) and the comments they answer (§5.6 comments; stored
from P4, analysed from P6)."""

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


class AutomationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class Trigger(StrEnum):
    DM_KEYWORD = "dm_keyword"
    COMMENT_KEYWORD = "comment_keyword"
    COMMENT_ANY = "comment_any"


class MatchMode(StrEnum):
    WORD = "word"
    EXACT = "exact"
    CONTAINS = "contains"


class AutomationAction(StrEnum):
    SEND_MESSAGE = "send_message"
    AI_REPLY = "ai_reply"


class SurgeOrder(StrEnum):
    OLDEST_FIRST = "oldest_first"
    NEWEST_FIRST = "newest_first"
    PUBLIC_ONLY = "public_only"


class PostScope(StrEnum):
    ALL = "all"
    SELECTED = "selected"
    NEXT_POST = "next_post"


class RunResult(StrEnum):
    QUEUED = "queued"  # waiting in the account's private-reply queue (TR-JOB-07)
    SENT = "sent"
    PARTIAL = "partial"  # one of the private and public replies failed
    FAILED = "failed"
    SKIPPED_COOLDOWN = "skipped_cooldown"
    SKIPPED_EXPIRED = "skipped_expired"  # the comment passed Instagram's 7-day limit
    ESCALATED = "escalated"  # an AI reply could not answer from knowledge (P5)


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


class Automation(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "automations"

    social_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text, server_default=sql("'Untitled automation'"))
    status: Mapped[str] = mapped_column(Text, server_default=sql("'draft'"))
    trigger: Mapped[str | None] = mapped_column(Text)
    match_mode: Mapped[str] = mapped_column(Text, server_default=sql("'word'"))
    action: Mapped[str | None] = mapped_column(Text)
    message_text: Mapped[str | None] = mapped_column(Text)
    ai_instructions: Mapped[str | None] = mapped_column(Text)
    public_reply_texts: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'"))
    message_buttons: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sql("'[]'::jsonb")
    )
    message_media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    template_key: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    surge_order: Mapped[str] = mapped_column(Text, server_default=sql("'oldest_first'"))
    post_scope: Mapped[str] = mapped_column(Text, server_default=sql("'all'"))
    cooldown_hours: Mapped[int] = mapped_column(SmallInteger, server_default=sql("24"))
    priority: Mapped[int] = mapped_column(Integer, server_default=sql("100"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index(
            "ix_automations_runtime",
            "social_account_id",
            "trigger",
            "status",
            "priority",
            "created_at",
        ),
        CheckConstraint(_in("status", AutomationStatus), name="status"),
        CheckConstraint(f"trigger IS NULL OR {_in('trigger', Trigger)}", name="trigger"),
        CheckConstraint(_in("match_mode", MatchMode), name="match_mode"),
        CheckConstraint(f"action IS NULL OR {_in('action', AutomationAction)}", name="action"),
        CheckConstraint(_in("surge_order", SurgeOrder), name="surge_order"),
        CheckConstraint(_in("post_scope", PostScope), name="post_scope"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint("cooldown_hours BETWEEN 0 AND 72", name="cooldown_hours"),
        CheckConstraint("cardinality(public_reply_texts) <= 5", name="public_reply_texts"),
        CheckConstraint("jsonb_array_length(message_buttons) <= 3", name="message_buttons"),
        CheckConstraint(
            "ai_instructions IS NULL OR char_length(ai_instructions) <= 2000",
            name="ai_instructions_length",
        ),
        # T4.1 done-when: an incomplete automation cannot be stored as active.
        CheckConstraint(
            "status <> 'active' OR (social_account_id IS NOT NULL AND trigger IS NOT NULL"
            " AND action IS NOT NULL)",
            name="complete_when_active",
        ),
    )


class AutomationKeyword(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "automation_keywords"

    automation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(Text)  # as typed
    keyword_normalized: Mapped[str] = mapped_column(Text)  # NFKC, casefold, collapsed spaces

    __table_args__ = (
        UniqueConstraint("automation_id", "keyword_normalized"),
        CheckConstraint("char_length(keyword) BETWEEN 1 AND 100", name="keyword_length"),
    )


class AutomationPost(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "automation_posts"

    automation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE")
    )
    media_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE")
    )
    # scheduled_posts arrives in P7; its FK is added then. media_item_id is filled when the
    # scheduled post publishes (FR-AUT-18).
    scheduled_post_id: Mapped[uuid.UUID | None] = mapped_column()

    __table_args__ = (
        Index(
            "uq_automation_posts_media_item",
            "automation_id",
            "media_item_id",
            unique=True,
            postgresql_where=sql("media_item_id IS NOT NULL"),
        ),
        Index(
            "uq_automation_posts_scheduled_post",
            "automation_id",
            "scheduled_post_id",
            unique=True,
            postgresql_where=sql("scheduled_post_id IS NOT NULL"),
        ),
        CheckConstraint(
            "media_item_id IS NOT NULL OR scheduled_post_id IS NOT NULL", name="has_target"
        ),
    )


class Comment(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "comments"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    media_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE")
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    platform_comment_id: Mapped[str] = mapped_column(Text)
    parent_platform_comment_id: Mapped[str | None] = mapped_column(Text)
    author_platform_user_id: Mapped[str | None] = mapped_column(Text)
    author_username: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    like_count: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    hidden: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    analysis_status: Mapped[str] = mapped_column(Text, server_default=sql("'pending'"))
    our_reply_platform_id: Mapped[str | None] = mapped_column(Text)
    our_reply_text: Mapped[str | None] = mapped_column(Text)
    our_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    private_reply_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("social_account_id", "platform_comment_id"),
        Index("ix_comments_media_commented", "media_item_id", sql("commented_at DESC")),
        Index(
            "ix_comments_pending_analysis",
            "social_account_id",
            "created_at",
            postgresql_where=sql("analysis_status = 'pending'"),
        ),
        CheckConstraint(_in("analysis_status", AnalysisStatus), name="analysis_status"),
    )


class AutomationRun(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "automation_runs"

    automation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE")
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    trigger_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    trigger_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE")
    )
    matched_keyword: Mapped[str] = mapped_column(Text)  # "" for any-comment triggers
    result: Mapped[str] = mapped_column(Text)
    private_reply_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    public_reply_platform_id: Mapped[str | None] = mapped_column(Text)
    public_reply_variant: Mapped[int | None] = mapped_column(SmallInteger)
    contact_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "uq_automation_runs_message",
            "automation_id",
            "trigger_message_id",
            unique=True,
            postgresql_where=sql("trigger_message_id IS NOT NULL"),
        ),
        Index(
            "uq_automation_runs_comment",
            "automation_id",
            "trigger_comment_id",
            unique=True,
            postgresql_where=sql("trigger_comment_id IS NOT NULL"),
        ),
        Index("ix_automation_runs_cooldown", "automation_id", "contact_id", sql("created_at DESC")),
        Index("ix_automation_runs_recent", "automation_id", sql("created_at DESC")),
        Index(
            "ix_automation_runs_queued",
            "automation_id",
            "created_at",
            postgresql_where=sql("result = 'queued'"),
        ),
        CheckConstraint(_in("result", RunResult), name="result"),
        CheckConstraint(
            "(trigger_message_id IS NULL) <> (trigger_comment_id IS NULL)", name="one_trigger"
        ),
    )
