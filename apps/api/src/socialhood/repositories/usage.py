"""AI credit counters and usage events (TR-AI-09, §5.8). One ``usage_counters`` row per
workspace, metric and period; the period starts on the subscription's billing anchor day."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.billing import AiUsageEvent, Subscription, UsageCounter, UsageMetric
from socialhood.repositories.base import scoped_update

AI = UsageMetric.AI_CREDITS


@dataclass(frozen=True)
class Counter:
    used: int
    limit: int | None  # None: unlimited
    period_start: date
    period_end: date
    notified_80_at: datetime | None
    notified_100_at: datetime | None


def _add_months(day: date, months: int, anchor: int) -> date:
    month_index = day.year * 12 + day.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, anchor)


def period_for(anchor_day: int, today: date) -> tuple[date, date]:
    """The credit period containing ``today``: from the last anchor day to the next (exclusive).
    Anchors are 1-28, so every month has one."""
    start = date(today.year, today.month, anchor_day)
    if today < start:
        start = _add_months(start, -1, anchor_day)
    return start, _add_months(start, 1, anchor_day)


async def anchor_day(session: AsyncSession) -> int:
    day = await session.scalar(select(Subscription.billing_anchor_day))
    return int(day or 1)


async def ensure_counter(
    session: AsyncSession, *, today: date, limit: int | None
) -> tuple[date, date]:
    """The current period's AI counter exists (limit as the plan says now); returns the period."""
    start, end = period_for(await anchor_day(session), today)
    await session.execute(
        insert(UsageCounter)
        .values(
            workspace_id=require_workspace(),
            metric=AI,
            period_start=start,
            period_end=end,
            used=0,
            limit=limit,
        )
        .on_conflict_do_nothing(index_elements=["workspace_id", "metric", "period_start"])
    )
    return start, end


async def counter(session: AsyncSession, period_start: date) -> Counter | None:
    row = await session.scalar(
        select(UsageCounter).where(
            UsageCounter.metric == AI, UsageCounter.period_start == period_start
        )
    )
    if row is None:
        return None
    return Counter(
        row.used,
        row.limit,
        row.period_start,
        row.period_end,
        row.notified_80_at,
        row.notified_100_at,
    )


async def reserve(session: AsyncSession, *, period_start: date, cost: int) -> int | None:
    """Atomically add ``cost`` if it fits under the limit (TR-AI-09); the new total, or None
    when the credits would run out."""
    fits = (UsageCounter.limit.is_(None)) | (UsageCounter.used + cost <= UsageCounter.limit)
    used = await session.scalar(
        scoped_update(UsageCounter, metric=AI, period_start=period_start)
        .where(fits)
        .values(used=UsageCounter.used + cost, updated_at=func.now())
        .returning(UsageCounter.used)
    )
    return None if used is None else int(used)


async def refund(session: AsyncSession, *, period_start: date, cost: int) -> None:
    await session.execute(
        scoped_update(UsageCounter, metric=AI, period_start=period_start).values(
            used=func.greatest(UsageCounter.used - cost, 0), updated_at=func.now()
        )
    )


async def mark_notified(
    session: AsyncSession, *, period_start: date, level: int, at: datetime
) -> bool:
    """Set notified_80_at or notified_100_at once; True when this call set it."""
    column = UsageCounter.notified_80_at if level == 80 else UsageCounter.notified_100_at
    done = await session.scalar(
        scoped_update(UsageCounter, metric=AI, period_start=period_start)
        .where(column.is_(None))
        .values({column: at})
        .returning(UsageCounter.id)
    )
    return done is not None


def record_event(
    session: AsyncSession,
    *,
    feature: str,
    model: str,
    credits: int,
    outcome: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
) -> None:
    session.add(
        AiUsageEvent(
            feature=feature,
            model=model,
            credits=credits,
            outcome=outcome,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            ref_type=ref_type,
            ref_id=ref_id,
        )
    )
