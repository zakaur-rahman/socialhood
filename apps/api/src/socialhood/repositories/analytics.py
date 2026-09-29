"""Writes for the metric snapshots (FR-ANL-01): post_metric_snapshots, account_daily_metrics and the
live counts on media_items. Inserts never overwrite: each window and each day is captured once, so
a re-run or a second worker writes nothing."""

from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping
from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.analytics import AccountDailyMetric, PostMetricSnapshot
from socialhood.models.media import MediaItem
from socialhood.repositories.base import scoped_update


async def insert_snapshot(
    session: AsyncSession,
    *,
    media_item_id: uuid.UUID,
    window: str,
    captured_at: datetime,
    metrics: Mapping[str, int],
    insights_final: bool,
) -> bool:
    """Store the post's snapshot for ``window``; False when that window was already captured."""
    statement = (
        insert(PostMetricSnapshot)
        .values(
            workspace_id=require_workspace(),
            media_item_id=media_item_id,
            window=window,
            captured_at=captured_at,
            metrics=dict(metrics),
            insights_final=insights_final,
        )
        .on_conflict_do_nothing(
            index_elements=[PostMetricSnapshot.media_item_id, PostMetricSnapshot.window]
        )
        .returning(PostMetricSnapshot.id)
    )
    return (await session.execute(statement)).scalar_one_or_none() is not None


async def mark_final(
    session: AsyncSession, media_item_id: uuid.UUID, windows: Collection[str]
) -> None:
    """Mark the post's snapshots for ``windows`` final (their lagging insights re-read)."""
    await session.execute(
        scoped_update(PostMetricSnapshot, media_item_id=media_item_id)
        .where(PostMetricSnapshot.window.in_(list(windows)))
        .values(insights_final=True)
    )


async def set_live_counts(
    session: AsyncSession,
    media_item_id: uuid.UUID,
    *,
    like_count: int | None,
    comments_count: int | None,
) -> None:
    """Refresh the post's like and comment counts with the ones the platform just gave."""
    values = {
        name: value
        for name, value in (("like_count", like_count), ("comments_count", comments_count))
        if value is not None
    }
    if values:
        await session.execute(scoped_update(MediaItem, id=media_item_id).values(**values))


async def insert_account_day(
    session: AsyncSession,
    *,
    social_account_id: uuid.UUID,
    day: date,
    followers_count: int | None,
    metrics: Mapping[str, int],
    captured_at: datetime,
) -> bool:
    """Store the account's row for ``day``; False when that day was already captured."""
    statement = (
        insert(AccountDailyMetric)
        .values(
            workspace_id=require_workspace(),
            social_account_id=social_account_id,
            date=day,
            followers_count=followers_count,
            metrics=dict(metrics),
            captured_at=captured_at,
        )
        .on_conflict_do_nothing(
            index_elements=[AccountDailyMetric.social_account_id, AccountDailyMetric.date]
        )
        .returning(AccountDailyMetric.id)
    )
    return (await session.execute(statement)).scalar_one_or_none() is not None


async def set_account_day_metrics(
    session: AsyncSession, social_account_id: uuid.UUID, day: date, metrics: Mapping[str, int]
) -> None:
    """Replace a stored day's insight values (followers stay as read that day)."""
    await session.execute(
        scoped_update(AccountDailyMetric, social_account_id=social_account_id, date=day).values(
            metrics=dict(metrics)
        )
    )
