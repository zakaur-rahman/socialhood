"""The Dodo Payments client interface (TR-BIL-01, TR-BIL-03, TR-BIL-06; T8.2).

Billing code depends on ``DodoClient`` only. ``billing/dodo_http.py`` is the real client: a thin
async client over the process's shared httpx client (the spec's "Dodo REST via httpx"), rather
than Dodo's generated SDK, so timeouts, logging and respx contract tests work as for Meta.
``billing/dodo_fake.py`` is the in-memory fake every test uses (``billing/registry.py``).

Dodo is the source of truth for subscription state (D9): nothing here changes a plan. Checkout and
the portal hand the owner to Dodo's hosted pages; the plan changes when the signed webhook arrives
(TR-BIL-02) or the reconcile job reads the subscription (TR-BIL-03).

Endpoints (base https://test.dodopayments.com or https://live.dodopayments.com by
DODO_ENVIRONMENT; ``Authorization: Bearer {DODO_API_KEY}``), checked against Dodo's API reference
on 2026-09-30:

- create_checkout: POST /checkouts {product_cart: [{product_id, quantity: 1}], customer: {email,
  name}, return_url, metadata: {workspace_id}, subscription_data: {trial_period_days}} ->
  {session_id, checkout_url}. The product carries its own trial (7 days on the test-mode Pro), so
  the trial is always sent: 7 when eligible, 0 otherwise (0 was verified live to remove it).
- get_subscription: GET /subscriptions/{id} -> subscription_id, status (pending, active, on_hold,
  paused, cancelled, failed, expired, past_due), product_id, customer {customer_id, email, name},
  created_at, previous_billing_date, next_billing_date, trial_period_days,
  cancel_at_next_billing_date, cancelled_at, expires_at, metadata. Webhook ``data`` for
  subscription.* events is the same object (payload_type "Subscription").
- set_cancel_at_period_end: PATCH /subscriptions/{id} {cancel_at_next_billing_date: bool}.
- cancel_now: PATCH /subscriptions/{id} {status: "cancelled"} (workspace deletion, F-16).
- create_portal_session: POST /customers/{customer_id}/customer-portal/session?return_url= ->
  {link}.
- get_product_price: GET /products/{id} -> price {type: recurring_price, price (minor units),
  currency, payment_frequency_interval (Month), trial_period_days}; cached for 1 h by the caller.

Recorded test-mode responses (anonymised) are in tests/fixtures/dodo/.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, Protocol

# Dodo's subscription statuses (GET /subscriptions/{id}).
DodoSubscriptionStatus = Literal[
    "pending", "active", "on_hold", "paused", "cancelled", "failed", "expired", "past_due"
]


class DodoError(Exception):
    """A Dodo call failed. ``retryable``: a timeout, 429 or 5xx (the caller may try again);
    otherwise Dodo refused the request (4xx) and repeating it won't help. ``not_found`` for 404."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable

    @property
    def not_found(self) -> bool:
        return self.status == 404


class DodoNotConfigured(DodoError):
    """DODO_API_KEY (or the product id asked for) is not set: the API answers 503."""

    def __init__(self, message: str = "Dodo Payments is not configured") -> None:
        super().__init__(message, status=None, retryable=False)


@dataclass(frozen=True)
class CheckoutParams:
    product_id: str
    customer_email: str
    customer_name: str | None
    return_url: str  # {WEB_BASE_URL}/w/{slug}/settings/billing?checkout=return
    metadata: Mapping[str, str]  # at least {"workspace_id": …}; comes back on every webhook
    trial_period_days: int | None = None  # set only when eligible (TR-BIL-05)


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    checkout_url: str


@dataclass(frozen=True)
class DodoSubscription:
    subscription_id: str
    status: DodoSubscriptionStatus
    product_id: str
    customer_id: str
    customer_email: str | None = None
    previous_billing_date: datetime | None = None  # the current period's start
    next_billing_date: datetime | None = None  # the current period's end
    trial_period_days: int = 0
    cancel_at_next_billing_date: bool = False
    cancelled_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    # When Dodo created it: a subscription is in its trial until created_at + trial_period_days
    # (trial_period_days stays set after the trial ends).
    created_at: datetime | None = None

    def trial_ends_at(self) -> datetime | None:
        start = self.created_at or self.previous_billing_date
        if self.trial_period_days <= 0 or start is None:
            return None
        return start + timedelta(days=self.trial_period_days)

    def in_trial(self, at: datetime) -> bool:
        ends = self.trial_ends_at()
        return ends is not None and at < ends


@dataclass(frozen=True)
class ProductPrice:
    product_id: str
    amount_minor: int
    currency: str  # ISO 4217
    interval: Literal["month"]
    trial_period_days: int = 0


class DodoClient(Protocol):
    async def create_checkout(self, params: CheckoutParams) -> CheckoutSession: ...

    async def get_subscription(self, subscription_id: str) -> DodoSubscription: ...

    async def set_cancel_at_period_end(
        self, subscription_id: str, cancel: bool
    ) -> DodoSubscription: ...

    async def cancel_now(self, subscription_id: str) -> DodoSubscription: ...

    async def create_portal_session(
        self, customer_id: str, *, return_url: str | None = None
    ) -> str: ...

    async def get_product_price(self, product_id: str) -> ProductPrice: ...
