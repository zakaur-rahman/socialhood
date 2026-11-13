"""API keys as MCP credentials (C-165; 01-design.md §3.3). In auth/ because finding a key's
workspace is a cross-workspace lookup (TR-TEN-04).

The same checks as the public API's ``api_key_ctx``, by the same function
(auth/api_key.usable_key): the key's hash, not revoked, not expired, the caller's address on its
allowlist (C-167; refused with 403 rather than 401), its workspace active. Then, MCP's own rule:
a key has no member, so the principal is the member who made it, with their current role. A key
whose maker has left the workspace (or whose maker was deleted) can't be used on /mcp.

The plan and the rate limits aren't checked here: on /mcp a refusal for those is a tool error
the model can explain (mcp/calls.py), not an HTTP error a client shows as "server broken".
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.api_key import INVALID, MAKER_LEFT, touch_last_used, usable_key
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.mcp.principal import ALWAYS_GRANTED, McpPrincipal
from socialhood.models.identity import Role, WorkspaceMember
from socialhood.models.mcp import CredentialKind

OWNER_LEFT = MAKER_LEFT


class CredentialRefused(Exception):
    """The bearer token doesn't authenticate. ``unknown``: it isn't any credential of ours (the
    caller's IP pays for it, so guessing is slow). ``forbidden``: it is valid but may not be used
    from here (C-167, an API key's IP allowlist): 403, not 401."""

    def __init__(self, message: str, *, unknown: bool = False, forbidden: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.unknown = unknown
        self.forbidden = forbidden


async def principal_for_api_key(
    session: AsyncSession, redis: Redis, raw: str, *, client_ip: str | None = None
) -> McpPrincipal:
    """The principal ``raw`` (an ``shk_`` key) acts as, or ``CredentialRefused``. ``client_ip``
    is the caller's address (``ratelimit.client_ip``); a key with an allowlist needs one."""
    try:
        found = await usable_key(session, raw, client_ip or "")
    except ApiError as error:
        raise CredentialRefused(
            error.detail or INVALID, forbidden=error.code == "forbidden"
        ) from error
    if found is None:
        raise CredentialRefused(INVALID, unknown=True)
    key, workspace = found
    if key.created_by_user_id is None:
        raise CredentialRefused(OWNER_LEFT)
    with workspace_scope(workspace.id):
        role = await session.scalar(
            select(WorkspaceMember.role).where(WorkspaceMember.user_id == key.created_by_user_id)
        )
        if role is None:
            raise CredentialRefused(OWNER_LEFT)
        await touch_last_used(redis, session, key)
    return McpPrincipal(
        workspace_id=workspace.id,
        user_id=key.created_by_user_id,
        role=Role(role),
        scopes=frozenset({*key.scopes, ALWAYS_GRANTED}),
        credential=CredentialKind.API_KEY,
        credential_id=key.id,
        credential_label=f"API key “{key.name}”",
    )
