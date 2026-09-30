"""The P8 contract's shared names agree with each other (TR-BIL-01…06, FR-NOT-01…04, TR-FE-09):
the 402 codes and their plan-limit fields, the API's plan and status names are the stored ones,
notification preferences match the stored defaults and the push events, the push payload the
service worker reads, the fakes behave like the providers they replace, production refuses the
fakes, every P8 route is in the API, and the P8 job modules are registered."""

from __future__ import annotations

import importlib
import json
import uuid
from typing import Any, get_args

import httpx
import pytest

from socialhood.billing.dodo import CheckoutParams, DodoError
from socialhood.billing.dodo_fake import FAKE_CHECKOUT_BASE, FakeDodo
from socialhood.billing.dodo_http import HttpDodoClient, base_url
from socialhood.billing.registry import get_dodo, use_dodo
from socialhood.errors import (
    ERROR_CODES,
    PAYMENT_REQUIRED_CODES,
    ApiError,
    PlanLimit,
    problem_body,
)
from socialhood.jobs.app import TASK_MODULES
from socialhood.main import create_app
from socialhood.models.billing import PaymentStatus, Plan, SubscriptionStatus
from socialhood.models.identity import DEFAULT_NOTIFICATION_PREFS
from socialhood.models.notifications import (
    EMAIL_TYPES,
    PUSH_EVENT_OF_TYPE,
    EmailTemplate,
    NotificationChannel,
    NotificationType,
    PushEvent,
)
from socialhood.notify.email import EmailMessage
from socialhood.notify.email_fake import FakeEmail
from socialhood.notify.email_resend import ResendEmailSender
from socialhood.notify.push import MAX_PAYLOAD_BYTES, PushGone, PushMessage, PushTarget
from socialhood.notify.push_fake import FakePush
from socialhood.notify.push_webpush import WebPushSender
from socialhood.notify.registry import (
    get_email_sender,
    get_push_sender,
    use_email_sender,
    use_push_sender,
)
from socialhood.schemas.billing import PaidPlanName, PlanName, SubscriptionStatusName
from socialhood.schemas.notifications import NotificationPreferences, PushPreferences
from socialhood.settings import ConfigurationError, Settings
from tests.unit.test_settings import complete_production

# operation id -> (method, path, pending task; None once built): §2.15's billing and
# notification-settings rows, plus the push configuration and the public plan list. Two tables,
# one per task owner, so each clears its own markers without touching the other's lines.

# Billing (T8.2).
BILLING_ROUTES = {
    "get_billing": ("get", "/v1/w/{wid}/billing", None),
    "create_billing_checkout": ("post", "/v1/w/{wid}/billing/checkout", None),
    "create_billing_portal": ("post", "/v1/w/{wid}/billing/portal", None),
    "cancel_billing": ("post", "/v1/w/{wid}/billing/cancel", None),
    "resume_billing": ("post", "/v1/w/{wid}/billing/resume", None),
    "list_billing_plans": ("get", "/v1/billing/plans", None),
}


# Notification settings (T8.6, T8.7).
NOTIFICATION_ROUTES = {
    "get_notification_preferences": ("get", "/v1/w/{wid}/notification-preferences", "T8.6"),
    "update_notification_preferences": ("put", "/v1/w/{wid}/notification-preferences", "T8.6"),
    "get_push_config": ("get", "/v1/push/config", None),
    "create_push_subscription": ("post", "/v1/me/push-subscriptions", "T8.6"),
    "delete_push_subscription": ("delete", "/v1/me/push-subscriptions", "T8.6"),
    "unsubscribe_digest": ("post", "/v1/digest/unsubscribe", "T8.7"),
}

P8_ROUTES = {**BILLING_ROUTES, **NOTIFICATION_ROUTES}

P8_JOB_MODULES = (
    "socialhood.jobs.tasks.billing",
    "socialhood.jobs.tasks.emails",
    "socialhood.jobs.tasks.push",
    "socialhood.jobs.tasks.digests",
)


# ---------------------------------------------------------------- errors


def test_the_402_codes_are_the_specs() -> None:
    assert PAYMENT_REQUIRED_CODES == ("entitlement_required", "quota_exceeded")
    assert {code for code, spec in ERROR_CODES.items() if spec.status == 402} == set(
        PAYMENT_REQUIRED_CODES
    )


