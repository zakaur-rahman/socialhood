"""The preview before a change, enforced by the server (C-169; 01-design.md §6.6).

A tool whose change needs the member's yes answers its first call with a preview and a
``confirmation_token``. The change itself needs ``confirmed: true`` and a token for exactly those
arguments, so an AI app can't skip the preview, or preview one thing and do another. Changed
arguments need a new preview.

The token is stateless: ``<expiry>.<mac>``, an HMAC-SHA256 over the tool, the workspace, the
credential, the canonical arguments (without ``confirmed``, the token and ``idempotency_key``),
what the call resolved them to (“latest” as a post id, so a post that syncs after the preview
means a new preview), and the expiry. The key is derived from each of TOKEN_ENCRYPTION_KEYS, like
the widget's tokens (security/widget_tokens.py): the newest signs, every configured key verifies.

It proves a preview was made by this connection. It can't prove a person read it: that rests on
the AI app, and one set to always allow the tools can preview and confirm by itself. A token
runs its change once: ``claim`` marks it used in Valkey just before the tool runs, and ``release``
gives it back when the call fails, so a failed call can be retried. A retry of a call that worked
gets the first result back when it has an idempotency key or the tool a dedupe window; without
either it reaches ``claim`` and is told the preview was used, so ``USED`` never says that nothing
changed.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping, Sequence
from typing import Final

from pydantic import BaseModel
from redis.asyncio import Redis

from socialhood.errors import ApiError, FieldError
from socialhood.mcp.context import ToolCall
from socialhood.observability.logging import get_logger
from socialhood.settings import ConfigurationError

log = get_logger(__name__)

PURPOSE = b"socialhood/mcp-confirmation/v1"
TTL_S: int = 900
ARGUMENT: Final = "confirmation_token"
# Not what is being confirmed: the arguments that say it is, and the retry key.
NOT_BOUND: Final = frozenset({"confirmed", ARGUMENT, "idempotency_key"})

THEN = (
    "Nothing was changed. Call without confirmed to get a preview, show it to the member, and "
    "after they agree call again with the same arguments, confirmed: true and its "
    "confirmation_token."
)
MISSING = f"This change needs a preview first. {THEN}"
EXPIRED = f"That preview has expired. {THEN}"
MISMATCH = f"That confirmation_token isn't for this change on this connection. {THEN}"
USED = (
    "That preview has already been used, so the change may already have been made. Check before "
    "retrying. To change something else, call without confirmed to get a new preview."
)


def next_step(then: str) -> str:
    """What a preview tells the AI app to do."""
    return (
        "Nothing was changed. Show the member this. After they agree, call again with the same "
        f"arguments, confirmed: true and this confirmation_token to {then}."
    )


def _mac_key(fernet_key: str) -> bytes | None:
    try:
        raw = base64.urlsafe_b64decode(fernet_key.encode())
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 32:
        return None
    return hmac.new(raw, PURPOSE, hashlib.sha256).digest()


def _keys(configured: Sequence[str]) -> list[bytes]:
    return [key for key in map(_mac_key, configured) if key is not None]


def _bound(call: ToolCall, args: BaseModel, resolved: Mapping[str, object], expires: int) -> bytes:
    """What the token is bound to, canonical bytes for the HMAC."""
    return json.dumps(
        {
            "tool": call.tool_name,
            "workspace": str(call.workspace.id),
            "credential": str(call.principal.credential_id),
            "arguments": args.model_dump(mode="json", exclude=set(NOT_BOUND)),
            "resolved": {name: str(value) for name, value in resolved.items()},
            "expires": expires,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sign(key: bytes, body: bytes) -> str:
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def issue(call: ToolCall, args: BaseModel, **resolved: object) -> str:
    """The token a preview returns."""
    keys = _keys(call.settings.token_encryption_keys)
    if not keys:
        raise ConfigurationError("TOKEN_ENCRYPTION_KEYS is empty or invalid; cannot sign tokens")
    expires = int(call.now.timestamp()) + TTL_S
    return f"{expires}.{_sign(keys[0], _bound(call, args, resolved, expires))}"


def _refused(message: str) -> ApiError:
    return ApiError("validation_error", message, errors=[FieldError(ARGUMENT, message)])


def require(call: ToolCall, args: BaseModel, token: str | None, **resolved: object) -> None:
    """Refuse a confirmed call without a valid token for exactly these arguments. Call it before
    anything changes. ``resolved`` is what the preview passed to ``issue``."""
    if not token:
        raise _refused(MISSING)
    expiry, _, mac = token.partition(".")
    if not expiry.isascii() or not expiry.isdecimal() or len(expiry) > 12:
        raise _refused(MISMATCH)
    expires = int(expiry)
    body = _bound(call, args, resolved, expires)
    keys = _keys(call.settings.token_encryption_keys)
    if not any(hmac.compare_digest(_sign(key, body).encode(), mac.encode()) for key in keys):
        raise _refused(MISMATCH)
    if expires <= int(call.now.timestamp()):
        raise _refused(EXPIRED)


async def claim(redis: Redis, credential_id: uuid.UUID, args: BaseModel) -> str | None:
    """Mark a confirmed call's token used, or refuse one already used. Returns what ``release``
    takes, or None when there is nothing to give back. Valkey being down never blocks a write
    (mcp/idempotency.py); the token's other limits still hold."""
    token = getattr(args, ARGUMENT, None)
    if not token or not getattr(args, "confirmed", False):
        return None
    name = f"mcp-confirm:{credential_id}:{hashlib.sha256(token.encode()).hexdigest()}"
    try:
        first = await redis.set(name, "1", nx=True, ex=TTL_S)
    except Exception:
        log.warning("mcp_confirmation_claim_unavailable")
        return None
    if not first:
        raise _refused(USED)
    return name


async def release(redis: Redis, claimed: str | None) -> None:
    """Give a token back after a call that changed nothing."""
    if claimed is None:
        return
    try:
        await redis.delete(claimed)
    except Exception:
        log.warning("mcp_confirmation_claim_unavailable")
