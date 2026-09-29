"""The real Dodo Payments client (T8.2; TR-BIL-01, TR-BIL-06): thin async calls over the shared
httpx client. Endpoints and fields are in billing/dodo.py.

T8.2 fills the method bodies: map 429, 5xx and timeouts to ``DodoError(retryable=True)`` and
other 4xx to ``DodoError(status=…)``; never log the API key or full request URLs (SEC-10); parse
Dodo's ISO dates to aware datetimes. Contract tests replay recorded test-mode responses with respx.
"""

from __future__ import annotations

import httpx

from socialhood.billing.dodo import (
    CheckoutParams,
    CheckoutSession,
    DodoNotConfigured,
    DodoSubscription,
    ProductPrice,
)
from socialhood.settings import Settings

BASE_URLS = {
    "test": "https://test.dodopayments.com",
    "live": "https://live.dodopayments.com",
}


def base_url(environment: str) -> str:
    """DODO_ENVIRONMENT ``live`` (or ``live_mode``) is live; anything else is test mode."""
    return BASE_URLS["live" if environment.removesuffix("_mode") == "live" else "test"]


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

    async def create_checkout(self, params: CheckoutParams) -> CheckoutSession:
        raise NotImplementedError("T8.2")

    async def get_subscription(self, subscription_id: str) -> DodoSubscription:
        raise NotImplementedError("T8.2")

    async def set_cancel_at_period_end(
        self, subscription_id: str, cancel: bool
    ) -> DodoSubscription:
        raise NotImplementedError("T8.2")

    async def cancel_now(self, subscription_id: str) -> DodoSubscription:
        raise NotImplementedError("T8.2")

    async def create_portal_session(
        self, customer_id: str, *, return_url: str | None = None
    ) -> str:
        raise NotImplementedError("T8.2")

    async def get_product_price(self, product_id: str) -> ProductPrice:
        raise NotImplementedError("T8.2")
