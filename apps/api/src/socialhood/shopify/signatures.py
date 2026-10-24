"""What Shopify signs (GR-31), checked over the raw bytes and in constant time.

- **Webhooks**: ``X-Shopify-Hmac-Sha256`` is the base64 of HMAC-SHA256 of the raw body with the
  app's client secret.
- **The install redirect** (OAuth callback): a ``hmac`` query parameter, the hex HMAC-SHA256 of
  the other parameters, sorted by name and joined as ``key=value`` with ``&``, with the client
  secret.

Anything missing or malformed is False, never an exception, so a caller can't fail open.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping


def sign_webhook(raw: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()


def verify_webhook(raw: bytes, header: str | None, secret: str) -> bool:
    if not header or not secret:
        return False
    return hmac.compare_digest(sign_webhook(raw, secret), header.strip())


def sign_query(params: Mapping[str, str], secret: str) -> str:
    message = "&".join(f"{key}={value}" for key, value in sorted(params.items()) if key != "hmac")
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_query(params: Mapping[str, str], secret: str) -> bool:
    given = params.get("hmac")
    if not given or not secret:
        return False
    return hmac.compare_digest(sign_query(params, secret), given)
