"""API keys as MCP credentials (C-165; 01-design.md §3.3). In auth/ because finding a key's
workspace is a cross-workspace lookup (TR-TEN-04).

The same checks as the public API's ``api_key_ctx`` (auth/api_key.py), in the same order: the
key's hash, not revoked, its workspace active. Then, MCP's own rule: a key has no member, so the
principal is the member who made it, with their current role. A key whose maker has left the
workspace (or whose maker was deleted) can't be used on /mcp.

The plan and the rate limits aren't checked here: on /mcp a refusal for those is a tool error
the model can explain (mcp/calls.py), not an HTTP error a client shows as "server broken".
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.api_key import find_key, touch_last_used
from socialhood.db.tenancy import workspace_scope
from socialhood.mcp.principal import ALWAYS_GRANTED, McpPrincipal
from socialhood.models.identity import Role, Workspace, WorkspaceMember, WorkspaceStatus
from socialhood.models.mcp import CredentialKind

INVALID = "That API key isn't valid."
REVOKED = "That API key has been revoked."
OWNER_LEFT = "This key's owner is no longer in the workspace. Make a new key in Amplychat."


class CredentialRefused(Exception):
    """The bearer token doesn't authenticate. ``unknown``: it isn't any credential of ours (the
    caller's IP pays for it, so guessing is slow)."""

    def __init__(self, message: str, *, unknown: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.unknown = unknown


async def principal_for_api_key(session: AsyncSession, redis: Redis, raw: str) -> McpPrincipal:
    """The principal ``raw`` (an ``shk_`` key) acts as, or ``CredentialRefused``."""
    key = await find_key(session, raw)
    if key is None:
        raise CredentialRefused(INVALID, unknown=True)
    if key.revoked_at is not None:
        raise CredentialRefused(REVOKED)
    workspace = await session.get(Workspace, key.workspace_id)
    if workspace is None or workspace.status != WorkspaceStatus.ACTIVE:
        raise CredentialRefused(INVALID)
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
