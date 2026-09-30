"""The Resend client against Resend's documented API (T8.5): POST /emails with the Idempotency-Key,
the request body, and the answers it gives (https://resend.com/docs/api-reference/emails/send-email
and .../introduction#error-codes). respx stands in for api.resend.com; no test reaches it."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from socialhood.notify.email import EmailError, EmailMessage, EmailNotConfigured
from socialhood.notify.email_resend import RESEND_URL, ResendEmailSender
from socialhood.settings import Settings

API_KEY = "fake-resend-key-for-contract-tests"
RECIPIENT = "priya.owner@example.com"

# Resend's answers, as its API reference documents them.
SENT = {"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"}


def resend_error(status: int, name: str, message: str) -> dict[str, Any]:
    return {"statusCode": status, "name": name, "message": message}


def message(**values: Any) -> EmailMessage:
    defaults: dict[str, Any] = {
        "to": RECIPIENT,
        "subject": "Reconnect @maple.bakery",
        "html": "<p>Reconnect</p>",
        "text": "Reconnect",
        "idempotency_key": "ws1:notification:7d1e",
        "headers": {},
        "tags": {"template": "account_needs_reconnect"},
    }
    return EmailMessage(**{**defaults, **values})


@pytest.fixture
def settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(
        update={
            "resend_api_key": SecretStr(API_KEY),
            "email_from": "Social Hood <hello@socialhood.test>",
        }
    )


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


async def test_an_email_is_posted_with_its_idempotency_key(
    http: httpx.AsyncClient, settings: Settings
) -> None:
    email = message(
        idempotency_key="ws1:digest:2026-09-28:user1",
        headers={
            "List-Unsubscribe": "<https://api.socialhood.test/v1/digest/unsubscribe?token=t>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        tags={"template": "weekly_digest"},
    )
    with respx.mock(assert_all_called=True) as router:
        route = router.post(RESEND_URL).mock(return_value=httpx.Response(200, json=SENT))
        sent = await ResendEmailSender(http, settings).send(email)

    assert sent.provider_message_id == SENT["id"]
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert request.headers["idempotency-key"] == "ws1:digest:2026-09-28:user1"
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.content) == {
        "from": "Social Hood <hello@socialhood.test>",
        "to": [RECIPIENT],
        "subject": "Reconnect @maple.bakery",
        "html": "<p>Reconnect</p>",
        "text": "Reconnect",
        "headers": {
            "List-Unsubscribe": "<https://api.socialhood.test/v1/digest/unsubscribe?token=t>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        "tags": [{"name": "template", "value": "weekly_digest"}],
    }


async def test_no_headers_or_tags_are_left_out_of_the_body(
    http: httpx.AsyncClient, settings: Settings
) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.post(RESEND_URL).mock(return_value=httpx.Response(200, json=SENT))
        await ResendEmailSender(http, settings).send(message(headers={}, tags={}))
    body = json.loads(route.calls.last.request.content)
    assert "headers" not in body
    assert "tags" not in body


@pytest.mark.parametrize(
    ("status", "name", "retryable"),
    [
        (422, "validation_error", False),
        (422, "missing_required_field", False),
        (403, "invalid_api_key", False),
        (401, "missing_api_key", False),
        (400, "invalid_idempotency_key", False),
        (409, "invalid_idempotent_request", False),  # the key was used with another body
        (409, "concurrent_idempotent_requests", True),  # the same key is still in flight
        (429, "rate_limit_exceeded", True),
        (429, "daily_quota_exceeded", False),
        (429, "monthly_quota_exceeded", False),
        (500, "application_error", True),
        (503, "internal_server_error", True),
    ],
)
async def test_resend_errors_say_whether_to_retry(
    http: httpx.AsyncClient, settings: Settings, status: int, name: str, retryable: bool
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(RESEND_URL).mock(
            return_value=httpx.Response(status, json=resend_error(status, name, "Try again."))
        )
        with pytest.raises(EmailError) as raised:
            await ResendEmailSender(http, settings).send(message())
    error = raised.value
    assert (error.status, error.retryable) == (status, retryable)
    assert name in str(error)
    assert API_KEY not in str(error)
    assert RECIPIENT not in str(error)


async def test_an_answer_that_isnt_json_is_still_an_error(
    http: httpx.AsyncClient, settings: Settings
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(RESEND_URL).mock(return_value=httpx.Response(502, text="<html>Bad gateway"))
        with pytest.raises(EmailError) as raised:
            await ResendEmailSender(http, settings).send(message())
    assert (raised.value.status, raised.value.retryable) == (502, True)


async def test_a_success_without_an_id_is_an_error(
    http: httpx.AsyncClient, settings: Settings
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(RESEND_URL).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(EmailError, match="without an email id"):
            await ResendEmailSender(http, settings).send(message())


@pytest.mark.parametrize(
    "failure", [httpx.ConnectTimeout("slow"), httpx.ReadTimeout("slow"), httpx.ConnectError("down")]
)
async def test_timeouts_and_network_errors_are_retried(
    http: httpx.AsyncClient, settings: Settings, failure: Exception
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(RESEND_URL).mock(side_effect=failure)
        with pytest.raises(EmailError) as raised:
            await ResendEmailSender(http, settings).send(message())
    assert raised.value.retryable


async def test_without_an_api_key_nothing_is_sent(
    http: httpx.AsyncClient, api_settings: Settings
) -> None:
    unconfigured = api_settings.model_copy(update={"resend_api_key": None})
    with respx.mock(assert_all_called=False) as router:
        route = router.post(RESEND_URL)
        with pytest.raises(EmailNotConfigured):
            await ResendEmailSender(http, unconfigured).send(message())
    assert not route.called


async def test_an_idempotency_key_over_256_characters_is_refused(
    http: httpx.AsyncClient, settings: Settings
) -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.post(RESEND_URL)
        with pytest.raises(EmailError, match="256"):
            await ResendEmailSender(http, settings).send(message(idempotency_key="k" * 257))
    assert not route.called
