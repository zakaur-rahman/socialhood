"""Token shapes and lifetimes (C-165 phase C; 01-design.md §3.2, §3.6).

- Access tokens: ``sho_`` and 43 random characters, one hour.
- Refresh tokens: ``shr_`` and 43 random characters; rotated on every use.
- Authorization codes: ``shc_`` and 43 random characters, 60 seconds, single use.
- Only SHA-256 hashes are stored (the values are long and random, so a plain hash is enough,
  as for API keys).
- A connection (the grant) lasts while it's used: 30 days without a use ends it, and 180 days
  after consent it ends whatever happens. Then the client asks the member to connect again.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from socialhood.models.oauth import McpConnection

ACCESS_PREFIX = "sho_"
REFRESH_PREFIX = "shr_"
CODE_PREFIX = "shc_"
ACCESS_TTL = timedelta(hours=1)
CODE_TTL = timedelta(seconds=60)
REQUEST_TTL = timedelta(minutes=10)  # an authorization request waiting on the consent page
IDLE_LIMIT = timedelta(days=30)
ABSOLUTE_LIMIT = timedelta(days=180)

REVOKED = "This connection was disconnected. Connect Amplychat again."
EXPIRED = "This connection has expired. Connect Amplychat again."


def new_token(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def looks_like(value: str, prefix: str) -> bool:
    return value.startswith(prefix) and 20 <= len(value) <= 100


def connection_problem(connection: McpConnection, now: datetime) -> str | None:
    """Why a connection can't be used now, in words for the member; None when it can."""
    if connection.revoked_at is not None:
        return REVOKED
    if now >= connection.expires_at:
        return EXPIRED
    last = connection.last_used_at or connection.created_at
    if now - last >= IDLE_LIMIT:
        return EXPIRED
    return None
