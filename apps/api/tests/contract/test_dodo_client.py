"""The Dodo client against recorded test-mode responses (T8.2; TR-BIL-01, TR-BIL-06): checkout,
subscriptions, cancel and resume, the customer portal, product prices, and errors. The fixtures in
tests/fixtures/dodo/ are real test-mode answers with the customer anonymised."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from socialhood.billing.dodo import CheckoutParams, DodoError, DodoNotConfigured
from socialhood.billing.dodo_http import HttpDodoClient, parse_subscription
from socialhood.settings import AppEnv, Settings

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dodo"
BASE = "https://test.dodopayments.com"
KEY = "fake-dodo-key-for-contract-tests"
PRO = "pdt_fvZrlRdUeVxrLfGIP6iYP"
SUB = "sub_YEaU8sj51t3HtOOyHktA7"
CUSTOMER = "cus_S8fu70OJYoHjkD1pRw4iH"
WORKSPACE = "0b4f6c2e-8f1d-4f4e-9b1a-3c2d1e0f9a8b"
RETURN_URL = "https://app.socialhood.com/w/acme/settings/billing?checkout=return"


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


def settings(**values: Any) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        database_url="postgresql+asyncpg://x/y",
        database_url_direct="postgresql://x/y",
        redis_url="redis://x",
        dodo_api_key=SecretStr(KEY),
        dodo_environment="test",
        **values,
    )


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def dodo(http: httpx.AsyncClient) -> HttpDodoClient:
    return HttpDodoClient(http, settings())


def params(trial: int | None = 7) -> CheckoutParams:
    return CheckoutParams(
        product_id=PRO,
        customer_email="owner@example.com",
        customer_name="Test Owner",
        return_url=RETURN_URL,
        metadata={"workspace_id": WORKSPACE},
        trial_period_days=trial,
    )


# ---------------------------------------------------------------- checkout (TR-BIL-01)


@respx.mock
async def test_checkout_sends_the_cart_customer_return_url_metadata_and_trial(
    dodo: HttpDodoClient,
) -> None:
    route = respx.post(f"{BASE}/checkouts").mock(
        return_value=httpx.Response(200, json=fixture("checkout_session.json"))
    )
    session = await dodo.create_checkout(params(7))

    assert session.session_id.startswith("cks_")
    assert session.checkout_url == (
        f"https://test.checkout.dodopayments.com/session/{session.session_id}"
    )
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert json.loads(request.content) == {
        "product_cart": [{"product_id": PRO, "quantity": 1}],
        "customer": {"email": "owner@example.com", "name": "Test Owner"},
        "return_url": RETURN_URL,
        "metadata": {"workspace_id": WORKSPACE},
        "subscription_data": {"trial_period_days": 7},
    }


@respx.mock
async def test_an_ineligible_checkout_sends_a_zero_day_trial(dodo: HttpDodoClient) -> None:
    """The product has its own 7-day trial; 0 removes it (verified live in test mode)."""
    route = respx.post(f"{BASE}/checkouts").mock(
        return_value=httpx.Response(200, json=fixture("checkout_session.json"))
    )
    await dodo.create_checkout(params(0))
    assert json.loads(route.calls.last.request.content)["subscription_data"] == {
        "trial_period_days": 0
    }


@respx.mock
async def test_an_unknown_product_is_a_refusal_not_a_retry(dodo: HttpDodoClient) -> None:
    respx.post(f"{BASE}/checkouts").mock(
        return_value=httpx.Response(422, json=fixture("error_invalid_request.json"))
    )
    with pytest.raises(DodoError) as refused:
        await dodo.create_checkout(params())
    assert (refused.value.status, refused.value.retryable) == (422, False)
    assert "INVALID_REQUEST_PARAMETERS" in str(refused.value)


# ---------------------------------------------------------------- subscriptions (TR-BIL-03, 06)


@respx.mock
async def test_get_subscription_reads_status_product_customer_and_period(
    dodo: HttpDodoClient,
) -> None:
    respx.get(f"{BASE}/subscriptions/{SUB}").mock(
        return_value=httpx.Response(200, json=fixture("subscription_active.json"))
    )
    sub = await dodo.get_subscription(SUB)

    assert (sub.subscription_id, sub.status, sub.product_id) == (SUB, "active", PRO)
    assert (sub.customer_id, sub.customer_email) == (CUSTOMER, "owner@example.com")
    assert sub.previous_billing_date == datetime(2026, 9, 11, 20, 23, 39, 604382, tzinfo=UTC)
    assert sub.next_billing_date == datetime(2026, 10, 11, 20, 23, 39, 604382, tzinfo=UTC)
    assert sub.created_at == datetime(2025, 11, 4, 20, 23, 16, 680711, tzinfo=UTC)
    assert sub.trial_period_days == 7
    assert not sub.in_trial(datetime(2026, 9, 30, tzinfo=UTC))  # the trial ended long ago
    assert sub.in_trial(datetime(2025, 11, 5, tzinfo=UTC))
    assert not sub.cancel_at_next_billing_date
    assert sub.metadata == {"workspace_id": WORKSPACE}


@respx.mock
async def test_a_cancelled_subscription_keeps_its_last_period(dodo: HttpDodoClient) -> None:
    sub_id = "sub_B7we3XD9yD80mPpFort54"
    respx.get(f"{BASE}/subscriptions/{sub_id}").mock(
        return_value=httpx.Response(200, json=fixture("subscription_cancelled.json"))
    )
    sub = await dodo.get_subscription(sub_id)
    assert sub.status == "cancelled"
    assert sub.cancelled_at is not None
    assert sub.next_billing_date is not None
    # Cancelled at the end of the period: Dodo stops at next_billing_date.
    assert sub.cancelled_at >= sub.next_billing_date


@respx.mock
async def test_cancel_at_period_end_and_resume_patch_the_flag(dodo: HttpDodoClient) -> None:
    route = respx.patch(f"{BASE}/subscriptions/{SUB}").mock(
        side_effect=[
            httpx.Response(200, json=fixture("subscription_cancel_scheduled.json")),
            httpx.Response(200, json=fixture("subscription_resumed.json")),
        ]
    )
    cancelled = await dodo.set_cancel_at_period_end(SUB, True)
    assert (cancelled.status, cancelled.cancel_at_next_billing_date) == ("active", True)
    resumed = await dodo.set_cancel_at_period_end(SUB, False)
    assert (resumed.status, resumed.cancel_at_next_billing_date) == ("active", False)
    assert [json.loads(c.request.content) for c in route.calls] == [
        {"cancel_at_next_billing_date": True},
        {"cancel_at_next_billing_date": False},
    ]


@respx.mock
async def test_cancel_now_sets_the_status(dodo: HttpDodoClient) -> None:
    body = {**fixture("subscription_active.json"), "status": "cancelled"}
    route = respx.patch(f"{BASE}/subscriptions/{SUB}").mock(
        return_value=httpx.Response(200, json=body)
    )
    assert (await dodo.cancel_now(SUB)).status == "cancelled"
    assert json.loads(route.calls.last.request.content) == {"status": "cancelled"}


@respx.mock
async def test_a_missing_subscription_is_not_found(dodo: HttpDodoClient) -> None:
    respx.get(f"{BASE}/subscriptions/sub_gone").mock(
        return_value=httpx.Response(404, json=fixture("error_not_found.json"))
    )
    with pytest.raises(DodoError) as missing:
        await dodo.get_subscription("sub_gone")
    assert missing.value.not_found
    assert not missing.value.retryable


def test_webhook_data_parses_like_the_api_object() -> None:
    data = {**fixture("subscription_active.json"), "payload_type": "Subscription"}
    assert parse_subscription(data) == parse_subscription(fixture("subscription_active.json"))
    odd = parse_subscription({**data, "status": "something_new"})
    assert odd.status == "pending"  # nothing acts on it


# ---------------------------------------------------------------- portal and prices


@respx.mock
async def test_the_portal_session_returns_the_link(dodo: HttpDodoClient) -> None:
    route = respx.post(f"{BASE}/customers/{CUSTOMER}/customer-portal/session").mock(
        return_value=httpx.Response(200, json=fixture("customer_portal_session.json"))
    )
    link = await dodo.create_portal_session(CUSTOMER, return_url=RETURN_URL)
    assert link.startswith("https://test.customer.dodopayments.com/session/")
    assert route.calls.last.request.url.params["return_url"] == RETURN_URL


@respx.mock
async def test_the_product_price_is_the_monthly_recurring_price(dodo: HttpDodoClient) -> None:
    respx.get(f"{BASE}/products/{PRO}").mock(
        return_value=httpx.Response(200, json=fixture("product_pro.json"))
    )
    price = await dodo.get_product_price(PRO)
    assert (price.product_id, price.amount_minor, price.currency) == (PRO, 1000, "USD")
    assert (price.interval, price.trial_period_days) == ("month", 7)


@respx.mock
async def test_a_yearly_price_is_refused(dodo: HttpDodoClient) -> None:
    product = fixture("product_pro.json")
    product["price"] = {**product["price"], "payment_frequency_interval": "Year"}
    respx.get(f"{BASE}/products/{PRO}").mock(return_value=httpx.Response(200, json=product))
    with pytest.raises(DodoError, match="monthly"):
        await dodo.get_product_price(PRO)


# ---------------------------------------------------------------- failures and safety


@respx.mock
@pytest.mark.parametrize("status", [429, 500, 503])
async def test_rate_limits_and_outages_are_retryable(dodo: HttpDodoClient, status: int) -> None:
    respx.get(f"{BASE}/subscriptions/{SUB}").mock(return_value=httpx.Response(status, json={}))
    with pytest.raises(DodoError) as failed:
        await dodo.get_subscription(SUB)
    assert (failed.value.status, failed.value.retryable) == (status, True)


@respx.mock
async def test_a_timeout_is_retryable(dodo: HttpDodoClient) -> None:
    respx.get(f"{BASE}/subscriptions/{SUB}").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(DodoError) as failed:
        await dodo.get_subscription(SUB)
    assert failed.value.retryable
    assert failed.value.status is None


async def test_without_a_key_nothing_is_sent(http: httpx.AsyncClient) -> None:
    client = HttpDodoClient(http, settings().model_copy(update={"dodo_api_key": None}))
    with respx.mock(assert_all_called=False) as router:
        route = router.route()
        with pytest.raises(DodoNotConfigured):
            await client.get_subscription(SUB)
        assert not route.called


async def test_ids_never_reach_a_url_path_unchecked(dodo: HttpDodoClient) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.route()
        for bad in ("../customers", "sub_1/../../x", "sub 1", ""):
            with pytest.raises(DodoError):
                await dodo.get_subscription(bad)
        assert not route.called


def test_live_mode_uses_the_live_host(http: httpx.AsyncClient) -> None:
    live = HttpDodoClient(http, settings().model_copy(update={"dodo_environment": "live_mode"}))
    assert live.base_url == "https://live.dodopayments.com"


async def test_the_key_and_urls_are_never_logged(
    dodo: HttpDodoClient, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    with respx.mock:
        respx.get(f"{BASE}/subscriptions/{SUB}").mock(
            return_value=httpx.Response(200, json=fixture("subscription_active.json"))
        )
        await dodo.get_subscription(SUB)
    captured = capsys.readouterr()
    logged = caplog.text + captured.out + captured.err
    assert KEY not in logged
    assert "dodopayments.com" not in logged
