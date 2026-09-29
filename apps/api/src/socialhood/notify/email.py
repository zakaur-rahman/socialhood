"""The email interface (T8.5, T8.7; FR-NOT-02, FR-NOT-04).

One ``EmailMessage`` is one rendered email to one address. ``idempotency_key`` is the outbox row's
dedupe key (models/notifications.EmailDelivery): Resend's ``Idempotency-Key`` header, so a retried
send within 24 h never delivers twice. ``headers`` carries List-Unsubscribe and
List-Unsubscribe-Post for the digest (RFC 8058 one-click).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str
    idempotency_key: str
    headers: Mapping[str, str] = field(default_factory=dict)
    tags: Mapping[str, str] = field(default_factory=dict)  # e.g. {"template": "post_failed"}


@dataclass(frozen=True)
class SentEmail:
    provider_message_id: str


class EmailError(Exception):
    """A send failed. ``retryable``: timeout, 429 or 5xx; otherwise the provider refused the
    message (a bad address, an unverified domain) and repeating it won't help."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class EmailNotConfigured(EmailError):
    """RESEND_API_KEY is not set."""

    def __init__(self, message: str = "Email is not configured") -> None:
        super().__init__(message, retryable=False)


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> SentEmail: ...