def test_a_402_names_its_entitlement_and_limit() -> None:
    body = problem_body(
        "quota_exceeded",
        detail="Your plan includes 3 active automations.",
        request_id="r1",
        plan_limit=PlanLimit(entitlement="active_automations", limit=3),
    )
    assert body["status"] == 402
    assert (body["entitlement"], body["limit"]) == ("active_automations", 3)
    feature = problem_body(
        "entitlement_required",
        detail="Auto mode is part of Pro.",
        request_id=None,
        plan_limit=PlanLimit(entitlement="ai_modes"),
    )
    assert (feature["entitlement"], feature["limit"]) == ("ai_modes", None)
    assert "entitlement" not in problem_body("quota_exceeded", detail=None, request_id=None)
    with pytest.raises(ValueError, match="only for 402"):
        ApiError("conflict", plan_limit=PlanLimit(entitlement="members"))


def test_the_problem_schema_documents_the_plan_limit_fields(api_settings: Any) -> None:
    problem = create_app(api_settings).openapi()["components"]["schemas"]["Problem"]
    assert {"entitlement", "limit"} <= set(problem["properties"])
    assert "entitlement" not in problem["required"]


# ---------------------------------------------------------------- names


def test_api_names_are_the_stored_ones() -> None:
    assert set(get_args(PlanName)) == set(Plan)
    assert set(get_args(PaidPlanName)) == set(Plan) - {Plan.FREE}
    assert set(get_args(SubscriptionStatusName)) == set(SubscriptionStatus)
    assert {status.value for status in PaymentStatus} == {
        "succeeded",
        "failed",
        "refunded",
        "pending",
    }


def test_preferences_match_the_stored_defaults_and_the_push_events() -> None:
    assert set(PushPreferences.model_fields) == set(PushEvent)
    assert NotificationPreferences.model_validate(DEFAULT_NOTIFICATION_PREFS).model_dump() == (
        DEFAULT_NOTIFICATION_PREFS
    )
    assert set(DEFAULT_NOTIFICATION_PREFS["push"]) == set(PushEvent)


def test_every_push_event_and_email_has_a_notification_type() -> None:
    types = {t.value for t in NotificationType}
    assert set(PUSH_EVENT_OF_TYPE) <= types
    assert set(PUSH_EVENT_OF_TYPE.values()) == set(PushEvent)
    assert types >= EMAIL_TYPES
    # A notification email uses the template named after its type; the digest has its own.
    assert {t.value for t in EmailTemplate} == EMAIL_TYPES | {"weekly_digest"}
    assert {c.value for c in NotificationChannel} == {"in_app", "email", "push"}


# ---------------------------------------------------------------- push payload


def test_the_push_payload_is_what_the_service_worker_reads() -> None:
    message = PushMessage(
        title="Priya needs you",
        body="Auto handed this conversation to you.",
        url="/w/acme/inbox/5f0c3c1e",
        tag="conversation:5f0c3c1e",
    )
    assert json.loads(message.payload()) == {
        "title": "Priya needs you",
        "body": "Auto handed this conversation to you.",
        "url": "/w/acme/inbox/5f0c3c1e",
        "tag": "conversation:5f0c3c1e",
    }
    with pytest.raises(ValueError, match="3000"):
        PushMessage(title="t", body="x" * MAX_PAYLOAD_BYTES, url="/app").payload()


# ---------------------------------------------------------------- fakes


async def test_the_fake_dodo_behaves_like_dodo() -> None:
    dodo = FakeDodo()
    dodo.add_product("pdt_pro", amount_minor=99900, currency="INR")
    params = CheckoutParams(
        product_id="pdt_pro",
        customer_email="owner@example.com",
        customer_name="Owner",
        return_url="http://web.test/w/acme/settings/billing?checkout=return",
        metadata={"workspace_id": str(uuid.uuid4())},
        trial_period_days=7,
    )
    session = await dodo.create_checkout(params)
    assert session.checkout_url.startswith(FAKE_CHECKOUT_BASE)
    assert dodo.checkouts == [params]
    with pytest.raises(DodoError) as missing:
        await dodo.create_checkout(CheckoutParams(**{**params.__dict__, "product_id": "nope"}))
    assert missing.value.not_found

    sub = dodo.add_subscription(product_id="pdt_pro", customer_id="cus_1")
    assert (
        await dodo.set_cancel_at_period_end(sub.subscription_id, True)
    ).cancel_at_next_billing_date
    assert (await dodo.get_subscription(sub.subscription_id)).cancel_at_next_billing_date
    assert (await dodo.cancel_now(sub.subscription_id)).status == "cancelled"
    assert (await dodo.get_product_price("pdt_pro")).amount_minor == 99900
    assert (await dodo.create_portal_session("cus_1")).endswith("cus_1")

    dodo.fail_next(DodoError("down", status=503, retryable=True))
    with pytest.raises(DodoError) as down:
        await dodo.get_subscription(sub.subscription_id)
    assert down.value.retryable
    assert [name for name, _ in dodo.calls][-1] == "get_subscription"


