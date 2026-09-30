"""The real Dodo Payments client (T8.2; TR-BIL-01, TR-BIL-06): thin async calls over the shared
httpx client. Endpoints and fields are in billing/dodo.py; recorded test-mode responses are in
tests/fixtures/dodo/.

429, 5xx, timeouts and network failures are ``DodoError(retryable=True)``; any other 4xx is
``DodoError(status=…)`` (a 404 is ``not_found``). Calls are logged by endpoint name with status and
duration, never the API key or the URL (SEC-10; httpx's own logger is held at WARNING, C-010).
Dodo's ISO dates become aware datetimes. ``parse_subscription`` also reads the ``data`` of
subscription.* webhook events, which is the same object.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast, get_args

import httpx

from socialhood.billing.dodo import (
    CheckoutParams,
    CheckoutSession,
    DodoError,
    DodoNotConfigured,
    DodoSubscription,
    DodoSubscriptionStatus,
    ProductPrice,
)
from socialhood.observability.logging import get_logger
from socialhood.settings import Settings

log = get_logger(__name__)

BASE_URLS = {
    "test": "https://test.dodopayments.com",
    "live": "https://live.dodopayments.com",
}
# Dodo ids are prefixed tokens (sub_…, cus_…, pdt_…); anything else never reaches a URL path.
_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_STATUSES = frozenset(get_args(DodoSubscriptionStatus))


def base_url(environment: str) -> str:
    """DODO_ENVIRONMENT ``live`` (or ``live_mode``) is live; anything else is test mode."""
    return BASE_URLS["live" if environment.removesuffix("_mode") == "live" else "test"]


# ---------------------------------------------------------------- parsing


def parse_datetime(value: Any) -> datetime | None:
    """Dodo's ISO 8601 times ("2026-10-11T20:23:39.604382Z") as aware datetimes."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def parse_subscription(data: Mapping[str, Any]) -> DodoSubscription:
    """A Subscription object (GET /subscriptions/{id}, PATCH answers, subscription.* webhook
    data). An unknown status reads as ``pending``, which nothing acts on."""
    subscription_id = _text(data.get("subscription_id"))
    product_id = _text(data.get("product_id"))
    if subscription_id is None or product_id is None:
        raise DodoError("subscription without an id or product")
    customer = _mapping(data.get("customer"))
    status = data.get("status")
    if status not in _STATUSES:
        log.warning("dodo_unknown_subscription_status", status=str(status)[:40])
        status = "pending"
    metadata = _mapping(data.get("metadata"))
    trial = data.get("trial_period_days")
    return DodoSubscription(
        subscription_id=subscription_id,
        status=cast(DodoSubscriptionStatus, status),
        product_id=product_id,
        customer_id=_text(customer.get("customer_id")) or "",
        customer_email=_text(customer.get("email")),
        previous_billing_date=parse_datetime(data.get("previous_billing_date")),
        next_billing_date=parse_datetime(data.get("next_billing_date")),
        trial_period_days=trial if isinstance(trial, int) and trial > 0 else 0,
        cancel_at_next_billing_date=data.get("cancel_at_next_billing_date") is True,
        cancelled_at=parse_datetime(data.get("cancelled_at")),
        expires_at=parse_datetime(data.get("expires_at")),
        metadata={str(k): str(v) for k, v in metadata.items() if v is not None},
        created_at=parse_datetime(data.get("created_at")),
    )


def parse_price(data: Mapping[str, Any]) -> ProductPrice:
    """A Product's monthly recurring price (GET /products/{id})."""
    product_id = _text(data.get("product_id"))
    price = _mapping(data.get("price"))
    amount = price.get("price")
    currency = price.get("currency")
    if (
        product_id is None
        or price.get("type") != "recurring_price"
        or str(price.get("payment_frequency_interval", "")).lower() != "month"
        or price.get("payment_frequency_count", 1) != 1
        or not isinstance(amount, int)
        or not isinstance(currency, str)
    ):
        raise DodoError("the product has no monthly recurring price")
    trial = price.get("trial_period_days")
    return ProductPrice(
        product_id=product_id,
        amount_minor=amount,
        currency=currency.upper(),
        interval="month",
        trial_period_days=trial if isinstance(trial, int) and trial > 0 else 0,
    )


