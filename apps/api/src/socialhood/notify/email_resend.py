"""Resend over the shared httpx client (T8.5).

POST https://api.resend.com/emails with ``Authorization: Bearer {RESEND_API_KEY}`` and
``Idempotency-Key: {message.idempotency_key}`` (at most 256 characters, remembered 24 h); body
{from: EMAIL_FROM, to: [to], subject, html, text, headers, tags: [{name, value}]} -> 200 {id}.

Errors come back as {statusCode, name, message}. Retryable (``EmailError(retryable=True)``):
timeouts and network errors, 5xx, 429 ``rate_limit_exceeded`` and 409
``concurrent_idempotent_requests`` (the same key is still being processed). Not retryable: other
4xx, including 429 ``daily_quota_exceeded`` / ``monthly_quota_exceeded`` (waiting a few minutes
won't help) and 409 ``invalid_idempotent_request`` (the key was used with a different body). The
API key and the recipient's address are never logged or put in an error message.
"""

from __future__ import annotations

from typing import Any

import httpx

from socialhood.notify.email import EmailError, EmailMessage, EmailNotConfigured, SentEmail
from socialhood.settings import Settings

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
MAX_IDEMPOTENCY_KEY = 256
RETRYABLE_NAMES = frozenset({"rate_limit_exceeded", "concurrent_idempotent_requests"})


class ResendEmailSender:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def _api_key(self) -> str:
        key = self._settings.resend_api_key
        if key is None or not key.get_secret_value():
            raise EmailNotConfigured()
        return key.get_secret_value()

    def request_body(self, message: EmailMessage) -> dict[str, Any]:
        body: dict[str, Any] = {
            "from": self._settings.email_from,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        if message.headers:
            body["headers"] = dict(message.headers)
        if message.tags:
            body["tags"] = [{"name": name, "value": value} for name, value in message.tags.items()]
        return body

    async def send(self, message: EmailMessage) -> SentEmail:
        if not message.idempotency_key or len(message.idempotency_key) > MAX_IDEMPOTENCY_KEY:
            raise EmailError("the idempotency key must be 1 to 256 characters")
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Idempotency-Key": message.idempotency_key,
            "User-Agent": "socialhood-api",
        }
        try:
            response = await self._http.post(
                RESEND_URL, json=self.request_body(message), headers=headers, timeout=TIMEOUT
            )
        except httpx.TimeoutException as error:
            raise EmailError("Resend timed out", retryable=True) from error
        except httpx.HTTPError as error:
            raise EmailError(
                f"Resend unreachable: {type(error).__name__}", retryable=True
            ) from error
        if response.is_success:
            email_id = _json(response).get("id")
            if not isinstance(email_id, str) or not email_id:
                raise EmailError("Resend answered without an email id", status=response.status_code)
            return SentEmail(provider_message_id=email_id)
        raise _error(response)


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _error(response: httpx.Response) -> EmailError:
    data = _json(response)
    status = response.status_code
    name = str(data.get("name") or "")
    # Resend's message describes the request (a field, the domain); it never echoes the key.
    detail = str(data.get("message") or response.reason_phrase or "error")[:300]
    retryable = status >= 500 or name in RETRYABLE_NAMES or (status == 429 and not name)
    return EmailError(
        f"Resend {status} {name or 'error'}: {detail}", status=status, retryable=retryable
    )
