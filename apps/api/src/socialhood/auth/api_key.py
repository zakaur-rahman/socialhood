"""Authentication for the public API (GR-25): ``Authorization: Bearer shk_...``.

A request is checked in this order, and each refusal stops it:

1. the key's shape, then its hash against api_keys (401 for an unknown, malformed or revoked key;
   an unknown key also counts against the caller's IP, so guessing is slow);
2. C-167: not expired (401 "That API key has expired."), then the caller's address is on the
   key's allowlist, when it has one (403 "This API key can't be used from this address.");
   the address is ``ratelimit.client_ip``, which reads X-Forwarded-For from the right behind
   Caddy (CLIENT_IP_HEADER, security/client_ip.py);
3. the workspace is active (401 otherwise, like a revoked key), and the member who made the key
   is still in it (C-167: their keys are revoked when they leave; this also covers a key whose
   revocation was missed). A key whose maker's account was deleted before C-167 still works;
4. the per-key rate limit (``api_key`` in security/ratelimit.py: 120 a minute), then the plan
   (402 entitlement_required when the workspace is no longer on Pro or Max, PD-6);
5. each route's scope (403 forbidden, naming the scope the key lacks).

The key resolves to its workspace, which becomes the request's tenant exactly as for a signed-in
member, so every service query is scoped to it. The request log carries ``api_key_id`` (never the
key). ``last_used_at`` is written at most once a minute.
"""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.deps import Session, _bearer
from socialhood.billing.entitlements import check_entitlement
from socialhood.db.tenancy import current_workspace_id, tenant_bypass_scope, workspace_scope
from socialhood.errors import ApiError
from socialhood.models.api_keys import ApiKey
from socialhood.models.identity import Workspace, WorkspaceMember, WorkspaceStatus
from socialhood.repositories.base import scoped_update
from socialhood.security import ratelimit
from socialhood.services import api_keys

LAST_USED_EVERY_S = 60
INVALID = "That API key isn't valid."
REVOKED = api_keys.REVOKED
EXPIRED = "That API key has expired."
WRONG_ADDRESS = "This API key can't be used from this address."
MAKER_LEFT = "This key's owner is no longer in the workspace. Make a new key in Amplychat."


def is_expired(key: ApiKey, now: datetime) -> bool:
    return key.expires_at is not None and key.expires_at <= now


def address_allowed(allowed: Sequence[str], address: str) -> bool:
    """Whether ``address`` is on the allowlist; any address when the list is empty. An address
    that doesn't parse ("unknown") is never on a list. An IPv4-mapped IPv6 address ("::ffff:
    203.0.113.7") is matched as the IPv4 address it carries."""
    if not allowed:
        return True
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    for entry in allowed:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if network.version == ip.version and ip in network:
            return True
    return False


async def maker_is_member(session: AsyncSession, key: ApiKey) -> bool:
    """Whether the member who made ``key`` still belongs to its workspace (True for a key with
    no maker on record). Runs in the key's workspace."""
    if key.created_by_user_id is None:
        return True
    with workspace_scope(key.workspace_id):
        found = await session.scalar(
            select(WorkspaceMember.id).where(WorkspaceMember.user_id == key.created_by_user_id)
        )
    return found is not None


@dataclass(frozen=True)
class ApiKeyContext:
    key_id: uuid.UUID
    workspace: Workspace
    scopes: frozenset[str]

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id


async def find_key(session: AsyncSession, raw: str) -> ApiKey | None:
    """The key ``raw`` is, revoked or not; None for anything that isn't one of ours. The one
    cross-workspace lookup: the key is how we find its workspace. Also used by the MCP server
    (auth/mcp_credentials.py)."""
    if not api_keys.looks_like_key(raw):
        return None
    with tenant_bypass_scope():
        return (
            await session.scalars(select(ApiKey).where(ApiKey.key_hash == api_keys.hash_key(raw)))
        ).one_or_none()


async def api_key_ctx(request: Request, session: Session) -> AsyncIterator[ApiKeyContext]:
    raw = _bearer(request)
    key = await find_key(session, raw)
    address = ratelimit.client_ip(request)
    if key is None:
        await ratelimit.enforce(request, "public", address)
        raise ApiError("unauthorized", INVALID)
    if key.revoked_at is not None:
        raise ApiError("unauthorized", REVOKED)
    if is_expired(key, datetime.now(UTC)):
        raise ApiError("unauthorized", EXPIRED)
    if not address_allowed(key.allowed_ips, address):
        raise ApiError("forbidden", WRONG_ADDRESS)
    workspace = await session.get(Workspace, key.workspace_id)
    if workspace is None or workspace.status != WorkspaceStatus.ACTIVE:
        raise ApiError("unauthorized", INVALID)
    if not await maker_is_member(session, key):
        raise ApiError("unauthorized", MAKER_LEFT)

    token = current_workspace_id.set(workspace.id)
    try:
        structlog.contextvars.bind_contextvars(
            api_key_id=str(key.id), workspace_id=str(workspace.id)
        )
        await ratelimit.enforce(request, "api_key", str(key.id))
        await check_entitlement(session, "public_api")
        await touch_last_used(request.app.state.redis, session, key)
        yield ApiKeyContext(key_id=key.id, workspace=workspace, scopes=frozenset(key.scopes))
    finally:
        with suppress(ValueError):  # a different context (after the response) cannot reset
            current_workspace_id.reset(token)


async def touch_last_used(redis: Redis, session: AsyncSession, key: ApiKey) -> None:
    """At most one write per key per minute; a Valkey outage never blocks a request."""
    try:
        first = await redis.set(f"apikey-used:{key.id}", "1", nx=True, ex=LAST_USED_EVERY_S)
    except Exception:
        return
    if first:
        await session.execute(
            scoped_update(ApiKey, id=key.id).values(last_used_at=datetime.now(UTC))
        )
        await session.commit()


KeyContext = Annotated[ApiKeyContext, Depends(api_key_ctx)]


def require_scope(scope: str) -> Callable[..., Awaitable[ApiKeyContext]]:
    """A route's gate: 403 forbidden unless the key carries ``scope``."""

    async def dependency(ctx: KeyContext) -> ApiKeyContext:
        if scope not in ctx.scopes:
            raise ApiError("forbidden", f"This API key doesn't have the {scope} scope.")
        return ctx

    dependency.required_scope = scope  # type: ignore[attr-defined]  # read by api/public_openapi.py
    return dependency
