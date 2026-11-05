"""AI credit metering (TR-AI-09, FR-AI-05).

``metered(...)`` wraps one AI call:

    async with metered(sessionmaker, workspace_id=wid, feature="message_analysis",
                       ref_type="message", ref_id=message.id) as meter:
        result = await provider.generate_json(...)
        meter.record(result)

It reserves the feature's credits (§1.7) in its own short transaction before the call, so no row
lock is held while the model runs, and raises ``QuotaExceeded`` before any call when they would run
out. A feature charged per batch passes the batch's ``cost`` (comment_analysis: 1 credit per 20
comments, rounded up, T6.2). After the call it records an ``ai_usage_events`` row; if the block
raises, it refunds the credits and records the event with 0 credits. Crossing 80% and 100% of the
period's credits notifies the owners and admins once per period.

Credits bound a workspace; two more limits sit in Valkey. Both let the call through when Valkey is
down (logged), like the rate limits: they protect spend and must not take the service down, and
credits still apply.

- ``contact_admitted``: what one contact may use, checked before a job that answers them starts.
- The platform's daily spend (TR-AI-13): each call's tokens at the model's price add to a counter
  for the UTC day, and ``metered`` raises ``SpendPaused`` once it is reached.
  AI_DAILY_SPEND_LIMIT_USD pauses the bulk features; twice that stops every feature, so spend is
  bounded while one spike can't stop customers' replies at the first limit. An alert goes out at
  80% and at 100%.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai.provider import AIError, AIResult
from socialhood.billing.plans import CREDIT_COSTS, current_plan, entitlement
from socialhood.db.tenancy import workspace_scope
from socialhood.kv import make_redis
from socialhood.observability.logging import get_logger
from socialhood.observability.metrics import record_ai_call
from socialhood.repositories import usage
from socialhood.security import ratelimit
from socialhood.services.notifications import notify_admins
from socialhood.settings import get_settings

log = get_logger(__name__)

# What one contact may use, per kind of job. Refused jobs aren't counted. A burst is one analysis.
CONTACT_LIMITS = (("hour", 30, 3600), ("day", 60, 86_400))
# USD per 1M tokens (input, output), Gemini paid tier as listed for 2027. Any other model is counted
# at the dearest. shortcut: update by hand when prices or AI_MODEL_* change.
TOKEN_PRICES = {"gemini-3.5-flash-lite": (0.30, 2.50), "gemini-3.8-flash": (1.50, 7.50)}
DEAREST_PRICE = (1.50, 7.50)
BULK_FEATURES = frozenset({"comment_analysis", "conversation_summary", "post_summary"})
HARD_STOP_MULTIPLE = 2.0
SPEND_TIMEOUT_S = 1.0


class QuotaExceeded(Exception):
    """The workspace's AI credits for this period are used up (FR-AI-05)."""


class SpendPaused(QuotaExceeded):
    """The platform's daily AI spend is reached (TR-AI-13); it lifts at 00:00 UTC. A subclass, so
    every caller already stops cleanly; one that gives up on work for good must not for this."""


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


async def contact_admitted(redis: Redis, contact_id: uuid.UUID, kind: str) -> bool:
    """Count one AI job for the contact; False when over CONTACT_LIMITS. See the module docstring
    on Valkey being down."""
    if not get_settings().rate_limits_enabled:
        return True
    try:
        for period, max_jobs, window_s in CONTACT_LIMITS:
            limit = ratelimit.Limit(f"ai_contact_{kind}_{period}", max_jobs, window_s)
            if await ratelimit.hit(redis, limit, str(contact_id)) > 0:
                log.info("ai_contact_limited", contact_id=str(contact_id), kind=kind, period=period)
                return False
    except Exception as error:
        log.warning("ai_contact_limit_unavailable", error=type(error).__name__)
    return True


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    per_input, per_output = TOKEN_PRICES.get(model, DEAREST_PRICE)
    return (input_tokens * per_input + output_tokens * per_output) / 1_000_000


def _spend_key() -> str:
    return f"ai:spend:{datetime.now(UTC).date().isoformat()}"


def spend_ceiling(feature: str, limit_usd: float) -> float:
    return limit_usd if feature in BULK_FEATURES else limit_usd * HARD_STOP_MULTIPLE


async def _spend_paused(feature: str) -> bool:
    # shortcut: a short-lived client, since callers hold no Valkey handle; a call to the model
    # dwarfs the connect. Thread one through metered if this ever shows in latency.
    try:
        settings = get_settings()
        redis = make_redis(settings)
        try:
            async with asyncio.timeout(SPEND_TIMEOUT_S):
                spent = float(await redis.get(_spend_key()) or 0)
        finally:
            await redis.aclose()
    except Exception as error:
        log.warning("ai_spend_unavailable", error=type(error).__name__)
        return False
    return spent >= spend_ceiling(feature, settings.ai_daily_spend_limit_usd)


async def _add_spend(meter: Meter) -> None:
    """Add a finished call to the day's spend, and alert when it crosses 80% or 100%."""
    cost = cost_usd(meter.model, meter.input_tokens, meter.output_tokens)
    if cost <= 0:
        return
    try:
        settings = get_settings()
        redis = make_redis(settings)
        try:
            async with asyncio.timeout(SPEND_TIMEOUT_S):
                total = float(await redis.incrbyfloat(_spend_key(), cost))
                await redis.expire(_spend_key(), 2 * 86_400)
        finally:
            await redis.aclose()
    except Exception as error:
        log.warning("ai_spend_unavailable", error=type(error).__name__)
        return
    limit = settings.ai_daily_spend_limit_usd
    for percent in (80, 100):
        if total - cost < limit * percent / 100 <= total:
            log.error(
                "alert", kind="ai_daily_spend", detail=f"{percent}% of the daily AI spend limit"
            )


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
    cost: int | None = None,
) -> AsyncIterator[Meter]:
    cost = CREDIT_COSTS[feature] if cost is None else cost
    at = now or datetime.now(UTC)
    if await _spend_paused(feature):
        log.info("ai_spend_paused", feature=feature)
        raise SpendPaused
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
    await _add_spend(meter)
    record_ai_call(
        feature,
        meter.model or "unknown",
        outcome,
        input_tokens=meter.input_tokens,
        output_tokens=meter.output_tokens,
    )
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
