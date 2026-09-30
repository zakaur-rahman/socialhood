"""The subscription state machine (T8.3; TR-BIL-02, TR-BIL-03, FR-BIL-02, 03, 06, 07; F-15).

``apply_event`` applies one signed Dodo event, already stored in webhook_events and routed to its
workspace, inside that workspace's scope. ``apply_snapshot`` makes a paid subscription match what
GET /subscriptions/{id} reports (the reconcile job, TR-BIL-03). They are the only code that
changes ``subscriptions.plan`` or ``status``; neither can turn a Free workspace into a paid one
except a signed event, so no checkout return, API call or job grants Pro.

Ordering: an event whose time (webhook_events.occurred_at, Dodo's ``timestamp``) is older than
``subscriptions.last_event_at`` is ignored ("out of order"); an applied event, or a snapshot that
corrected drift, moves last_event_at forward.

The plan comes from the product id (plans.plan_for_product); an unknown product is ignored.
Events about a subscription other than the workspace's are ignored, except one that grants a plan
while the workspace has no live one (a new checkout).

Events (TR-BIL-02, and C-049's mapping for the ones it doesn't list):

- subscription.active: plan from product; trialing while in the trial, else active; period; the
  workspace's trial_used_at set on its first trial (TR-BIL-05).
- subscription.renewed: active; new period; plan from product; grace cleared.
- subscription.plan_changed: plan from product; period; status kept.
- subscription.unpaused: active (trialing while in the trial); grace cleared.
- subscription.on_hold, past_due, paused: on_hold; grace_until = event time + 3 days (kept when
  already on hold); payment_problem.
- subscription.updated: period and cancel flag only.
- subscription.cancelled: cancel_at_period_end; the plan stays until the period ends, and ends at
  once when it already has (Dodo cancels a scheduled cancellation at the period end).
- subscription.failed, expired: expired; plan free; downgrade effects.
- payment.succeeded, failed, processing, cancelled: a payments row (succeeded, failed, pending,
  failed); no plan change; a failed renewal notifies payment_problem.
- refund.*, dispute.*, anything else: logged and ignored.

After a change: the anchor day follows the plan (Dodo's period start on a paid plan, the
workspace's creation day on Free), the current period's counters take the new plan's limits,
a lower plan applies the downgrade effects, owners and admins are notified (plan_activated,
payment_problem, plan_downgraded: the type only; services/notifications picks the channels), and
usage.updated is queued for after the commit (C-049: the web refetches GET …/billing).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.dodo import DodoError, DodoSubscription
from socialhood.billing.dodo_http import parse_datetime, parse_subscription
from socialhood.billing.downgrade import DowngradeReport, apply_downgrade
from socialhood.billing.plans import PLANS, plan_for_product
from socialhood.billing.usage import PERIOD_KEYS, anchor_day, apply_plan_limits
from socialhood.db.tenancy import require_workspace
from socialhood.models.billing import PaymentStatus, Plan, Subscription, SubscriptionStatus
from socialhood.models.identity import Workspace
from socialhood.models.platform import WebhookEvent
from socialhood.observability.logging import get_logger
from socialhood.realtime import events
from socialhood.repositories import payments, subscriptions, usage
from socialhood.repositories.subscriptions import LIVE_STATUSES
from socialhood.services.notifications import notify_admins
from socialhood.settings import Settings, get_settings

log = get_logger(__name__)

GRACE = timedelta(days=3)  # FR-BIL-06

S = SubscriptionStatus
GRANTS = frozenset(
    {
        "subscription.active",
        "subscription.renewed",
        "subscription.plan_changed",
        "subscription.unpaused",
    }
)
HOLDS = frozenset({"subscription.on_hold", "subscription.past_due", "subscription.paused"})
ENDS = frozenset({"subscription.failed", "subscription.expired"})
PAYMENTS = {
    "payment.succeeded": PaymentStatus.SUCCEEDED,
    "payment.failed": PaymentStatus.FAILED,
    "payment.processing": PaymentStatus.PENDING,
    "payment.cancelled": PaymentStatus.FAILED,
}
LOGGED_ONLY = ("refund.", "dispute.")
BILLING_LINK = "/settings/billing"


@dataclass(frozen=True)
class Applied:
    """What an event did: ``changed`` False for an ignored (out-of-order, unknown) event."""

    changed: bool
    reason: str | None = None


def _rank(plan: str) -> int:
    return PLANS.index(plan) if plan in PLANS else 0


def _day(at: datetime) -> str:
    return f"{at.day} {at:%B}"


# ---------------------------------------------------------------- events


async def apply_event(
    session: AsyncSession,
    event: WebhookEvent,
    *,
    now: datetime,
    settings: Settings | None = None,
) -> Applied:
    settings = settings or get_settings()
    event_type = event.event_type
    data = event.payload.get("data")
    if not isinstance(data, dict):
        return Applied(False, "the event has no data")
    at = event.occurred_at or event.received_at or now
    if event_type in PAYMENTS:
        return await _payment(session, PAYMENTS[event_type], data, at=at)
    if event_type.startswith(LOGGED_ONLY):
        log.info("dodo_event_recorded", event_type=event_type)
        return Applied(False, f"{event_type} is recorded, not acted on")
    if not event_type.startswith("subscription."):
        return Applied(False, f"{event_type} events are not used")
    try:
        snap = parse_subscription(data)
    except DodoError:
        return Applied(False, "the event's subscription can't be read")

    sub = await subscriptions.current(session, for_update=True)
    if sub is None:
        return Applied(False, "the workspace has no subscription row")
    if sub.last_event_at is not None and at < sub.last_event_at:
        return Applied(False, "out of order: older than the last event applied")
    ours = sub.dodo_subscription_id == snap.subscription_id
    paid = sub.plan != Plan.FREE
    before = (sub.plan, sub.status, sub.cancel_at_period_end)

    if event_type in GRANTS:
        plan = plan_for_product(snap.product_id, settings)
        if plan is None:
            return Applied(False, f"product {snap.product_id} is not a plan we sell")
        if not ours and sub.dodo_subscription_id is not None and sub.status in LIVE_STATUSES:
            # Two checkouts completed at once: Dodo bills both, we honour the first. An alert, so
            # someone cancels and refunds the second in Dodo's dashboard.
            log.error(
                "alert",
                kind="billing_duplicate_subscription",
                detail=f"{snap.subscription_id} while {sub.dodo_subscription_id} is live",
            )
            return Applied(False, "the workspace already has another live subscription")
        await _grant(session, sub, snap, plan, event_type, at=at)
    elif not ours:
        return Applied(False, "not the workspace's subscription")
    elif event_type in HOLDS:
        if not paid:
            return Applied(False, "the plan has already ended")
        _hold(sub, snap, at)
    elif event_type == "subscription.cancelled":
        if not paid:
            return Applied(False, "the plan has already ended")
        _cancel(sub, snap, at)
    elif event_type in ENDS:
        if not paid:
            return Applied(False, "the plan has already ended")
        _expire(sub)
    elif event_type == "subscription.updated":
        if not paid:
            return Applied(False, "the plan has already ended")
        _period(sub, snap)
        sub.cancel_at_period_end = snap.cancel_at_next_billing_date
    else:
        return Applied(False, f"{event_type} events are not used")

    sub.last_event_at = at
    await _after_change(session, sub, before, now=now, at=at)
    log.info(
        "billing_event_applied",
        event_type=event_type,
        plan=sub.plan,
        status=sub.status,
        cancel_at_period_end=sub.cancel_at_period_end,
    )
    return Applied(True)


async def _grant(
    session: AsyncSession,
    sub: Subscription,
    snap: DodoSubscription,
    plan: str,
    event_type: str,
    *,
    at: datetime,
) -> None:
    trial = snap.in_trial(at) and event_type != "subscription.renewed"
    if event_type == "subscription.plan_changed" and sub.status in LIVE_STATUSES:
        status = S(sub.status)  # a plan change keeps trialing, active or on hold
    else:
        status = S.TRIALING if trial else S.ACTIVE
    sub.plan = plan
    sub.status = status
    sub.dodo_subscription_id = snap.subscription_id
    sub.dodo_customer_id = snap.customer_id or sub.dodo_customer_id
    sub.dodo_product_id = snap.product_id
    _period(sub, snap)
    sub.cancel_at_period_end = snap.cancel_at_next_billing_date
    if status != S.ON_HOLD:
        sub.grace_until = None
    sub.trial_ends_at = snap.trial_ends_at() if status == S.TRIALING else None
    if status == S.TRIALING:
        workspace = await session.get(Workspace, require_workspace())
        if workspace is not None and workspace.trial_used_at is None:
            workspace.trial_used_at = at  # TR-BIL-05: one trial per workspace and owner email


def _hold(sub: Subscription, snap: DodoSubscription, at: datetime) -> None:
    if sub.status != S.ON_HOLD or sub.grace_until is None:
        sub.grace_until = at + GRACE
    sub.status = S.ON_HOLD
    sub.cancel_at_period_end = snap.cancel_at_next_billing_date


def _cancel(sub: Subscription, snap: DodoSubscription, at: datetime) -> None:
    end = snap.next_billing_date or sub.current_period_end
    sub.cancel_at_period_end = True
    if end is None or end <= at:
        _expire(sub)


def _expire(sub: Subscription) -> None:
    """Plan Free, status expired. The Dodo ids stay, for the portal's invoices."""
    sub.plan = Plan.FREE
    sub.status = S.EXPIRED
    sub.grace_until = None
    sub.trial_ends_at = None
    sub.cancel_at_period_end = False


