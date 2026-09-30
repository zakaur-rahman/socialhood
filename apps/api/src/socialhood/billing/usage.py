"""Usage periods and live counts (T8.1; §1.7, §5.8, FR-BIL-05).

Monthly allowances (ai_credits_monthly, scheduled_posts_monthly) are stored in usage_counters, one
row per period. A period runs from the subscription's ``billing_anchor_day`` to the same day next
month (repositories/usage.period_for): on a paid plan that is the day Dodo's current period
started, so allowances reset when Dodo bills; on Free it is the workspace's creation day (§1.7
"Credits reset on the subscription's billing anchor day (Free: the workspace creation day each
month)"). Days 29 to 31 count as the 28th so every month has one.

A plan change (billing/lifecycle.py) moves the anchor, then gives the current period's counters
the new plan's limits (F-15: "resets usage_counters limits for the new plan in the current
period"). A counter keeps what was used; a period that starts with the change starts at 0.

Capacity limits (accounts, active automations, knowledge characters, pending scheduled messages)
are counted live, never stored (§5.8).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import current_plan, entitlement
from socialhood.models.billing import UsageMetric
from socialhood.repositories import automations, knowledge, scheduled, subscriptions, usage

# The §1.7 keys counted per period, and their usage_counters metric.
PERIOD_KEYS: dict[str, UsageMetric] = {
    "ai_credits_monthly": UsageMetric.AI_CREDITS,
    "scheduled_posts_monthly": UsageMetric.SCHEDULED_POSTS,
}


def anchor_day(day: date | datetime) -> int:
    """subscriptions.billing_anchor_day for a period starting on ``day`` (1-28)."""
    return min(day.day, 28)


async def apply_plan_limits(session: AsyncSession, plan: str, *, today: date) -> None:
    """The current period's counters exist and carry ``plan``'s limits."""
    for key, metric in PERIOD_KEYS.items():
        limit = entitlement(plan, key)
        start, _ = await usage.ensure_counter(session, today=today, limit=limit, metric=metric)
        await subscriptions.set_counter_limit(
            session, metric=metric, period_start=start, limit=limit
        )


async def period_used(session: AsyncSession, key: str, *, today: date) -> tuple[int, int | None]:
    """(used, limit) of a monthly allowance in the current period (creates the counter)."""
    metric = PERIOD_KEYS[key]
    plan_limit = entitlement(await current_plan(session), key)
    start, _ = await usage.ensure_counter(session, today=today, limit=plan_limit, metric=metric)
    row = await usage.counter(session, start, metric=metric)
    if row is None:  # pragma: no cover - ensure_counter just made it
        return 0, plan_limit
    return row.used, row.limit


async def live_used(session: AsyncSession, key: str) -> int:
    """What a capacity key uses now, counted live (§5.8)."""
    if key == "active_automations":
        return await automations.count_active(session)
    if key == "knowledge_characters":
        return await knowledge.characters_used(session)
    if key == "pending_scheduled_messages":
        return await scheduled.count_pending(session)
    raise KeyError(f"{key} is not counted live")
