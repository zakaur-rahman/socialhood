"""Subscriptions, usage counters and AI usage events (§5.8)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    MAX = "max"


class SubscriptionStatus(StrEnum):
    FREE = "free"
    TRIALING = "trialing"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    EXPIRED = "expired"


class UsageMetric(StrEnum):
    AI_CREDITS = "ai_credits"
    SCHEDULED_POSTS = "scheduled_posts"


class AiFeature(StrEnum):
    """Credit feature keys (§1.7); the cost of each is in billing/plans.CREDIT_COSTS."""

    MESSAGE_ANALYSIS = "message_analysis"
    REPLY_SUGGESTION = "reply_suggestion"
    AUTO_REPLY = "auto_reply"
    CONVERSATION_SUMMARY = "conversation_summary"
    COMMENT_ANALYSIS = "comment_analysis"
    POST_SUMMARY = "post_summary"
    CAPTION_GENERATION = "caption_generation"
    KNOWLEDGE_TEST = "knowledge_test"
    AUTOMATION_AI_REPLY = "automation_ai_reply"
    AGENT_TURN = "agent_turn"  # each model call of an Ask Social Hood run (TR-AGT-02)


class AiOutcome(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class Subscription(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "subscriptions"

    plan: Mapped[str] = mapped_column(Text, server_default=text("'free'"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'free'"))
    dodo_customer_id: Mapped[str | None] = mapped_column(Text)
    dodo_subscription_id: Mapped[str | None] = mapped_column(Text, unique=True)
    dodo_product_id: Mapped[str | None] = mapped_column(Text)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    billing_anchor_day: Mapped[int] = mapped_column(SmallInteger)

    __table_args__ = (
        UniqueConstraint("workspace_id"),
        CheckConstraint(_in("plan", Plan), name="plan"),
        CheckConstraint(_in("status", SubscriptionStatus), name="status"),
        CheckConstraint("billing_anchor_day BETWEEN 1 AND 28", name="billing_anchor_day"),
    )


class UsageCounter(IdMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "usage_counters"

    metric: Mapped[str] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    used: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    limit: Mapped[int | None] = mapped_column(Integer)  # null = unlimited
    notified_80_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_100_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("workspace_id", "metric", "period_start"),
        CheckConstraint(_in("metric", UsageMetric), name="metric"),
    )


class AiUsageEvent(IdMixin, TimestampMixin, TenantScoped, Base):
    """One AI call (TR-AI-09): what it cost and how it went; feeds the global spend guard
    (TR-AI-13)."""

    __tablename__ = "ai_usage_events"

    feature: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    credits: Mapped[int] = mapped_column(SmallInteger)  # 0 when refunded
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    outcome: Mapped[str] = mapped_column(Text)
    ref_type: Mapped[str | None] = mapped_column(Text)  # e.g. "message"
    ref_id: Mapped[uuid.UUID | None] = mapped_column()

    __table_args__ = (
        Index("ix_ai_usage_events_recent", "workspace_id", text("created_at DESC")),
        CheckConstraint(_in("feature", AiFeature), name="feature"),
        CheckConstraint(_in("outcome", AiOutcome), name="outcome"),
    )
