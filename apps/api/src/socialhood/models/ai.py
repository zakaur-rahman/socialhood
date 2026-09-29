"""AI settings, message analyses, reply suggestions, knowledge, knowledge gaps and auto-reply
decisions (§5.5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    REAL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class Tone(StrEnum):
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    PLAYFUL = "playful"
    CONCISE = "concise"


class EmojiPolicy(StrEnum):
    NONE = "none"
    LIGHT = "light"
    LOTS = "lots"


TAKEOVER_MINUTES = (0, 30, 120, 1440)  # 0 = until resumed


class AiSettings(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "ai_settings"

    business_name: Mapped[str | None] = mapped_column(Text)
    business_description: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(Text, server_default=text("'friendly'"))
    emoji_policy: Mapped[str] = mapped_column(Text, server_default=text("'light'"))
    do_list: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    dont_list: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    escalation_phrases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    sign_off: Mapped[str | None] = mapped_column(Text)
    takeover_minutes: Mapped[int] = mapped_column(Integer, server_default=text("120"))

    __table_args__ = (
        UniqueConstraint("workspace_id"),
        CheckConstraint(_in("tone", Tone), name="tone"),
        CheckConstraint(_in("emoji_policy", EmojiPolicy), name="emoji_policy"),
        CheckConstraint(
            f"takeover_minutes IN ({', '.join(str(m) for m in TAKEOVER_MINUTES)})",
            name="takeover_minutes",
        ),
    )


# ---------------------------------------------------------------- P5 enums (§5.5)


class Intent(StrEnum):
    PRICING = "pricing"
    PRODUCT_INQUIRY = "product_inquiry"
    PURCHASE = "purchase"
    ORDER_STATUS = "order_status"
    SHIPPING = "shipping"
    SUPPORT = "support"
    COMPLAINT = "complaint"
    REFUND = "refund"
    FEEDBACK = "feedback"
    COLLABORATION = "collaboration"
    GREETING = "greeting"
    SPAM = "spam"
    OTHER = "other"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EscalationReason(StrEnum):
    REFUND = "refund"
    LEGAL = "legal"
    COMPLAINT = "complaint"
    NEGATIVE_SENTIMENT = "negative_sentiment"
    ABUSE = "abuse"
    ACCOUNT_OR_PAYMENT = "account_or_payment"
    HUMAN_REQUESTED = "human_requested"
    LOW_CONFIDENCE = "low_confidence"
    OUT_OF_KNOWLEDGE = "out_of_knowledge"
    WINDOW_CLOSED = "window_closed"
    POLICY_KEYWORD = "policy_keyword"
    OUTPUT_BLOCKED = "output_blocked"


class SkipReason(StrEnum):
    MODE_NOT_AUTO = "mode_not_auto"
    QUOTA_EXHAUSTED = "quota_exhausted"
    PAUSED = "paused"
    AUTOMATION_HANDLED = "automation_handled"
    RATE_CAPPED = "rate_capped"
    NOT_NEEDED = "not_needed"


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    EDITED_SENT = "edited_sent"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    FAILED = "failed"


class DecisionOutcome(StrEnum):
    AUTO_SENT = "auto_sent"
    ESCALATED = "escalated"
    SKIPPED = "skipped"


class KnowledgeType(StrEnum):
    FAQ = "faq"
    TEXT = "text"
    URL = "url"
    FILE = "file"


class KnowledgeStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class GapStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


EMBED_DIM = 768  # AI_EMBED_DIM must match (TR-AI-02); a new model means re-embedding every chunk


# ---------------------------------------------------------------- analysis (TR-AI-05, FR-AI-01)


class MessageAnalysis(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "message_analyses"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    intent: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(Text)
    sentiment_score: Mapped[float] = mapped_column(REAL)
    priority: Mapped[str] = mapped_column(Text)
    lead_score: Mapped[int] = mapped_column(SmallInteger)
    language: Mapped[str] = mapped_column(Text)  # BCP-47: "en", "hi", "hi-Latn"
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    needs_reply: Mapped[bool] = mapped_column(Boolean)
    needs_human: Mapped[bool] = mapped_column(Boolean)
    needs_human_reason: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    # FR-AI-04: a member's correction, exported into the evaluation set (TR-AI-10).
    corrected_intent: Mapped[str | None] = mapped_column(Text)
    corrected_sentiment: Mapped[str | None] = mapped_column(Text)
    corrected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_message_analyses_conversation", "conversation_id", text("created_at DESC")),
        CheckConstraint(_in("intent", Intent), name="intent"),
        CheckConstraint(_in("sentiment", Sentiment), name="sentiment"),
        CheckConstraint(_in("priority", Priority), name="priority"),
        CheckConstraint(
            f"corrected_intent IS NULL OR {_in('corrected_intent', Intent)}",
            name="corrected_intent",
        ),
        CheckConstraint(
            f"corrected_sentiment IS NULL OR {_in('corrected_sentiment', Sentiment)}",
            name="corrected_sentiment",
        ),
        CheckConstraint(
            f"needs_human_reason IS NULL OR {_in('needs_human_reason', EscalationReason)}",
            name="needs_human_reason",
        ),
        CheckConstraint("sentiment_score BETWEEN -1 AND 1", name="sentiment_score"),
        CheckConstraint("lead_score BETWEEN 0 AND 100", name="lead_score"),
        CheckConstraint("cardinality(topics) <= 3", name="topics"),
    )


# ---------------------------------------------------------------- suggestions (TR-AI-06, FR-SUG-02)


class ReplySuggestion(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "reply_suggestions"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(  # the inbound message answered
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    can_answer: Mapped[bool] = mapped_column(Boolean)
    reply_text: Mapped[str | None] = mapped_column(Text)
    missing_info: Mapped[str | None] = mapped_column(Text)  # for the business, not the customer
    missing_topic: Mapped[str | None] = mapped_column(Text)  # 2-4 words, groups gaps (TR-AI-12)
    model_confidence: Mapped[float | None] = mapped_column(REAL)
    top_similarity: Mapped[float | None] = mapped_column(REAL)
    used_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid()), server_default=text("'{}'")
    )
    regeneration_index: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    sent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    edit_distance: Mapped[float | None] = mapped_column(REAL)  # normalised Levenshtein, 0-1
    # An automation's AI reply (T5.8) drafts through the same path; it is never pending.
    automation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("automation_runs.id", ondelete="SET NULL")
    )
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_reply_suggestions_conversation", "conversation_id", text("created_at DESC")),
        Index(
            "uq_reply_suggestions_pending",
            "conversation_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint(_in("status", SuggestionStatus), name="status"),
        CheckConstraint("regeneration_index BETWEEN 0 AND 5", name="regeneration_index"),
    )


# ---------------------------------------------------------------- knowledge (TR-AI-08, FR-KB)


class KnowledgeSource(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "knowledge_sources"

    type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)  # an FAQ's title is its question
    question: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)  # the FAQ answer or the note
    url: Mapped[str | None] = mapped_column(Text)
    file_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    error: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))  # +1 on each edit
    char_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    chunk_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_knowledge_sources_workspace", "workspace_id", text("created_at DESC")),
        CheckConstraint(_in("type", KnowledgeType), name="type"),
        CheckConstraint(_in("status", KnowledgeStatus), name="status"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="title_length"),
        CheckConstraint("body IS NULL OR char_length(body) <= 20000", name="body_length"),
    )


class KnowledgeChunk(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "knowledge_chunks"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True
    )
    source_version: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)  # "[{source title}] " + at most 1,200 characters
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))  # L2-normalised

    __table_args__ = (
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class KnowledgeGap(IdMixin, TimestampMixin, TenantScoped, Base):
    """A question the AI couldn't answer from knowledge (FR-KB-06, TR-AI-12)."""

    __tablename__ = "knowledge_gaps"

    topic: Mapped[str] = mapped_column(Text)  # the first phrasing seen
    topic_normalized: Mapped[str] = mapped_column(Text)  # lowercase, no punctuation
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    occurrences: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    example_message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid()), server_default=text("'{}'")
    )  # at most 5, newest first
    resolved_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="SET NULL")
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_knowledge_gaps_open_topic",
            "workspace_id",
            "topic_normalized",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index(
            "ix_knowledge_gaps_topic_trgm",
            "topic_normalized",
            postgresql_using="gin",
            postgresql_ops={"topic_normalized": "gin_trgm_ops"},
        ),
        Index("ix_knowledge_gaps_list", "workspace_id", "status", text("occurrences DESC")),
        CheckConstraint(_in("status", GapStatus), name="status"),
        CheckConstraint("cardinality(example_message_ids) <= 5", name="examples"),
    )


# ---------------------------------------------------------------- auto-reply decisions (TR-AI-07)


class AiDecision(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "ai_decisions"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(  # the inbound message decided on
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reply_suggestions.id", ondelete="SET NULL")
    )
    sent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    outcome: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)  # the first failed check's code
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # [{n, name, passed, value}]
    user_feedback: Mapped[str | None] = mapped_column(Text)  # "bad": should not have sent

    __table_args__ = (
        Index("ix_ai_decisions_conversation", "conversation_id", text("created_at DESC")),
        CheckConstraint(_in("outcome", DecisionOutcome), name="outcome"),
    )
