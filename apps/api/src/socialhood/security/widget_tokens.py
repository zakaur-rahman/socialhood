"""Visitor tokens for the website chat widget (GR-28). No table: a token says which widget, which
workspace, which visitor and which site it was issued for, and only the server can make one.

A visitor starts with a *visitor secret* (random, kept by the widget in its own storage). The
contact is keyed by a hash of it (``visitor_id``), so the id that appears in the inbox and in
exports cannot be used to read the chat. ``POST /v1/widget/session`` turns the secret into a
short-lived token, which the widget sends as a bearer on every call; a token never reaches the
page that embeds the widget (the widget lives in its own frame).

Token: base64url(JSON claims) + "." + base64url(first 16 bytes of HMAC-SHA256 over the first
part). The key is derived from each of TOKEN_ENCRYPTION_KEYS like the digest unsubscribe links
(notify/unsubscribe.py): the newest signs, every configured key verifies, so rotating keys keeps
live tokens working. A token lasts ``TOKEN_TTL_S``; the widget asks for a new one when a call
says it expired.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from socialhood.settings import ConfigurationError

PURPOSE = b"socialhood/widget-visitor/v1"
TOKEN_TTL_S = 6 * 3600
MAX_TOKEN_CHARS = 700
_MAC_BYTES = 16
SECRET_MIN_CHARS = 20
SECRET_MAX_CHARS = 100
_SECRET = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class VisitorClaim:
    account_id: uuid.UUID
    workspace_id: uuid.UUID
    visitor_id: str
    host: str
    expires_at: int


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def valid_secret(secret: str) -> bool:
    return SECRET_MIN_CHARS <= len(secret) <= SECRET_MAX_CHARS and bool(_SECRET.fullmatch(secret))


def visitor_id(secret: str) -> str:
    """The contact key for a visitor secret: ``v_`` and 24 hex characters of its SHA-256."""
    return "v_" + hashlib.sha256(secret.encode()).hexdigest()[:24]


def _mac_key(fernet_key: str) -> bytes | None:
    try:
        raw = base64.urlsafe_b64decode(fernet_key.encode())
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 32:
        return None
    return hmac.new(raw, PURPOSE, hashlib.sha256).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(key: bytes, body: str) -> bytes:
    return hmac.new(key, body.encode(), hashlib.sha256).digest()[:_MAC_BYTES]


def make_token(claim: VisitorClaim, keys: Sequence[str]) -> str:
    """Sign with the newest key (the first of TOKEN_ENCRYPTION_KEYS)."""
    key = _mac_key(keys[0]) if keys else None
    if key is None:
        raise ConfigurationError("TOKEN_ENCRYPTION_KEYS is empty or invalid; cannot sign tokens")
    body = _b64(
        json.dumps(
            {
                "a": str(claim.account_id),
                "w": str(claim.workspace_id),
                "v": claim.visitor_id,
                "h": claim.host,
                "e": claim.expires_at,
            },
            separators=(",", ":"),
        ).encode()
    )
    return f"{body}.{_b64(_mac(key, body))}"


def issue(
    *,
    account_id: uuid.UUID,
    workspace_id: uuid.UUID,
    visitor: str,
    host: str,
    keys: Sequence[str],
    now: float | None = None,
) -> tuple[str, int]:
    """A token and the seconds it lasts."""
    expires_at = int((time.time() if now is None else now) + TOKEN_TTL_S)
    claim = VisitorClaim(account_id, workspace_id, visitor, host, expires_at)
    return make_token(claim, keys), TOKEN_TTL_S


def read_token(token: str, keys: Sequence[str], *, now: float | None = None) -> VisitorClaim | None:
    """The claim if any configured key signed this token and it has not expired, else None
    (never raises)."""
    if not token or len(token) > MAX_TOKEN_CHARS or token.count(".") != 1:
        return None
    body, _, mac_text = token.partition(".")
    try:
        mac = _unb64(mac_text)
    except (binascii.Error, ValueError):
        return None
    signed = False
    for candidate in keys:
        key = _mac_key(candidate)
        if key is not None and hmac.compare_digest(_mac(key, body), mac):
            signed = True
            break
    if not signed:
        return None
    try:
        data = json.loads(_unb64(body))
        claim = VisitorClaim(
            account_id=uuid.UUID(data["a"]),
            workspace_id=uuid.UUID(data["w"]),
            visitor_id=str(data["v"]),
            host=str(data["h"]),
            expires_at=int(data["e"]),
        )
    except (binascii.Error, ValueError, KeyError, TypeError):
        return None
    if claim.expires_at <= (time.time() if now is None else now):
        return None
    return claim
