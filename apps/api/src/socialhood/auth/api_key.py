"""Authentication for the public API (GR-25): ``Authorization: Bearer shk_...``.

A request is checked in this order, and each refusal stops it:

1. the key's shape, then its hash against api_keys (401 for an unknown, malformed or revoked key;
   an unknown key also counts against the caller's IP, so guessing is slow);
2. the workspace is active (401 otherwise, like a revoked key);
3. the per-key rate limit (``api_key`` in security/ratelimit.py: 120 a minute), then the plan
   (402 entitlement_required when the workspace is no longer on Pro or Max, PD-6);
4. each route's scope (403 forbidden, naming the scope the key lacks).

The key resolves to its workspace, which becomes the request's tenant exactly as for a signed-in
member, so every service query is scoped to it. The request log carries ``api_key_id`` (never the
key). ``last_used_at`` is written at most once a minute.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
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
from socialhood.db.tenancy import current_workspace_id, tenant_bypass_scope
from socialhood.errors import ApiError
from socialhood.models.api_keys import ApiKey
from socialhood.models.identity import Workspace, WorkspaceStatus
from socialhood.repositories.base import scoped_update
from socialhood.security import ratelimit
from socialhood.services import api_keys

LAST_USED_EVERY_S = 60


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
    if key is None:
        await ratelimit.enforce(request, "public", ratelimit.client_ip(request))
        raise ApiError("unauthorized", "That API key isn't valid.")
    if key.revoked_at is not None:
        raise ApiError("unauthorized", "That API key has been revoked.")
    workspace = await session.get(Workspace, key.workspace_id)
    if workspace is None or workspace.status != WorkspaceStatus.ACTIVE:
        raise ApiError("unauthorized", "That API key isn't valid.")

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
