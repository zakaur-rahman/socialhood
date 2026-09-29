"""An in-memory Dodo for tests and for running without Dodo (``DODO_PROVIDER=fake``).

- ``products`` holds the prices ``get_product_price`` returns; ``add_product`` adds one.
- ``subscriptions`` holds what ``get_subscription`` returns; ``add_subscription`` adds one (a test
  that simulates Dodo's side of a checkout adds the subscription, then posts the signed webhook).
- ``create_checkout`` records the params and returns a session on a ``.invalid`` host, so nothing
  can follow it anywhere; ``create_portal_session`` likewise.
- ``fail_next(error)`` makes the next call raise ``error`` (a DodoError, usually).
- Every call is recorded in ``calls`` as (method name, arguments).
"""

from __future__ import annotations

import dataclasses
import itertools
from collections import deque
from datetime import datetime
from typing import Any

from socialhood.billing.dodo import (
    CheckoutParams,
    CheckoutSession,
    DodoError,
    DodoSubscription,
    DodoSubscriptionStatus,
    ProductPrice,
)

FAKE_CHECKOUT_BASE = "https://checkout.dodo.invalid/session/"
FAKE_PORTAL_BASE = "https://portal.dodo.invalid/customer/"


class FakeDodo:
    def __init__(self) -> None:
        self.products: dict[str, ProductPrice] = {}
        self.subscriptions: dict[str, DodoSubscription] = {}
        self.checkouts: list[CheckoutParams] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._failures: deque[BaseException] = deque()
        self._ids = itertools.count(1)

    # ---------------------------------------------------------------- test setup

    def add_product(
        self,
        product_id: str,
        *,
        amount_minor: int = 99900,
        currency: str = "INR",
        trial_period_days: int = 7,
    ) -> ProductPrice:
        price = ProductPrice(
            product_id=product_id,
            amount_minor=amount_minor,
            currency=currency,
            interval="month",
            trial_period_days=trial_period_days,
        )
        self.products[product_id] = price
        return price

    def add_subscription(
        self,
        subscription_id: str | None = None,
        *,
        product_id: str,
        status: DodoSubscriptionStatus = "active",
        customer_id: str = "cus_fake",
        customer_email: str | None = None,
        previous_billing_date: datetime | None = None,
        next_billing_date: datetime | None = None,
        **values: Any,
    ) -> DodoSubscription:
        sub = DodoSubscription(
            subscription_id=subscription_id or f"sub_fake_{next(self._ids)}",
            status=status,
            product_id=product_id,
            customer_id=customer_id,
            customer_email=customer_email,
            previous_billing_date=previous_billing_date,
            next_billing_date=next_billing_date,
            **values,
        )
        self.subscriptions[sub.subscription_id] = sub
        return sub

    def fail_next(self, error: BaseException) -> None:
        self._failures.append(error)

    # ---------------------------------------------------------------- DodoClient

    def _record(self, name: str, **arguments: Any) -> None:
        self.calls.append((name, arguments))
        if self._failures:
            raise self._failures.popleft()

    def _subscription(self, subscription_id: str) -> DodoSubscription:
        sub = self.subscriptions.get(subscription_id)
        if sub is None:
            raise DodoError("subscription not found", status=404)
        return sub

    async def create_checkout(self, params: CheckoutParams) -> CheckoutSession:
        self._record("create_checkout", params=params)
        if params.product_id not in self.products:
            raise DodoError("product not found", status=404)
        self.checkouts.append(params)
        session_id = f"cks_fake_{next(self._ids)}"
        return CheckoutSession(session_id=session_id, checkout_url=FAKE_CHECKOUT_BASE + session_id)

    async def get_subscription(self, subscription_id: str) -> DodoSubscription:
        self._record("get_subscription", subscription_id=subscription_id)
        return self._subscription(subscription_id)

    async def set_cancel_at_period_end(
        self, subscription_id: str, cancel: bool
    ) -> DodoSubscription:
        self._record("set_cancel_at_period_end", subscription_id=subscription_id, cancel=cancel)
        sub = dataclasses.replace(
            self._subscription(subscription_id), cancel_at_next_billing_date=cancel
        )
        self.subscriptions[subscription_id] = sub
        return sub

    async def cancel_now(self, subscription_id: str) -> DodoSubscription:
        self._record("cancel_now", subscription_id=subscription_id)
        sub = dataclasses.replace(self._subscription(subscription_id), status="cancelled")
        self.subscriptions[subscription_id] = sub
        return sub

    async def create_portal_session(
        self, customer_id: str, *, return_url: str | None = None
    ) -> str:
        self._record("create_portal_session", customer_id=customer_id, return_url=return_url)
        return FAKE_PORTAL_BASE + customer_id

    async def get_product_price(self, product_id: str) -> ProductPrice:
        self._record("get_product_price", product_id=product_id)
        price = self.products.get(product_id)
        if price is None:
            raise DodoError("product not found", status=404)
        return price
