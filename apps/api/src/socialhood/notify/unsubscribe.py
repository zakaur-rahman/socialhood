"""Signed one-click unsubscribe tokens for the weekly digest (FR-NOT-04, T8.7). No table: the
token itself says who and where, and only the server can make one.

Token: base64url(version 1 · workspace id · user id · MAC), 66 characters, where MAC is the first
16 bytes of HMAC-SHA256 over the first 33 bytes. The MAC key is derived from each of
TOKEN_ENCRYPTION_KEYS (HMAC-SHA256 of a fixed purpose label with the Fernet key's bytes), so no
new secret is needed: the newest key signs and every configured key verifies, and rotating keys
keeps old links working until the old key is removed. Tokens don't expire: an unsubscribe link in
an old email should still work (RFC 8058). The token only turns the digest off for that member of
that workspace; it grants nothing else.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from socialhood.settings import ConfigurationError

PURPOSE = b"socialhood/digest-unsubscribe/v1"
VERSION = 1
_MAC_BYTES = 16
_BODY_BYTES = 1 + 16 + 16


@dataclass(frozen=True)
class UnsubscribeClaim:
    workspace_id: uuid.UUID
    user_id: uuid.UUID


def _mac_key(fernet_key: str) -> bytes | None:
    try:
        raw = base64.urlsafe_b64decode(fernet_key.encode())
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 32:
        return None
    return hmac.new(raw, PURPOSE, hashlib.sha256).digest()


def _mac(key: bytes, body: bytes) -> bytes:
    return hmac.new(key, body, hashlib.sha256).digest()[:_MAC_BYTES]


def make_token(workspace_id: uuid.UUID, user_id: uuid.UUID, keys: Sequence[str]) -> str:
    """Sign with the newest key (the first of TOKEN_ENCRYPTION_KEYS)."""
    key = _mac_key(keys[0]) if keys else None
    if key is None:
        raise ConfigurationError("TOKEN_ENCRYPTION_KEYS is empty or invalid; cannot sign links")
    body = bytes([VERSION]) + workspace_id.bytes + user_id.bytes
    return base64.urlsafe_b64encode(body + _mac(key, body)).rstrip(b"=").decode()


def read_token(token: str, keys: Sequence[str]) -> UnsubscribeClaim | None:
    """The claim if any configured key signed this token, else None (never raises)."""
    if not token or len(token) > 100:
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None
    if len(raw) != _BODY_BYTES + _MAC_BYTES or raw[0] != VERSION:
        return None
    body, mac = raw[:_BODY_BYTES], raw[_BODY_BYTES:]
    for candidate in keys:
        key = _mac_key(candidate)
        if key is not None and hmac.compare_digest(_mac(key, body), mac):
            return UnsubscribeClaim(
                workspace_id=uuid.UUID(bytes=body[1:17]), user_id=uuid.UUID(bytes=body[17:33])
            )
    return None
