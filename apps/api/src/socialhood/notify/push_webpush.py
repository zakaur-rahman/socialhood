"""Web Push with VAPID (T8.6; TR-FE-09) over the shared httpx client.

pywebpush encrypts (``WebPusher(subscription_info).encode(payload, "aes128gcm")``, RFC 8291) and
py_vapid signs the VAPID JWT (``Vapid.from_string(VAPID_PRIVATE_KEY).sign({"sub":
VAPID_SUBJECT, "aud": <endpoint origin>})``, RFC 8292); the POST to the endpoint goes through
httpx rather than pywebpush's requests or aiohttp session, so it shares the process's client and
respx can stand in for push services in tests. Headers: TTL, Urgency, Topic (from the tag),
Content-Encoding: aes128gcm, Authorization: vapid t=…, k=…. 201 (or any 2xx) is success; 404 or
410 raise ``PushGone``; 429, 5xx and network errors ``PushError(retryable=True)``; anything else
``PushError``.

Endpoints must belong to a known browser push service (``is_push_service``): the API POSTs to
whatever URL a browser registered, so an arbitrary https URL would let anyone make the API call
internal or third-party addresses (SSRF). The list covers Chrome, Edge, Opera and Samsung
(FCM), Firefox (Mozilla autopush), Safari on macOS and iOS 16.4+ (Apple) and legacy Edge (WNS).
"""

from __future__ import annotations

import base64
import hashlib
import time
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import httpx
from py_vapid import Vapid
from pywebpush import WebPusher

from socialhood.notify.push import PushError, PushGone, PushMessage, PushNotConfigured, PushTarget
from socialhood.settings import Settings

TIMEOUT = httpx.Timeout(10.0, connect=5.0)
JWT_LIFETIME_S = 12 * 3600  # RFC 8292 allows up to 24 h
TOPIC_CHARS = 32  # RFC 8030: at most 32 characters of the URL-safe base64 alphabet

# Host suffixes of the browser push services (the endpoint's host is one of these or below it).
PUSH_SERVICE_HOSTS = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "push.services.mozilla.com",
    "push.apple.com",
    "notify.windows.com",
)


def is_push_service(endpoint: str) -> bool:
    """An https URL on a known browser push service, on the default port."""
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme != "https" or port not in (None, 443) or parts.username or parts.password:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in PUSH_SERVICE_HOSTS)


def audience(endpoint: str) -> str:
    """The VAPID ``aud`` claim: the endpoint's origin."""
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}"


def topic(tag: str | None) -> str | None:
    """RFC 8030 Topic from a notification tag: a newer push with the same topic replaces one the
    push service still holds for an offline device."""
    if not tag:
        return None
    digest = hashlib.sha256(tag.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:TOPIC_CHARS]


@lru_cache(maxsize=4)
def _vapid(private_key: str) -> Any:
    return Vapid.from_string(private_key=private_key)


class WebPushSender:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def _private_key(self) -> str:
        key = self._settings.vapid_private_key
        if key is None or not key.get_secret_value() or not self._settings.vapid_public_key:
            raise PushNotConfigured()
        return key.get_secret_value()

    def authorization(self, endpoint: str, *, now: float | None = None) -> str:
        """``vapid t=<JWT>, k=<public key>`` for this endpoint's push service (RFC 8292)."""
        claims: dict[str, str | int] = {
            "sub": self._settings.vapid_subject,
            "aud": audience(endpoint),
            "exp": int(now if now is not None else time.time()) + JWT_LIFETIME_S,
        }
        try:
            headers: dict[str, str] = _vapid(self._private_key()).sign(claims)
        except PushNotConfigured:
            raise
        except Exception as error:  # a malformed key or subject: configuration, not the device
            raise PushNotConfigured(f"VAPID signing failed: {type(error).__name__}") from error
        return headers["Authorization"]

    def encrypt(self, target: PushTarget, payload: bytes) -> bytes:
        info = {"endpoint": target.endpoint, "keys": {"p256dh": target.p256dh, "auth": target.auth}}
        try:
            body: bytes = WebPusher(info).encode(payload, "aes128gcm")["body"]
        except Exception as error:  # keys that aren't a valid P-256 point or auth secret
            raise PushError(
                f"can't encrypt to this subscription: {type(error).__name__}"
            ) from error
        return body

    async def send(self, target: PushTarget, message: PushMessage) -> None:
        if not is_push_service(target.endpoint):
            raise PushError("not a browser push service endpoint")
        authorization = self.authorization(target.endpoint)
        body = self.encrypt(target, message.payload())
        headers = {
            "Authorization": authorization,
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(max(0, message.ttl_s)),
            "Urgency": message.urgency,
        }
        if (name := topic(message.tag)) is not None:
            headers["Topic"] = name
        try:
            response = await self._http.post(
                target.endpoint, content=body, headers=headers, timeout=TIMEOUT
            )
        except httpx.TimeoutException as error:
            raise PushError("push service timed out", retryable=True) from error
        except httpx.HTTPError as error:
            raise PushError(
                f"push service unreachable: {type(error).__name__}", retryable=True
            ) from error
        status = response.status_code
        if response.is_success:
            return
        if status in (404, 410):
            raise PushGone(target.endpoint, status)
        raise PushError(
            f"push service answered {status}",
            status=status,
            retryable=status == 429 or status >= 500,
        )
