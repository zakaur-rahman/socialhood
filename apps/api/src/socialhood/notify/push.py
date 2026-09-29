"""The Web Push interface (T8.6; FR-NOT-03, TR-FE-09).

``PushMessage.payload()`` is the contract with the web's service worker (apps/web/public/sw.js):
a JSON object {"title", "body", "url", "tag"}. ``url`` is a same-origin app path to open on tap
(``/w/{slug}`` + the notification's workspace-relative link, e.g. ``/w/acme/inbox/{id}``);
``tag`` groups notifications so a newer one replaces an older one on the device. The payload
stays under 3 KB (push services cap it near 4 KB after encryption).

A push service answering 404 or 410 means the subscription is gone: ``send`` raises
``PushGone`` and the caller deletes the row (TR-FE-09). ``PushError(retryable=True)`` for 429,
5xx and timeouts; other failures are not retryable and count towards disabling the row.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Protocol

MAX_PAYLOAD_BYTES = 3000


@dataclass(frozen=True)
class PushTarget:
    """One browser's subscription (push_subscriptions): where to send and its keys."""

    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    url: str  # same-origin path opened on tap, e.g. /w/acme/inbox/{conversation_id}
    tag: str | None = None
    ttl_s: int = 24 * 3600  # how long the push service keeps it for an offline device
    urgency: Literal["very-low", "low", "normal", "high"] = "normal"

    def payload(self) -> bytes:
        """The JSON the service worker reads (``event.data.json()``)."""
        data = {"title": self.title, "body": self.body, "url": self.url, "tag": self.tag}
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        if len(encoded) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"push payload is {len(encoded)} bytes; the limit is 3000")
        return encoded


class PushError(Exception):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class PushGone(PushError):
    """404 or 410: the browser dropped the subscription; delete it."""

    def __init__(self, endpoint: str, status: int) -> None:
        super().__init__("push subscription is gone", status=status, retryable=False)
        self.endpoint = endpoint


class PushNotConfigured(PushError):
    """VAPID_PUBLIC_KEY or VAPID_PRIVATE_KEY is not set."""

    def __init__(self, message: str = "Web Push is not configured") -> None:
        super().__init__(message, retryable=False)


class PushSender(Protocol):
    async def send(self, target: PushTarget, message: PushMessage) -> None: ...
