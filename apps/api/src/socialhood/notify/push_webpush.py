"""Web Push with VAPID (T8.6; TR-FE-09) over the shared httpx client.

pywebpush encrypts (``WebPusher(subscription_info).encode(payload, "aes128gcm")``, RFC 8291) and
py_vapid signs the VAPID JWT (``Vapid.from_string(VAPID_PRIVATE_KEY).sign({"sub":
VAPID_SUBJECT, "aud": <endpoint origin>})``, RFC 8292); the POST to the endpoint goes through
httpx rather than pywebpush's requests or aiohttp session, so it shares the process's timeouts
and respx can stand in for push services in tests. Headers: TTL, Urgency, Topic (the tag),
Content-Encoding: aes128gcm, Authorization: vapid t=…, k=…. 201 is success; 404 or 410 raise
``PushGone``; 429 and 5xx ``PushError(retryable=True)``.
"""

from __future__ import annotations

import httpx

from socialhood.notify.push import PushMessage, PushNotConfigured, PushTarget
from socialhood.settings import Settings


class WebPushSender:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    def _private_key(self) -> str:
        key = self._settings.vapid_private_key
        if key is None or not key.get_secret_value() or not self._settings.vapid_public_key:
            raise PushNotConfigured()
        return key.get_secret_value()

    async def send(self, target: PushTarget, message: PushMessage) -> None:
        raise NotImplementedError("T8.6")
