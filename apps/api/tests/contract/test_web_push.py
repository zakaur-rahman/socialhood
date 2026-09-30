"""The Web Push sender against the protocols it speaks (T8.6; TR-FE-09): RFC 8030 (the POST, TTL,
Urgency, Topic; 201 created, 404 and 410 gone), RFC 8291 (aes128gcm encryption to the browser's
keys: the test decrypts with the browser's private key) and RFC 8292 (the VAPID JWT, verified
with py_vapid). respx stands in for the push services; no test reaches one."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import http_ece
import httpx
import jwt
import pytest
import respx
from py_vapid import Vapid02
from pydantic import SecretStr

from socialhood.notify.push import PushError, PushGone, PushMessage, PushNotConfigured, PushTarget
from socialhood.notify.push_webpush import WebPushSender, is_push_service, topic
from socialhood.settings import Settings
from tests.support.notify import AUTH, BROWSER_KEY, P256DH, VAPID_PUBLIC_KEY

ENDPOINT = "https://fcm.googleapis.com/fcm/send/dXnQ-test-subscription"
TARGET = PushTarget(endpoint=ENDPOINT, p256dh=P256DH, auth=AUTH)
MESSAGE = PushMessage(
    title="Priya needs you",
    body="AI didn't reply: she asked for a refund.",
    url="/w/maple/inbox/5f0c3c1e-8a3c-4a52-9a53-0e3b1c1f2a10",
    tag="conversation:5f0c3c1e-8a3c-4a52-9a53-0e3b1c1f2a10",
    urgency="high",
)


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.mark.parametrize(
    ("endpoint", "allowed"),
    [
        ("https://fcm.googleapis.com/fcm/send/abc", True),
        ("https://android.googleapis.com/gcm/send/abc", True),
        ("https://updates.push.services.mozilla.com/wpush/v2/abc", True),
        ("https://web.push.apple.com/QGuQyavXutnMH-abc", True),
        ("https://wns2-par02p.notify.windows.com/w/?token=abc", True),
        ("https://FCM.googleapis.com./fcm/send/abc", True),
        ("http://fcm.googleapis.com/fcm/send/abc", False),  # not https
        ("https://fcm.googleapis.com:8443/fcm/send/abc", False),  # not the default port
        ("https://user:pw@fcm.googleapis.com/fcm/send/abc", False),
        ("https://evilfcm.googleapis.com.attacker.test/x", False),
        ("https://notfcm.googleapis.com.example/x", False),
        ("https://169.254.169.254/latest/meta-data", False),
        ("https://localhost/push", False),
        ("https://api.socialhood.com/v1/internal", False),
        ("not a url", False),
    ],
)
def test_only_browser_push_services_are_endpoints(endpoint: str, allowed: bool) -> None:
    assert is_push_service(endpoint) is allowed


def test_a_topic_is_32_url_safe_characters() -> None:
    name = topic(MESSAGE.tag)
    assert name is not None
    assert len(name) == 32
    assert set(name) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert topic(MESSAGE.tag) == name  # the same tag, the same topic
    assert topic(None) is None


async def test_a_push_is_encrypted_to_the_browser_and_signed_with_vapid(
    http: httpx.AsyncClient, api_settings: Settings
) -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.post(ENDPOINT).mock(return_value=httpx.Response(201))
        await WebPushSender(http, api_settings).send(TARGET, MESSAGE)

    request = route.calls.last.request
    headers = request.headers
    assert headers["content-encoding"] == "aes128gcm"
    assert headers["content-type"] == "application/octet-stream"
    assert headers["ttl"] == str(24 * 3600)
    assert headers["urgency"] == "high"
    assert headers["topic"] == topic(MESSAGE.tag)

    # RFC 8291: only the browser's private key and auth secret open the payload.
    plain = http_ece.decrypt(
        request.content, private_key=BROWSER_KEY, auth_secret=_unb64(AUTH), version="aes128gcm"
    )
    assert json.loads(plain) == {
        "title": "Priya needs you",
        "body": "AI didn't reply: she asked for a refund.",
        "url": "/w/maple/inbox/5f0c3c1e-8a3c-4a52-9a53-0e3b1c1f2a10",
        "tag": "conversation:5f0c3c1e-8a3c-4a52-9a53-0e3b1c1f2a10",
    }

    # RFC 8292: vapid t=<JWT signed by our key>, k=<our public key>.
    authorization = headers["authorization"]
    assert authorization.startswith("vapid t=")
    assert Vapid02.verify(authorization)
    params = dict(part.split("=", 1) for part in authorization.split(" ", 1)[1].split(","))
    assert params["k"] == VAPID_PUBLIC_KEY
    claims: dict[str, Any] = jwt.decode(params["t"], options={"verify_signature": False})
    assert claims["aud"] == "https://fcm.googleapis.com"
    assert claims["sub"] == api_settings.vapid_subject
    assert time.time() < claims["exp"] <= time.time() + 24 * 3600


@pytest.mark.parametrize("status", [404, 410])
async def test_a_gone_subscription_raises_push_gone(
    http: httpx.AsyncClient, api_settings: Settings, status: int
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(ENDPOINT).mock(return_value=httpx.Response(status))
        with pytest.raises(PushGone) as raised:
            await WebPushSender(http, api_settings).send(TARGET, MESSAGE)
    assert (raised.value.status, raised.value.endpoint) == (status, ENDPOINT)


@pytest.mark.parametrize(
    ("status", "retryable"), [(400, False), (403, False), (413, False), (429, True), (503, True)]
)
async def test_other_answers_say_whether_to_retry(
    http: httpx.AsyncClient, api_settings: Settings, status: int, retryable: bool
) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(ENDPOINT).mock(return_value=httpx.Response(status))
        with pytest.raises(PushError) as raised:
            await WebPushSender(http, api_settings).send(TARGET, MESSAGE)
    assert not isinstance(raised.value, PushGone)
    assert (raised.value.status, raised.value.retryable) == (status, retryable)


async def test_a_timeout_is_retried(http: httpx.AsyncClient, api_settings: Settings) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(ENDPOINT).mock(side_effect=httpx.ReadTimeout("slow"))
        with pytest.raises(PushError) as raised:
            await WebPushSender(http, api_settings).send(TARGET, MESSAGE)
    assert raised.value.retryable


async def test_an_endpoint_outside_the_push_services_is_never_called(
    http: httpx.AsyncClient, api_settings: Settings
) -> None:
    target = PushTarget(endpoint="https://internal.example.test/hook", p256dh=P256DH, auth=AUTH)
    with respx.mock(assert_all_called=False) as router:
        route = router.post(target.endpoint)
        with pytest.raises(PushError, match="not a browser push service"):
            await WebPushSender(http, api_settings).send(target, MESSAGE)
    assert not route.called


async def test_bad_subscription_keys_are_the_devices_fault(
    http: httpx.AsyncClient, api_settings: Settings
) -> None:
    target = PushTarget(endpoint=ENDPOINT, p256dh="bm90LWEta2V5", auth=AUTH)
    with respx.mock(assert_all_called=False) as router:
        route = router.post(ENDPOINT)
        with pytest.raises(PushError) as raised:
            await WebPushSender(http, api_settings).send(target, MESSAGE)
    assert not isinstance(raised.value, PushNotConfigured)
    assert not raised.value.retryable
    assert not route.called


@pytest.mark.parametrize(
    "update",
    [
        {"vapid_private_key": None},
        {"vapid_public_key": None},
        {"vapid_private_key": SecretStr("not-a-key")},
    ],
)
async def test_without_usable_vapid_keys_nothing_is_sent(
    http: httpx.AsyncClient, api_settings: Settings, update: dict[str, Any]
) -> None:
    settings = api_settings.model_copy(update=update)
    with respx.mock(assert_all_called=False) as router:
        route = router.post(ENDPOINT)
        with pytest.raises(PushNotConfigured):
            await WebPushSender(http, settings).send(TARGET, MESSAGE)
    assert not route.called
