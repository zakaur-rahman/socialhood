"""Dodo webhook signatures (TR-BIL-02, TR-WH-02, SEC-04): Standard Webhooks, checked against the
specification's published example and every way a delivery can be wrong. The helper never raises,
so no caller can fail open."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from socialhood.security.signatures import sign_standard_webhook, verify_standard_webhook

# The example in the Standard Webhooks specification (and Svix's docs): secret, message id,
# timestamp and body, and the signature they produce.
VECTOR_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"  # gitleaks:allow (published example)
VECTOR_ID = "msg_p5jXN8AQM9LWM0D4loKWxJek"
VECTOR_TIMESTAMP = 1614265330
VECTOR_BODY = b'{"test": 2432232314}'
VECTOR_SIGNATURE = "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="
VECTOR_TIME = datetime.fromtimestamp(VECTOR_TIMESTAMP, tz=UTC)

OTHER_SECRET = "whsec_" + base64.b64encode(b"a different signing key!!").decode()


def headers(signature: str = VECTOR_SIGNATURE, **overrides: str) -> dict[str, str]:
    values = {
        "webhook-id": VECTOR_ID,
        "webhook-timestamp": str(VECTOR_TIMESTAMP),
        "webhook-signature": signature,
    }
    return {**values, **overrides}


@pytest.fixture
def at_vector_time() -> Iterator[None]:
    with time_machine.travel(VECTOR_TIME + timedelta(seconds=30), tick=False):
        yield


def test_the_specification_example_signs_to_its_published_signature() -> None:
    assert sign_standard_webhook(VECTOR_ID, VECTOR_TIME, VECTOR_BODY, VECTOR_SECRET) == (
        VECTOR_SIGNATURE
    )


@pytest.mark.usefixtures("at_vector_time")
def test_the_specification_example_verifies() -> None:
    assert verify_standard_webhook(VECTOR_BODY, headers(), VECTOR_SECRET)
    # Header names are case-insensitive; other v1 signatures may come first (key rotation).
    mixed = {key.title(): value for key, value in headers().items()}
    assert verify_standard_webhook(VECTOR_BODY, mixed, VECTOR_SECRET)
    rotated = headers(signature=f"v1,{base64.b64encode(b'x' * 32).decode()} {VECTOR_SIGNATURE}")
    assert verify_standard_webhook(VECTOR_BODY, rotated, VECTOR_SECRET)


@pytest.mark.usefixtures("at_vector_time")
@pytest.mark.parametrize(
    ("body", "values", "secret"),
    [
        (b'{"test": 2432232315}', headers(), VECTOR_SECRET),  # body changed
        (b'{"test":2432232314}', headers(), VECTOR_SECRET),  # re-serialised (v1's Dodo bug)
        (VECTOR_BODY, headers(), OTHER_SECRET),  # another secret
        (VECTOR_BODY, headers(**{"webhook-id": "msg_other"}), VECTOR_SECRET),
        (VECTOR_BODY, headers(**{"webhook-timestamp": str(VECTOR_TIMESTAMP + 1)}), VECTOR_SECRET),
        (VECTOR_BODY, headers(signature="v2," + VECTOR_SIGNATURE[3:]), VECTOR_SECRET),
        (VECTOR_BODY, headers(signature="g0hM9SsE+OTPJTGt"), VECTOR_SECRET),  # no version
        (VECTOR_BODY, headers(signature="v1,not base64!"), VECTOR_SECRET),
        (VECTOR_BODY, headers(signature=""), VECTOR_SECRET),
        (VECTOR_BODY, headers(**{"webhook-timestamp": "yesterday"}), VECTOR_SECRET),
        (VECTOR_BODY, {"webhook-signature": VECTOR_SIGNATURE}, VECTOR_SECRET),  # ids missing
        (VECTOR_BODY, headers(), ""),  # not configured
        (VECTOR_BODY, headers(), "whsec_"),  # decodes to nothing
        (b"\xff\xfe not utf-8", headers(), VECTOR_SECRET),
    ],
)
def test_anything_else_is_refused(body: bytes, values: dict[str, str], secret: str) -> None:
    assert verify_standard_webhook(body, values, secret) is False


def test_a_delivery_older_or_newer_than_five_minutes_is_refused() -> None:
    with time_machine.travel(VECTOR_TIME + timedelta(minutes=6), tick=False):
        assert verify_standard_webhook(VECTOR_BODY, headers(), VECTOR_SECRET) is False
    with time_machine.travel(VECTOR_TIME - timedelta(minutes=6), tick=False):
        assert verify_standard_webhook(VECTOR_BODY, headers(), VECTOR_SECRET) is False
    with time_machine.travel(VECTOR_TIME + timedelta(minutes=4), tick=False):
        assert verify_standard_webhook(VECTOR_BODY, headers(), VECTOR_SECRET) is True


def test_a_fresh_signature_verifies_now() -> None:
    now = datetime.now(UTC)
    raw = b'{"type": "subscription.active", "data": {}}'
    signed = {
        "webhook-id": "msg_1",
        "webhook-timestamp": str(int(now.timestamp())),
        "webhook-signature": sign_standard_webhook("msg_1", now, raw, OTHER_SECRET),
    }
    assert verify_standard_webhook(raw, signed, OTHER_SECRET)
    assert not verify_standard_webhook(raw, signed, VECTOR_SECRET)
