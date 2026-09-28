"""Request ids: ULIDs, sortable by time, echoed in X-Request-ID and in every problem body."""

from __future__ import annotations

import os
import re
import time
from contextvars import ContextVar

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_INCOMING = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

current_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_ulid() -> str:
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def accept_or_new(incoming: str | None) -> str:
    """Keep a well-formed id from a trusted proxy or client; otherwise make one."""
    if incoming and _INCOMING.match(incoming):
        return incoming
    return new_ulid()