async def test_the_fake_email_sends_once_per_idempotency_key() -> None:
    email = FakeEmail()
    message = EmailMessage(
        to="owner@example.com",
        subject="Reconnect @maple.bakery",
        html="<p>Reconnect</p>",
        text="Reconnect",
        idempotency_key="notification:1",
    )
    first = await email.send(message)
    again = await email.send(message)
    assert first == again
    assert email.outbox == [message]
    assert email.sent_to("owner@example.com") == [message]


async def test_the_fake_push_reports_gone_subscriptions() -> None:
    push = FakePush()
    target = PushTarget(endpoint="https://push.example.test/1", p256dh="k", auth="a")
    message = PushMessage(title="New lead", body="Priya asked about prices", url="/w/acme/inbox/1")
    await push.send(target, message)
    assert push.sent_to(target.endpoint) == [message]
    push.gone.add(target.endpoint)
    with pytest.raises(PushGone) as gone:
        await push.send(target, message)
    assert gone.value.status == 410


# ---------------------------------------------------------------- registry and settings


async def test_the_registries_pick_the_real_adapters_or_a_tests_fake(
    api_settings: Settings,
) -> None:
    async with httpx.AsyncClient() as http:
        await _registries_pick(http, api_settings)


async def _registries_pick(http: httpx.AsyncClient, api_settings: Settings) -> None:
    # tests/support installs a fake for every test; outside it, the settings decide.
    with use_dodo(FakeDodo()) as fake_dodo:
        assert get_dodo(http, api_settings) is fake_dodo
    with use_email_sender(FakeEmail()) as fake_email:
        assert get_email_sender(http, api_settings) is fake_email
    with use_push_sender(FakePush()) as fake_push:
        assert get_push_sender(http, api_settings) is fake_push


async def test_without_an_override_the_settings_choose(api_settings: Settings) -> None:
    async with httpx.AsyncClient() as http:
        _settings_choose(http, api_settings)


def _settings_choose(http: httpx.AsyncClient, api_settings: Settings) -> None:
    from socialhood.billing import registry as billing_registry
    from socialhood.notify import registry as notify_registry

    saved = (
        list(billing_registry._override),
        list(notify_registry._email_override),
        list(notify_registry._push_override),
    )
    billing_registry._override.clear()
    notify_registry._email_override.clear()
    notify_registry._push_override.clear()
    try:
        assert isinstance(get_dodo(http, api_settings), HttpDodoClient)
        assert isinstance(get_email_sender(http, api_settings), ResendEmailSender)
        assert isinstance(get_push_sender(http, api_settings), WebPushSender)
        fakes = api_settings.model_copy(
            update={"dodo_provider": "fake", "email_provider": "fake", "push_provider": "fake"}
        )
        assert isinstance(get_dodo(http, fakes), FakeDodo)
        assert isinstance(get_email_sender(http, fakes), FakeEmail)
        assert isinstance(get_push_sender(http, fakes), FakePush)
    finally:
        billing_registry._override[:] = saved[0]
        notify_registry._email_override[:] = saved[1]
        notify_registry._push_override[:] = saved[2]


@pytest.mark.parametrize("name", ["dodo_provider", "email_provider", "push_provider"])
def test_production_refuses_the_fakes(name: str) -> None:
    values = complete_production()
    values[name] = "fake"
    with pytest.raises(ConfigurationError, match=name.upper()):
        Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_dodo_environment_picks_the_base_url() -> None:
    assert base_url("test") == "https://test.dodopayments.com"
    assert base_url("live") == "https://live.dodopayments.com"
    assert base_url("live_mode") == "https://live.dodopayments.com"
    assert base_url("anything else") == "https://test.dodopayments.com"


# ---------------------------------------------------------------- routes and jobs


def test_every_p8_route_is_in_the_api(api_settings: Any) -> None:
    openapi = create_app(api_settings).openapi()
    found = {
        operation["operationId"]: (method, path, operation.get("x-pending"))
        for path, operations in openapi["paths"].items()
        for method, operation in operations.items()
        if operation.get("operationId") in P8_ROUTES
    }
    assert found == P8_ROUTES
    # Webhooks are not part of the product API's contract.
    assert not any(path.startswith("/webhooks") for path in openapi["paths"])
    assert "201" in openapi["paths"]["/v1/me/push-subscriptions"]["post"]["responses"]


def test_the_p8_job_modules_are_registered() -> None:
    for module in P8_JOB_MODULES:
        assert module in TASK_MODULES
        importlib.import_module(module)
