"""Comment sentiment distribution (T6.5; TR-AGT-05; agent-architecture §6
``sentiment_distribution(scope)``), from comment_analyses (TR-AI-11).

For one post, or for the comments made in a date range (the workspace's calendar days,
optionally on one account's posts). Deleted comments are left out. ``analysed`` counts comments
with an analysis; the rest are reported as not analysed, never guessed. Spam is counted apart:
positive + neutral + negative are analysed comments that are not spam, and the percentages are
shares of that sum (C-039).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import Sentiment
from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import Comment
from socialhood.schemas.analytics import SentimentDistribution
from socialhood.services.analytics.common import View, date_range, load_account, load_post


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


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
