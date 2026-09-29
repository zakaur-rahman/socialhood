"""Comment sentiment distribution (T6.5; TR-AGT-05; agent-architecture §6
``sentiment_distribution(scope)``), from comment_analyses (TR-AI-11).

For one post, or for the comments made in a date range (the workspace's calendar days,
optionally on one account's posts). Deleted comments are left out. ``analysed`` counts comments
with an analysis; the rest are reported as not analysed, never guessed. Spam is counted apart:
positive + neutral + negative are analysed comments that are not spam, and the percentages are
shares of that sum (C-039).

``comment_topics`` (agent-architecture §6 ``comment_topics(scope, sentiment, n)``, TA.4) counts
the same scope's analysed, non-spam comments by their TR-AI-11 topic label, with example comments.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import Sentiment
from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import AnalysisStatus, Comment
from socialhood.schemas.analytics import SentimentDistribution
from socialhood.services.analytics.common import View, date_range, load_account, load_post


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


async def _scope(
    session: AsyncSession,
    view: View,
    *,
    post_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
    since: date | None,
    until: date | None,
) -> tuple[list[ColumnElement[bool]], uuid.UUID | None, date | None, date | None]:
    """The comments a distribution or topic count covers: one post (the range ignored), or the
    comments made in a date range, optionally on one account's posts; deleted ones left out."""
    scope: list[ColumnElement[bool]] = [Comment.deleted_at.is_(None)]
    if post_id is not None:
        post = await load_post(session, post_id)
        if account_id is not None:
            await load_account(session, account_id)
        scope.append(Comment.media_item_id == post.id)
        return scope, post.social_account_id, None, None
    span = date_range(view.timezone, view.now, since, until)
    scope += [Comment.commented_at >= span.start, Comment.commented_at < span.end]
    if account_id is not None:
        await load_account(session, account_id)
        scope.append(Comment.social_account_id == account_id)
    return scope, account_id, span.since, span.until


@dataclass(frozen=True)
class TopicExample:
    comment_id: uuid.UUID
    text: str
    commented_at: datetime


@dataclass(frozen=True)
class TopicCount:
    label: str  # TR-AI-11's topic label (at most 3 words, lowercase)
    count: int
    positive: int
    neutral: int
    negative: int
    examples: list[TopicExample] = field(default_factory=list)  # newest first


@dataclass(frozen=True)
class CommentTopics:
    """Top comment topics in a scope (agent-architecture §6 ``comment_topics``): analysed comments
    that are not spam, with the sentiment filter when given. ``analysed`` counts them, with or
    without a topic; ``total`` counts every comment in scope and ``pending`` / ``skipped`` those
    not analysed, which are reported, never guessed."""

    since: date | None
    until: date | None
    topics: list[TopicCount]
    topic_count: int  # distinct topics
    analysed: int
    total: int
    pending: int
    skipped: int