def _period(sub: Subscription, snap: DodoSubscription) -> None:
    sub.current_period_start = snap.previous_billing_date or sub.current_period_start
    sub.current_period_end = snap.next_billing_date or sub.current_period_end


# ---------------------------------------------------------------- after a change


async def _after_change(
    session: AsyncSession,
    sub: Subscription,
    before: tuple[str, str, bool],
    *,
    now: datetime,
    at: datetime,
) -> None:
    old_plan, old_status, old_cancel = before
    workspace = await session.get(Workspace, require_workspace())
    if sub.plan != Plan.FREE:
        anchor = anchor_day(sub.current_period_start or at)
    else:
        anchor = anchor_day(workspace.created_at if workspace is not None else at)
    sub.billing_anchor_day = anchor
    await session.flush()
    await apply_plan_limits(session, sub.plan, today=now.date())

    report: DowngradeReport | None = None
    if _rank(sub.plan) < _rank(old_plan):
        report = await apply_downgrade(session, plan=sub.plan, now=now)
    await _notify(session, sub, old_plan, old_status, report)
    if (sub.plan, sub.status, sub.cancel_at_period_end) != (old_plan, old_status, old_cancel):
        await _queue_usage(session, now=now)


async def _notify(
    session: AsyncSession,
    sub: Subscription,
    old_plan: str,
    old_status: str,
    report: DowngradeReport | None,
) -> None:
    name = sub.plan.capitalize()
    sub_ref = sub.dodo_subscription_id or "none"
    was_live = old_plan != Plan.FREE and old_status in LIVE_STATUSES
    if (
        sub.plan != Plan.FREE
        and sub.status in LIVE_STATUSES
        and (not was_live or _rank(sub.plan) > _rank(old_plan))
    ):
        trial = sub.status == S.TRIALING
        await notify_admins(
            session,
            type="plan_activated",
            severity="info",
            title=f"Your {name} trial has started" if trial else f"You're on {name}",
            body=(
                f"{name} is on until {_day(sub.trial_ends_at)}. Your new limits apply now."
                if trial and sub.trial_ends_at is not None
                else f"{name} is active. Your new limits apply now."
            ),
            link=BILLING_LINK,
            dedupe_key=f"plan_activated:{sub_ref}:{sub.plan}",
        )
    if sub.status == S.ON_HOLD and old_status != S.ON_HOLD and sub.grace_until is not None:
        await _payment_problem(session, sub)
    if report is not None:
        await notify_admins(
            session,
            type="plan_downgraded",
            severity="warning",
            title=f"You're on {name} now",
            body=report.summary(),
            link=BILLING_LINK,
            dedupe_key=f"plan_downgraded:{sub_ref}:{old_plan}:{sub.last_event_at or ''}",
        )


