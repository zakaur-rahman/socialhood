"""The subscription state machine (T8.3; TR-BIL-02, FR-BIL-02, 03, 06, 07; §3.9 Subscription).

``apply_event`` applies one signed Dodo event, already stored in webhook_events and routed to its
workspace, inside that workspace's scope. It is the only code that changes ``subscriptions.plan``
or ``status``, together with ``apply_snapshot`` for the reconcile job (TR-BIL-03). Rules:

- An event whose time (webhook_events.occurred_at, Dodo's payload ``timestamp``) is older than
  ``subscriptions.last_event_at`` is ignored ("out of order"); an applied event moves
  last_event_at forward.
- The plan comes from the product id: DODO_PRODUCT_PRO_MONTHLY is pro, DODO_PRODUCT_MAX_MONTHLY
  max (R2); an unknown product is ignored with the reason.
- TR-BIL-02's table: active (trialing while in trial; trial_used_at set on the first trial),
  renewed, plan_changed, on_hold (grace_until = now + GRACE), cancelled (cancel_at_period_end;
  plan unchanged), failed and expired (plan free, status expired, downgrade effects). Dodo also
  sends subscription.updated, past_due, paused and unpaused (docs/CONFLICTS.md records how they
  map). payment.succeeded and payment.failed upsert ``payments`` and change no plan.
- After a change: reset the usage_counters limits of the new plan in the current period, write an
  audit log (billing.plan_changed), notify (plan_activated, payment_problem, plan_downgraded) and
  publish usage.updated after commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.dodo import DodoSubscription
from socialhood.models.platform import WebhookEvent

GRACE = timedelta(days=3)  # FR-BIL-06


@dataclass(frozen=True)
class Applied:
    """What an event did: ``changed`` False for an ignored (out-of-order, unknown) event."""

    changed: bool
    reason: str | None = None


async def apply_event(session: AsyncSession, event: WebhookEvent, *, now: datetime) -> Applied:
    raise NotImplementedError("T8.3")


async def apply_snapshot(
    session: AsyncSession, snapshot: DodoSubscription, *, now: datetime
) -> Applied:
    """TR-BIL-03: make the current workspace's subscription match what Dodo reports now."""
    raise NotImplementedError("T8.3")
