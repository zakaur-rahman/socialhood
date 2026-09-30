"""Webhook signature checks (TR-WH-02). Always over the raw bytes, always constant-time."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from standardwebhooks.webhooks import Webhook

# Standard Webhooks (https://standardwebhooks.com), which Dodo follows: the message id, the Unix
# timestamp and ``v1,<base64 HMAC-SHA256>`` signatures (space-separated) in these headers.
STANDARD_WEBHOOK_HEADERS = ("webhook-id", "webhook-timestamp", "webhook-signature")


def verify_standard_webhook(raw: bytes, headers: Mapping[str, str], secret: str) -> bool:
    """TR-WH-02 for Dodo (TR-BIL-02, SEC-04): True only when a ``v1`` signature in
    ``webhook-signature`` is HMAC-SHA256 of ``{webhook-id}.{webhook-timestamp}.{raw body}`` with
    the secret (``whsec_`` + base64 key), and the timestamp is within 5 minutes of now (replays).
    Anything else is False: a missing header, a malformed signature, an empty or invalid secret,
    a body that is not UTF-8. Never raises, so a caller cannot fail open by accident."""
    if not secret:
        return False
    wanted = {name.lower(): value for name, value in headers.items()}
    picked = {name: wanted.get(name, "") for name in STANDARD_WEBHOOK_HEADERS}
    if not all(picked.values()):
        return False
    try:
        Webhook(secret).verify(raw, picked, json_parse=False)
    except Exception:
        # WebhookVerificationError, and what the library lets through: ValueError for a
        # signature without a comma or a non-UTF-8 body, binascii.Error for bad base64,
        # EmptyWebhookSecretError for a secret that decodes to nothing.
        return False
    return True


def sign_standard_webhook(msg_id: str, timestamp: datetime, raw: bytes, secret: str) -> str:
    """The ``webhook-signature`` value for a body (tests and the sandbox)."""
    return Webhook(secret).sign(msg_id=msg_id, timestamp=timestamp, data=raw.decode())


CLOUDINARY_MAX_AGE_S = 7200  # Cloudinary's own SDKs accept a notification for 2 hours


def _cloudinary_digest(raw: bytes, timestamp: str, secret: str, hex_length: int) -> str:
    algorithm = hashlib.sha256 if hex_length == 64 else hashlib.sha1
    return algorithm(raw + timestamp.encode() + secret.encode()).hexdigest()


def verify_cloudinary_notification(
    raw: bytes,
    headers: Mapping[str, str],
    secret: str,
    *,
    now: float,
    max_age_s: int = CLOUDINARY_MAX_AGE_S,
) -> bool:
    """TR-MED-05 (SEC-04): a Cloudinary notification is genuine only when ``X-Cld-Signature`` is
    the hex SHA-1 (SHA-256 on accounts set to it: 64 hex digits) of the raw body, then
    ``X-Cld-Timestamp``, then the API secret, and the timestamp is at most ``max_age_s`` old (and
    not more than 5 minutes ahead). Anything else is False: no secret, a missing or malformed
    header, a stale or future timestamp. Never raises, so a caller cannot fail open by accident.
    (The spike checked the account signs with SHA-1: the upload API's own ``signature`` is
    sha1("public_id=…&version=…" + secret).)"""
    if not secret:
        return False
    wanted = {name.lower(): value for name, value in headers.items()}
    signature = wanted.get("x-cld-signature", "").strip().lower()
    timestamp = wanted.get("x-cld-timestamp", "").strip()
    if len(signature) not in (40, 64) or not timestamp.isdigit():
        return False
    if not now - max_age_s <= int(timestamp) <= now + 300:
        return False
    expected = _cloudinary_digest(raw, timestamp, secret, len(signature))
    return hmac.compare_digest(expected, signature)


def sign_cloudinary_notification(
    raw: bytes, timestamp: int, secret: str, *, algorithm: str = "sha1"
) -> dict[str, str]:
    """The headers Cloudinary would send with ``raw`` (tests and the sandbox)."""
    stamp = str(timestamp)
    digest = _cloudinary_digest(raw, stamp, secret, 64 if algorithm == "sha256" else 40)
    return {"X-Cld-Timestamp": stamp, "X-Cld-Signature": digest}


def verify_hub_signature(raw: bytes, header: str | None, secret: str) -> bool:
    """Meta's X-Hub-Signature-256: ``sha256=<hex>`` of HMAC-SHA256(secret, raw body)."""
    if not header or not secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def parse_signed_request(signed_request: str | None, secrets: list[str]) -> dict[str, Any] | None:
    """Meta's signed_request (deauthorize and data-deletion callbacks): ``<sig>.<payload>``,
    both base64url; the signature is HMAC-SHA256 of the payload part with an app secret.
    Returns the payload if any given secret verifies it."""
    if not signed_request or "." not in signed_request:
        return None
    signature_part, payload_part = signed_request.split(".", 1)
    try:
        signature = _b64url_decode(signature_part)
        payload = json.loads(_b64url_decode(payload_part))
    except (ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("algorithm", "HMAC-SHA256").upper() != "HMAC-SHA256"
    ):
        return None
    for secret in secrets:
        if not secret:
            continue
        expected = hmac.new(secret.encode(), payload_part.encode(), hashlib.sha256).digest()
        if hmac.compare_digest(expected, signature):
            return payload
    return None


def sign_request(payload: dict[str, Any], secret: str) -> str:
    """The inverse of parse_signed_request; used by tests and the sandbox."""
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return f"{signature}.{body}"