async def _payment_problem(session: AsyncSession, sub: Subscription) -> None:
    """One payment_problem per failing renewal: the on_hold event and the failed payment of the
    same period share the dedupe key, so the owner hears once."""
    period = sub.current_period_end.date().isoformat() if sub.current_period_end else "none"
    grace = f" by {_day(sub.grace_until)}" if sub.grace_until is not None else ""
    await notify_admins(
        session,
        type="payment_problem",
        severity="critical",
        title="Payment failed",
        body=f"Update your payment method{grace} to keep {sub.plan.capitalize()}.",
        link=BILLING_LINK,
        dedupe_key=f"payment_problem:{sub.dodo_subscription_id}:{period}",
    )


async def _queue_usage(session: AsyncSession, *, now: datetime) -> None:
    """usage.updated per monthly allowance, after the commit (the web refetches billing)."""
    workspace_id = require_workspace()
    for metric in PERIOD_KEYS.values():
        start, end = usage.period_for(await usage.anchor_day(session), now.date())
        row = await usage.counter(session, start, metric=metric)
        events.queue(
            session,
            workspace_id,
            "usage.updated",
            {
                "metric": metric.value,
                "used": row.used if row else 0,
                "limit": row.limit if row else None,
                "period_end": (row.period_end if row else end).isoformat(),
            },
        )


# ---------------------------------------------------------------- payments