async def comment_topics(
    session: AsyncSession,
    view: View,
    *,
    post_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    since: date | None = None,
    until: date | None = None,
    sentiment: Sentiment | None = None,
    n: int = 5,
    examples: int = 3,
) -> CommentTopics:
    """The ``n`` most frequent topics with counts per sentiment and up to ``examples`` example
    comments each (Ask Social Hood's comment_topics, TA.4). Ties go to the label, A to Z."""
    scope, _, since, until = await _scope(
        session, view, post_id=post_id, account_id=account_id, since=since, until=until
    )
    counted = [*scope, CommentAnalysis.is_spam.is_(False)]
    if sentiment is not None:
        counted.append(CommentAnalysis.sentiment == sentiment.value)
    base = (
        select(Comment.id)
        .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
        .where(*counted)
    )
    analysed = await session.scalar(select(func.count()).select_from(base.subquery()))
    by = (
        select(
            CommentAnalysis.topic,
            func.count(),
            func.count().filter(CommentAnalysis.sentiment == Sentiment.POSITIVE.value),
            func.count().filter(CommentAnalysis.sentiment == Sentiment.NEUTRAL.value),
            func.count().filter(CommentAnalysis.sentiment == Sentiment.NEGATIVE.value),
        )
        .select_from(Comment)
        .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
        .where(*counted, CommentAnalysis.topic.is_not(None))
        .group_by(CommentAnalysis.topic)
    )
    topic_count = await session.scalar(select(func.count()).select_from(by.subquery()))
    rows = (
        await session.execute(by.order_by(func.count().desc(), CommentAnalysis.topic).limit(n))
    ).all()
    labels = [str(row[0]) for row in rows]
    found: dict[str, list[TopicExample]] = {label: [] for label in labels}
    if labels and examples > 0:
        ranked = (
            select(
                Comment.id,
                Comment.text,
                Comment.commented_at,
                CommentAnalysis.topic,
                func.row_number()
                .over(
                    partition_by=CommentAnalysis.topic,
                    order_by=(Comment.commented_at.desc(), Comment.id.desc()),
                )
                .label("rank"),
            )
            .join(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
            .where(*counted, CommentAnalysis.topic.in_(labels))
            .subquery()
        )
        picked = await session.execute(
            select(ranked.c.id, ranked.c.text, ranked.c.commented_at, ranked.c.topic)
            .where(ranked.c.rank <= examples)
            .order_by(ranked.c.topic, ranked.c.rank)
        )
        for comment_id, text, at, topic in picked.all():
            found[topic].append(TopicExample(comment_id, text, at))
    status = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(Comment.analysis_status == AnalysisStatus.PENDING),
                func.count().filter(Comment.analysis_status == AnalysisStatus.SKIPPED),
            )
            .select_from(Comment)
            .where(*scope)
        )
    ).one()
    return CommentTopics(
        since=since,
        until=until,
        topics=[
            TopicCount(
                label=str(label),
                count=int(count),
                positive=int(positive),
                neutral=int(neutral),
                negative=int(negative),
                examples=found[str(label)],
            )
            for label, count, positive, neutral, negative in rows
        ],
        topic_count=int(topic_count or 0),
        analysed=int(analysed or 0),
        total=int(status[0] or 0),
        pending=int(status[1] or 0),
        skipped=int(status[2] or 0),
    )


async def sentiment_distribution(
    session: AsyncSession,
    view: View,
    *,
    post_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    since: date | None = None,
    until: date | None = None,
) -> SentimentDistribution:
    """Counts and shares of positive, neutral and negative comments, spam apart, with how many
    were analysed of how many there are. With ``post_id`` the range is ignored."""
    scope: list[ColumnElement[bool]] = [Comment.deleted_at.is_(None)]
    if post_id is not None:
        post = await load_post(session, post_id)
        if account_id is not None:
            await load_account(session, account_id)
        account_id = post.social_account_id
        since = until = None
        scope.append(Comment.media_item_id == post.id)
    else:
        span = date_range(view.timezone, view.now, since, until)
        since, until = span.since, span.until
        scope += [Comment.commented_at >= span.start, Comment.commented_at < span.end]
        if account_id is not None:
            await load_account(session, account_id)
            scope.append(Comment.social_account_id == account_id)

    analysed = func.count(CommentAnalysis.id)

    def clean(sentiment: Sentiment) -> ColumnElement[int]:
        return analysed.filter(
            and_(CommentAnalysis.is_spam.is_(False), CommentAnalysis.sentiment == sentiment.value)
        )

    row = (
        await session.execute(
            select(
                func.count(Comment.id),
                analysed,
                clean(Sentiment.POSITIVE),
                clean(Sentiment.NEUTRAL),
                clean(Sentiment.NEGATIVE),
                analysed.filter(CommentAnalysis.is_spam.is_(True)),
            )
            .select_from(Comment)
            .outerjoin(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
            .where(*scope)
        )
    ).one()
    total, done, positive, neutral, negative, spam = (int(v or 0) for v in row)
    clean_total = positive + neutral + negative
    return SentimentDistribution(
        post_id=post_id,
        account_id=account_id,
        since=since,
        until=until,
        total=total,
        analysed=done,
        positive=positive,
        neutral=neutral,
        negative=negative,
        spam=spam,
        positive_pct=_pct(positive, clean_total),
        neutral_pct=_pct(neutral, clean_total),
        negative_pct=_pct(negative, clean_total),
    )
