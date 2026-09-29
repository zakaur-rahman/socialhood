"""Comment intelligence and post analytics (§5.6): comment analyses (TR-AI-11, FR-CMT-02), post
metric snapshots and account daily metrics (FR-ANL-01), read by services/analytics (TR-AGT-05).

The P6 contract. The metric names below are the keys of the ``metrics`` JSON columns: the
snapshot jobs write them and the analytics service reads them, so both use these enums.
"""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    REAL,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.ai import Intent, Sentiment
from socialhood.models.identity import _in


class SnapshotWindow(StrEnum):
    """A post's age when a snapshot is taken (FR-ANL-01)."""

    H1 = "1h"
    H6 = "6h"
    H24 = "24h"
    H72 = "72h"
    D7 = "7d"
    D30 = "30d"


# How long after publishing each window is due.
WINDOW_AGES: dict[SnapshotWindow, dt.timedelta] = {
    SnapshotWindow.H1: dt.timedelta(hours=1),
    SnapshotWindow.H6: dt.timedelta(hours=6),
    SnapshotWindow.H24: dt.timedelta(hours=24),
    SnapshotWindow.H72: dt.timedelta(hours=72),
    SnapshotWindow.D7: dt.timedelta(days=7),
    SnapshotWindow.D30: dt.timedelta(days=30),
}

# Instagram's insights lag up to 48 h, so the 1 h and 6 h snapshots hold only the live counts
# (likes, comments); insights start at 24 h, and the 72 h run re-reads the 24 h values and marks
# both final (FR-ANL-01).
LIVE_COUNT_WINDOWS = frozenset({SnapshotWindow.H1, SnapshotWindow.H6})


class PostMetric(StrEnum):
    """Keys of ``post_metric_snapshots.metrics`` (metric name -> integer)."""

    LIKES = "likes"
    COMMENTS = "comments"
    REACH = "reach"
    VIEWS = "views"
    SHARES = "shares"
    SAVES = "saves"  # Instagram's "saved"
    TOTAL_INTERACTIONS = "total_interactions"
    PROFILE_VISITS = "profile_visits"
    FOLLOWS = "follows"


class AccountMetric(StrEnum):
    """Keys of ``account_daily_metrics.metrics``: that day's account insights ({} without the
    insights scope)."""

    REACH = "reach"
    VIEWS = "views"
    ACCOUNTS_ENGAGED = "accounts_engaged"
    TOTAL_INTERACTIONS = "total_interactions"
    FOLLOWS = "follows"
    UNFOLLOWS = "unfollows"
    PROFILE_LINKS_TAPS = "profile_links_taps"


class CommentAnalysis(IdMixin, TimestampMixin, TenantScoped, Base):
    """One comment's reading by analyze_comments (TR-AI-11): 50 comments per model call.

    ``media_item_id`` repeats the comment's post so per-post figures (sentiment split, the 50 most
    frequent topics for summarize_post) read this table alone.
    """

    __tablename__ = "comment_analyses"

    comment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), unique=True
    )
    media_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE")
    )
    sentiment: Mapped[str] = mapped_column(Text)
    sentiment_score: Mapped[float] = mapped_column(REAL)
    intent: Mapped[str] = mapped_column(Text)
    is_spam: Mapped[bool] = mapped_column(Boolean)
    topic: Mapped[str | None] = mapped_column(Text)  # at most 3 words, lowercase; None: no topic
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        Index("ix_comment_analyses_media_sentiment", "media_item_id", "sentiment", "is_spam"),
        Index("ix_comment_analyses_media_topic", "media_item_id", "topic"),
        CheckConstraint(_in("sentiment", Sentiment), name="sentiment"),
        CheckConstraint(_in("intent", Intent), name="intent"),
        CheckConstraint("sentiment_score BETWEEN -1 AND 1", name="sentiment_score"),
        CheckConstraint(
            "topic IS NULL OR char_length(topic) BETWEEN 1 AND 60", name="topic_length"
        ),
    )


class PostMetricSnapshot(IdMixin, TimestampMixin, TenantScoped, Base):
    """A post's metrics at one age (FR-ANL-01), taken once per window by snapshot_post_metrics.

    ``window`` is a reserved word in SQL: quote it ("window") in raw SQL.
    """

    __tablename__ = "post_metric_snapshots"

    media_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE")
    )
    window: Mapped[str] = mapped_column(Text)
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    # PostMetric name -> integer. 1 h and 6 h hold live counts (likes, comments) only.
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # False until the 72 h run re-reads lagging insight values.
    insights_final: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("media_item_id", "window"),
        CheckConstraint(_in('"window"', SnapshotWindow), name="window"),
    )


class AccountDailyMetric(IdMixin, TimestampMixin, TenantScoped, Base):
    """One row per account per day (FR-ANL-01), written by snapshot_account_daily. Instagram keeps
    account insights for 90 days only, so this table is the long-term history."""

    __tablename__ = "account_daily_metrics"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    date: Mapped[dt.date] = mapped_column(Date)  # in the workspace time zone
    # From the account fields: the only reliable follower history.
    followers_count: Mapped[int | None] = mapped_column(Integer)
    # AccountMetric name -> integer; {} without the insights scope.
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    captured_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("social_account_id", "date"),)
