"""P6 rows for tests: comment analyses, post metric snapshots and account daily metrics (written
through the ORM in the workspace's scope, committed, returned as ids). Posts and comments come from
tests/support/automations.py (make_media_item, make_comment)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.analytics import AccountDailyMetric, CommentAnalysis, PostMetricSnapshot
from socialhood.models.automations import Comment


def _wid(workspace_id: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(workspace_id))


async def make_comment_analysis(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    comment_id: uuid.UUID | str,
    mark_done: bool = True,
    **values: Any,
) -> uuid.UUID:
    """An analysis of the comment, on the comment's post; the comment's ``analysis_status``
    becomes done unless ``mark_done`` is False."""
    defaults: dict[str, Any] = {
        "sentiment": "positive",
        "sentiment_score": 0.6,
        "intent": "product_inquiry",
        "is_spam": False,
        "topic": "price",
        "model": "fake-model",
        "prompt_version": "comments.v1",
    }
    with workspace_scope(_wid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            comment = await session.get(Comment, uuid.UUID(str(comment_id)))
            assert comment is not None, "no such comment in this workspace"
            row = CommentAnalysis(
                comment_id=comment.id,
                media_item_id=comment.media_item_id,
                **{**defaults, **values},
            )
            session.add(row)
            if mark_done:
                comment.analysis_status = "done"
            await session.commit()
            return row.id


async def make_snapshot(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    media_item_id: uuid.UUID | str,
    window: str = "24h",
    metrics: dict[str, int] | None = None,
    insights_final: bool = False,
    captured_at: datetime | None = None,
) -> uuid.UUID:
    """A post_metric_snapshots row; by default a 24 h snapshot with insights."""
    default_metrics = {
        "likes": 120,
        "comments": 14,
        "reach": 2400,
        "views": 3100,
        "shares": 9,
        "saves": 22,
        "total_interactions": 165,
    }
    with workspace_scope(_wid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = PostMetricSnapshot(
                media_item_id=uuid.UUID(str(media_item_id)),
                window=window,
                captured_at=captured_at or datetime.now(UTC),
                metrics=default_metrics if metrics is None else metrics,
                insights_final=insights_final,
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_account_day(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str,
    day: date | None = None,
    followers_count: int | None = 1520,
    metrics: dict[str, int] | None = None,
    captured_at: datetime | None = None,
) -> uuid.UUID:
    """An account_daily_metrics row; by default today's, with insights."""
    default_metrics = {
        "reach": 5400,
        "views": 9100,
        "accounts_engaged": 310,
        "total_interactions": 480,
        "follows": 12,
        "unfollows": 3,
        "profile_links_taps": 25,
    }
    with workspace_scope(_wid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = AccountDailyMetric(
                social_account_id=uuid.UUID(str(account_id)),
                date=day or datetime.now(UTC).date(),
                followers_count=followers_count,
                metrics=default_metrics if metrics is None else metrics,
                captured_at=captured_at or datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            return row.id