def _amount(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


async def _payment(
    session: AsyncSession, status: PaymentStatus, data: dict[str, Any], *, at: datetime
) -> Applied:
    payment_id = data.get("payment_id")
    amount = _amount(data.get("total_amount"))
    currency = data.get("currency")
    if not isinstance(payment_id, str) or not payment_id or amount is None:
        return Applied(False, "the payment can't be read")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        return Applied(False, "the payment has no currency")
    invoice_url = data.get("invoice_url")
    reason = data.get("error_message") or data.get("error_code")
    sub_id = data.get("subscription_id") if isinstance(data.get("subscription_id"), str) else None
    written = await payments.upsert(
        session,
        dodo_payment_id=payment_id,
        dodo_subscription_id=sub_id,
        status=status,
        amount_minor=amount,
        currency=currency.upper(),
        occurred_at=parse_datetime(data.get("created_at")) or at,
        invoice_url=invoice_url if isinstance(invoice_url, str) and invoice_url else None,
        failure_reason=(str(reason)[:500] if reason else None)
        if status == PaymentStatus.FAILED
        else None,
    )
    if not written:
        return Applied(False, "a newer status of this payment is already recorded")
    if status == PaymentStatus.FAILED and sub_id is not None:
        sub = await subscriptions.current(session)
        if (
            sub is not None
            and sub.dodo_subscription_id == sub_id
            and sub.plan != Plan.FREE
            and sub.status in LIVE_STATUSES
        ):
            await _payment_problem(session, sub)  # a renewal failed (FR-BIL-06)
    return Applied(True)


# ---------------------------------------------------------------- snapshots (TR-BIL-03)


def _fields(sub: Subscription) -> dict[str, Any]:
    return {
        "plan": sub.plan,
        "status": sub.status,
        "product": sub.dodo_product_id,
        "period_end": sub.current_period_end,
        "cancel_at_period_end": sub.cancel_at_period_end,
    }


async def apply_snapshot(
    session: AsyncSession,
    snapshot: DodoSubscription,
    *,
    now: datetime,
    settings: Settings | None = None,
) -> Applied:
    """TR-BIL-03: make the current workspace's paid subscription match what Dodo reports now.
    A Free workspace is never changed here (only a signed event can grant a plan)."""
    settings = settings or get_settings()
    sub = await subscriptions.current(session, for_update=True)
    if sub is None or sub.plan == Plan.FREE:
        return Applied(False, "Free workspaces change only through a signed event")
    if sub.dodo_subscription_id != snapshot.subscription_id:
        return Applied(False, "not the workspace's subscription")
    before_fields = _fields(sub)
    before = (sub.plan, sub.status, sub.cancel_at_period_end)
    status = snapshot.status
    if status == "active":
        plan = plan_for_product(snapshot.product_id, settings)
        if plan is None:
            return Applied(False, f"product {snapshot.product_id} is not a plan we sell")
        wanted = S.TRIALING if snapshot.in_trial(now) else S.ACTIVE
        if sub.plan != plan or sub.status != wanted:
            await _grant(session, sub, snapshot, plan, "subscription.active", at=now)
        else:
            _period(sub, snapshot)
            sub.cancel_at_period_end = snapshot.cancel_at_next_billing_date
    elif status in ("on_hold", "past_due", "paused"):
        _hold(sub, snapshot, now)
    elif status == "cancelled":
        _cancel(sub, snapshot, now)
    elif status in ("expired", "failed"):
        _expire(sub)
    else:  # pending: nothing to mirror yet
        return Applied(False, f"Dodo reports {status}")
    after = _fields(sub)
    drift = {k: (before_fields[k], after[k]) for k in after if before_fields[k] != after[k]}
    if not drift:
        return Applied(False)
    sub.last_event_at = max(sub.last_event_at or now, now)
    await _after_change(session, sub, before, now=now, at=now)
    log.warning(
        "billing_drift_corrected",
        subscription_id=snapshot.subscription_id,
        drift={k: [str(v[0]), str(v[1])] for k, v in drift.items()},
    )
    return Applied(True, ", ".join(sorted(drift)))


async def expire_now(session: AsyncSession, *, now: datetime, reason: str) -> Applied:
    """End the current workspace's paid plan (grace passed while on hold, TR-BIL-03)."""
    sub = await subscriptions.current(session, for_update=True)
    if sub is None or sub.plan == Plan.FREE:
        return Applied(False, "already Free")
    before = (sub.plan, sub.status, sub.cancel_at_period_end)
    _expire(sub)
    sub.last_event_at = max(sub.last_event_at or now, now)
    await _after_change(session, sub, before, now=now, at=now)
    log.warning("billing_plan_expired", reason=reason)
    return Applied(True, reason)
