"""Webhook signature checks (TR-WH-02). Always over the raw bytes, always constant-time."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any


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
