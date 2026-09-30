"""Reconciliation (T8.3; TR-BIL-03): every 6 h, GET /subscriptions/{id} for each subscription
that isn't Free, correct drift through billing/lifecycle.apply_snapshot and log it; a
subscription past grace_until still on hold is set to Free. Runs from jobs/tasks/billing.py,
which finds the subscriptions across workspaces (the tenant bypass is allowed in jobs/) and calls
``reconcile_one`` in each workspace's scope.

- On hold past its grace: Dodo is asked first; a subscription Dodo reports active again is
  restored, anything else (still on hold, gone, or Dodo not answering) goes to Free with the
  downgrade effects (FR-BIL-06).
- Otherwise Dodo's answer is mirrored (a cancelled subscription whose period has ended goes to
  Free); when Dodo can't be reached, nothing changes until the next run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing import lifecycle
from socialhood.billing.dodo import DodoClient, DodoError
from socialhood.models.billing import Plan, SubscriptionStatus
from socialhood.observability.logging import get_logger
from socialhood.repositories import subscriptions
from socialhood.settings import Settings

log = get_logger(__name__)


@dataclass(frozen=True)
class Reconciled:
    drift: bool
    detail: str | None = None


async def reconcile_one(
    session: AsyncSession,
    dodo: DodoClient,
    *,
    now: datetime,
    settings: Settings | None = None,
) -> Reconciled:
    """The current workspace's subscription against Dodo."""
    sub = await subscriptions.current(session)
    if sub is None or sub.plan == Plan.FREE:
        return Reconciled(False, "free")
    grace_over = (
        sub.status == SubscriptionStatus.ON_HOLD
        and sub.grace_until is not None
        and sub.grace_until <= now
    )
    if sub.dodo_subscription_id is None:
        log.warning("billing_paid_without_dodo_subscription", plan=sub.plan)
        return Reconciled(False, "no Dodo subscription to compare")
    try:
        snapshot = await dodo.get_subscription(sub.dodo_subscription_id)
    except DodoError as error:
        if grace_over:
            applied = await lifecycle.expire_now(session, now=now, reason="grace ended")
            why = "has no such subscription" if error.not_found else "didn't answer"
            return Reconciled(applied.changed, f"grace ended; Dodo {why}")
        log.warning("billing_reconcile_skipped", status=error.status, retryable=error.retryable)
        return Reconciled(False, "Dodo didn't answer")
    if grace_over and snapshot.status != "active":
        applied = await lifecycle.expire_now(session, now=now, reason="grace ended")
        return Reconciled(applied.changed, "grace ended while on hold")
    applied = await lifecycle.apply_snapshot(session, snapshot, now=now, settings=settings)
    return Reconciled(applied.changed, applied.reason)
