"""AI credit metering (TR-AI-09, FR-AI-05).

``metered(...)`` wraps one AI call:

    async with metered(sessionmaker, workspace_id=wid, feature="message_analysis",
                       ref_type="message", ref_id=message.id) as meter:
        result = await provider.generate_json(...)
        meter.record(result)

It reserves the feature's credits (§1.7) in its own short transaction before the call, so no row
lock is held while the model runs, and raises ``QuotaExceeded`` before any call when they would run
out. After the call it records an ``ai_usage_events`` row; if the block raises, it refunds the
credits and records the event with 0 credits. Crossing 80% and 100% of the period's credits
notifies the owners and admins once per period.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai.provider import AIError, AIResult
from socialhood.billing.plans import CREDIT_COSTS, current_plan, entitlement
from socialhood.db.tenancy import workspace_scope
from socialhood.observability.logging import get_logger
from socialhood.repositories import usage
from socialhood.services.notifications import notify_admins

log = get_logger(__name__)


class QuotaExceeded(Exception):
    """The workspace's AI credits for this period are used up (FR-AI-05)."""


@dataclass(frozen=True)
class Quota:
    used: int
    limit: int | None  # None: unlimited
    period_end: date

    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(self.limit - self.used, 0)

    def allows(self, cost: int) -> bool:
        return self.limit is None or self.used + cost <= self.limit


@dataclass
class Meter:
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    def record(self, result: AIResult[object]) -> None:
        self.model = result.model
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.latency_ms += result.latency_ms


async def quota(session: AsyncSession, *, now: datetime | None = None) -> Quota:
    """The current workspace's credits this period (creates the period's counter)."""
    today = (now or datetime.now(UTC)).date()
    limit = entitlement(await current_plan(session), "ai_credits_monthly")
    start, end = await usage.ensure_counter(session, today=today, limit=limit)
    row = await usage.counter(session, start)
    used = row.used if row else 0
    return Quota(used=used, limit=row.limit if row else limit, period_end=end)


async def reserve(session: AsyncSession, *, cost: int, now: datetime) -> date:
    """Reserve ``cost`` credits in the caller's transaction; returns the period start."""
    limit = entitlement(await current_plan(session), "ai_credits_monthly")
    start, _ = await usage.ensure_counter(session, today=now.date(), limit=limit)
    used = await usage.reserve(session, period_start=start, cost=cost)
    if used is None:
        await _notify(session, start, 100, now)
        raise QuotaExceeded
    if limit:
        if used >= limit:
            await _notify(session, start, 100, now)
        elif used * 5 >= limit * 4:
            await _notify(session, start, 80, now)
    return start


async def _notify(session: AsyncSession, period_start: date, level: int, now: datetime) -> None:
    if not await usage.mark_notified(session, period_start=period_start, level=level, at=now):
        return
    if level == 100:
        title, body = (
            "AI credits used up",
            "Analysis, suggestions and auto replies are paused until your credits reset. "
            "Messaging works as usual.",
        )
    else:
        title, body = (
            "80% of AI credits used",
            "Analysis, suggestions and auto replies pause when your credits run out.",
        )
    await notify_admins(
        session,
        type=f"ai_credits_{level}",
        severity="warning" if level == 80 else "critical",
        title=title,
        body=body,
        link="/settings/billing",
        dedupe_key=f"ai_credits_{level}:{period_start.isoformat()}",
    )


@asynccontextmanager
async def metered(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: uuid.UUID,
    feature: str,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> AsyncIterator[Meter]:
    cost = CREDIT_COSTS[feature]
    at = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            try:
                period_start = await reserve(session, cost=cost, now=at)
            except QuotaExceeded:
                await session.commit()  # keeps the 100% notification (FR-AI-05)
                raise
            await session.commit()
    meter = Meter()
    try:
        yield meter
    except BaseException as error:
        outcome = "timeout" if isinstance(error, AIError) and error.code == "timeout" else "error"
        await _settle(
            sessionmaker,
            workspace_id,
            feature,
            meter,
            0,
            outcome,
            ref_type,
            ref_id,
            refund=(period_start, cost),
        )
        raise
    await _settle(sessionmaker, workspace_id, feature, meter, cost, "ok", ref_type, ref_id)


async def _settle(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: uuid.UUID,
    feature: str,
    meter: Meter,
    credits: int,
    outcome: str,
    ref_type: str | None,
    ref_id: uuid.UUID | None,
    *,
    refund: tuple[date, int] | None = None,
) -> None:
    """The usage event, and the refund when the call failed. Never raises: a lost event must
    not turn a successful call into a failure."""
    try:
        with workspace_scope(workspace_id):
            async with sessionmaker() as session:
                if refund is not None:
                    await usage.refund(session, period_start=refund[0], cost=refund[1])
                usage.record_event(
                    session,
                    feature=feature,
                    model=meter.model or "unknown",
                    credits=credits,
                    outcome=outcome,
                    input_tokens=meter.input_tokens,
                    output_tokens=meter.output_tokens,
                    latency_ms=meter.latency_ms,
                    ref_type=ref_type,
                    ref_id=ref_id,
                )
                await session.commit()
    except Exception:
        log.warning("ai_usage_settle_failed", feature=feature, outcome=outcome, exc_info=True)
