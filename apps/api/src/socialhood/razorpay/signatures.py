"""What Razorpay signs (GR-32): ``X-Razorpay-Signature`` is the hex HMAC-SHA256 of the raw
webhook body with the webhook secret the business set on its Razorpay webhook, checked in
constant time. Anything missing or malformed is False, never an exception."""

from __future__ import annotations

import hashlib
import hmac


def sign_webhook(raw: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def verify_webhook(raw: bytes, header: str | None, secret: str) -> bool:
    if not header or not secret:
        return False
    return hmac.compare_digest(sign_webhook(raw, secret), header.strip())
