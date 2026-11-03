"""Billing (§5.10 BillingState; TR-BIL-01…06, F-15). P5 serves plan, entitlements and usage for
the AI credit banner (FR-AI-05); P8 adds prices, checkout, the portal, cancel and resume, and the
public plan list."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

PlanName = Literal["free", "pro", "max", "agency"]
PaidPlanName = Literal["pro", "max", "agency"]
BillingPeriodName = Literal["month", "six_month"]
SubscriptionStatusName = Literal["free", "trialing", "active", "on_hold", "expired"]
PaymentStatusName = Literal["succeeded", "failed", "refunded", "pending"]


class BillingPrice(ResponseModel):
    plan: PaidPlanName
    amount_minor: int
    currency: str
    interval: BillingPeriodName


class EntitlementValue(ResponseModel):
    key: str
    value: int | bool | list[str] | None  # None = unlimited


class UsageMeter(ResponseModel):
    metric: str  # ai_credits, scheduled_posts, knowledge_characters, …
    used: int
    limit: int | None = None
    period_end: date | None = None  # when counted credits reset


class BillingState(ResponseModel):
    plan: PlanName
    status: SubscriptionStatusName
    current_period_end: datetime | None = None
    trial_ends_at: datetime | None = None
    cancel_at_period_end: bool
    grace_until: datetime | None = None
    trial_eligible: bool
    # C-149: false while billing isn't set up on this server: paid plans aren't on sale, so the
    # UI offers no checkout or trial (the workspace stays on Free).
    billing_available: bool
    # Every plan and period on sale; six-month prices have interval "six_month".
    prices: list[BillingPrice]
    # What this workspace actually bought (its Dodo product), when Dodo can give the price.
    current_price: BillingPrice | None = None
    entitlements: list[EntitlementValue]
    usage: list[UsageMeter]


# ---------------------------------------------------------------- P8 (T8.2)


class CheckoutRequest(RequestModel):
    """POST …/billing/checkout (F-15). A plan or period is refused with 422 until its Dodo product
    is set."""

    plan: PaidPlanName
    period: BillingPeriodName = "month"


class CheckoutSession(ResponseModel):
    """Where to send the browser: Dodo's hosted checkout. Coming back to
    /w/{slug}/settings/billing?checkout=return changes nothing by itself; the plan changes when
    Dodo's signed webhook arrives (FR-BIL-02)."""

    checkout_url: str
    trial: bool  # the checkout starts the 7-day trial (TR-BIL-05; monthly Creator only)


class PortalSession(ResponseModel):
    """Dodo's customer portal (payment method, invoices; FR-BIL-04), opened in a new tab."""

    portal_url: str


class PlanOffer(ResponseModel):
    """One plan for the pricing page and the upgrade dialog: its entitlements (billing/plans.py)
    and, for a paid plan, its monthly price from Dodo (cached 1 h; null when Dodo can't be reached).
    ``six_month_price`` is set only while the plan's six-month product is on sale and priced."""

    plan: PlanName
    price: BillingPrice | None = None
    six_month_price: BillingPrice | None = None
    trial_days: int = Field(
        ge=0
    )  # 7 for Creator (pro), once per workspace and owner email (FR-BIL-03)
    entitlements: list[EntitlementValue]
    available: (
        bool  # false while billing is off (C-149), and for a plan until its monthly product is set
    )


class PlanList(ResponseModel):
    items: list[PlanOffer]


# ---------------------------------------------------------------- payment history (C-066)


class PaymentOut(ResponseModel):
    """One Dodo payment (§5.8 payments), as upserted from payment.* webhooks. ``invoice_url`` is
    Dodo's own (never constructed); ``failure_reason`` is Dodo's reason for a failed payment."""

    id: uuid.UUID
    occurred_at: datetime
    amount_minor: int
    currency: str  # ISO 4217
    status: PaymentStatusName
    invoice_url: str | None = None
    failure_reason: str | None = None


class PaymentList(ResponseModel):
    items: list[PaymentOut]
    next_cursor: str | None = None
