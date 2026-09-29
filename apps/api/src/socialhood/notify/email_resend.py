"""Resend over the shared httpx client (T8.5).

POST https://api.resend.com/emails with ``Authorization: Bearer {RESEND_API_KEY}`` and
``Idempotency-Key: {message.idempotency_key}`` (at most 256 characters, remembered 24 h); body
{from: EMAIL_FROM, to: [to], subject, html, text, headers, tags: [{name, value}]} -> {id}.
429 and 5xx are ``EmailError(retryable=True)``, other 4xx not retryable. The API key and the
recipient's address are never logged.
"""

from __future__ import annotations

import httpx

from socialhood.notify.email import EmailMessage, EmailNotConfigured, SentEmail
from socialhood.settings import Settings

RESEND_URL = "https://api.resend.com/emails"


class ResendEmailSender:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def _api_key(self) -> str:
        key = self._settings.resend_api_key
        if key is None or not key.get_secret_value():
            raise EmailNotConfigured()
        return key.get_secret_value()

    async def send(self, message: EmailMessage) -> SentEmail:
        raise NotImplementedError("T8.5")
