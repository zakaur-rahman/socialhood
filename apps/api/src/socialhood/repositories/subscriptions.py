"""The workspace's subscription row and its usage-counter limits (§5.8; TR-BIL-02, TR-BIL-03).

Only billing/lifecycle.py changes ``plan`` and ``status`` (from signed Dodo events and the
reconcile job's reads of Dodo). The cross-workspace lookups (routing an event, listing what to
reconcile) live in webhooks/dodo_routing.py and jobs/tasks/billing.py, where the tenant bypass is
allowed (TR-TEN-04).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.billing import Subscription, SubscriptionStatus, UsageCounter
from socialhood.repositories.base import scoped_update

# A paid plan is in force (Pro features on): trialing, active, or on hold within its grace.
LIVE_STATUSES = frozenset(
    {SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE, SubscriptionStatus.ON_HOLD}
)


async def current(session: AsyncSession, *, for_update: bool = False) -> Subscription | None:
    """The current workspace's subscription (one per workspace, created with it)."""
    query = select(Subscription)
    if for_update:
        query = query.with_for_update()
    return (await session.scalars(query)).one_or_none()


async def set_counter_limit(
    session: AsyncSession, *, metric: str, period_start: date, limit: int | None
) -> None:
    """F-15: the current period's counter takes the new plan's limit (used is kept)."""
    await session.execute(
        scoped_update(UsageCounter, metric=metric, period_start=period_start).values(
            limit=limit, updated_at=func.now()
        )
    )