def _checked_id(value: str) -> str:
    if not _ID.match(value):
        raise DodoError("not a Dodo id", status=400)
    return value


# ---------------------------------------------------------------- the client


class HttpDodoClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings
        self.base_url = base_url(settings.dodo_environment)

    def _api_key(self) -> str:
        key = self._settings.dodo_api_key
        if key is None or not key.get_secret_value():
            raise DodoNotConfigured()
        return key.get_secret_value()

    async def _call(
        self,
        method: str,
        path: str,
        *,
        endpoint: str,
        json: Any = None,
        params: Mapping[str, str] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self._api_key()}"}
        started = time.perf_counter()
        try:
            response = await self._http.request(
                method, self.base_url + path, headers=headers, json=json, params=params
            )
        except httpx.TimeoutException as error:
            self._log(endpoint, None, started, "timeout")
            raise DodoError("Dodo did not respond", retryable=True) from error
        except httpx.HTTPError as error:
            self._log(endpoint, None, started, "network")
            raise DodoError("Could not reach Dodo", retryable=True) from error
        try:
            body = response.json()
        except ValueError:
            body = None
        status = response.status_code
        if status >= 400:
            retryable = status == 429 or status >= 500
            code = body.get("code") if isinstance(body, dict) else None
            message = body.get("message") if isinstance(body, dict) else None
            self._log(endpoint, status, started, str(code or "error"))
            raise DodoError(
                f"Dodo refused {endpoint}: {code or status} {message or ''}".strip(),
                status=status,
                retryable=retryable,
            )
        self._log(endpoint, status, started, "ok")
        if not isinstance(body, dict):
            raise DodoError(f"Dodo answered {endpoint} without a JSON object", retryable=True)
        return body

    def _log(self, endpoint: str, status: int | None, started: float, outcome: str) -> None:
        log.info(
            "dodo_call",
            endpoint=endpoint,
            status_code=status,
            outcome=outcome,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    async def create_checkout(self, params: CheckoutParams) -> CheckoutSession:
        customer: dict[str, str] = {"email": params.customer_email}
        if params.customer_name:
            customer["name"] = params.customer_name
        payload: dict[str, Any] = {
            "product_cart": [{"product_id": params.product_id, "quantity": 1}],
            "customer": customer,
            "return_url": params.return_url,
            "metadata": dict(params.metadata),
        }
        if params.trial_period_days is not None:
            payload["subscription_data"] = {"trial_period_days": params.trial_period_days}
        body = await self._call("POST", "/checkouts", endpoint="create_checkout", json=payload)
        session_id, url = _text(body.get("session_id")), _text(body.get("checkout_url"))
        if session_id is None or url is None:
            raise DodoError("Dodo answered the checkout without a checkout_url")
        return CheckoutSession(session_id=session_id, checkout_url=url)

    async def get_subscription(self, subscription_id: str) -> DodoSubscription:
        path = f"/subscriptions/{_checked_id(subscription_id)}"
        return parse_subscription(await self._call("GET", path, endpoint="get_subscription"))

    async def set_cancel_at_period_end(
        self, subscription_id: str, cancel: bool
    ) -> DodoSubscription:
        path = f"/subscriptions/{_checked_id(subscription_id)}"
        body = await self._call(
            "PATCH",
            path,
            endpoint="set_cancel_at_period_end",
            json={"cancel_at_next_billing_date": cancel},
        )
        return parse_subscription(body)

    async def cancel_now(self, subscription_id: str) -> DodoSubscription:
        path = f"/subscriptions/{_checked_id(subscription_id)}"
        body = await self._call("PATCH", path, endpoint="cancel_now", json={"status": "cancelled"})
        return parse_subscription(body)

    async def create_portal_session(
        self, customer_id: str, *, return_url: str | None = None
    ) -> str:
        path = f"/customers/{_checked_id(customer_id)}/customer-portal/session"
        params = {"return_url": return_url} if return_url else None
        body = await self._call("POST", path, endpoint="create_portal_session", params=params)
        link = _text(body.get("link"))
        if link is None:
            raise DodoError("Dodo answered the portal session without a link")
        return link

    async def get_product_price(self, product_id: str) -> ProductPrice:
        path = f"/products/{_checked_id(product_id)}"
        return parse_price(await self._call("GET", path, endpoint="get_product"))
