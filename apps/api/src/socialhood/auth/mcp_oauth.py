"""OAuth access tokens as MCP credentials, and the lookups behind the token endpoint (C-165
phase C; 01-design.md §3.2, §3.5, §3.6). In auth/ because finding a code or a token by its hash
is how we learn its workspace: the one cross-workspace lookup each (TR-TEN-04).

An access token (``sho_``) acts as the member who consented, with their *current* role, in the
one workspace they picked, with the scopes they allowed. It stops working at once when:

- it expires (one hour) or is revoked;
- its connection is revoked (Settings, Disconnect; a refresh token reused; the client's own
  revocation), expired (180 days) or idle (30 days);
- it was issued for another resource than this server's /mcp (RFC 8707 audience binding);
- the member left the workspace, or the workspace isn't active;
- its client is blocked by an operator.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.mcp.principal import ALWAYS_GRANTED, McpPrincipal
from socialhood.models.identity import Role, Workspace, WorkspaceMember, WorkspaceStatus
from socialhood.models.mcp import CredentialKind
from socialhood.models.oauth import McpConnection, OAuthClient, OAuthCode, OAuthToken, TokenKind
from socialhood.oauth import tokens

INVALID = "That access token isn't valid."
EXPIRED_TOKEN = "That access token has expired."  # noqa: S105  (a message)
WRONG_AUDIENCE = "That access token is for another server."
MEMBER_LEFT = "You're no longer a member of this workspace."
LAST_USED_EVERY_S = 60
# ChatGPT's linking UI wants the step-up on the tool result (_meta["mcp/www_authenticate"]);
# a client that follows the MCP spec gets an HTTP 403 with the scope challenge.
TOOL_RESULT_CHALLENGE_HOSTS = ("chatgpt.com", "openai.com")


class OAuthRefused(Exception):
    def __init__(self, message: str, *, unknown: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.unknown = unknown


async def find_code(
    session: AsyncSession, raw: str, *, for_update: bool = False
) -> OAuthCode | None:
    """The code ``raw`` is, used or not. ``for_update`` locks its row, so two exchanges of
    one code can't both see it unused."""
    if not tokens.looks_like(raw, tokens.CODE_PREFIX):
        return None
    statement = select(OAuthCode).where(OAuthCode.code_hash == tokens.hash_token(raw))
    if for_update:
        statement = statement.with_for_update()
    with tenant_bypass_scope():
        return (await session.scalars(statement)).one_or_none()


async def find_token(
    session: AsyncSession, raw: str, kind: TokenKind | None, *, for_update: bool = False
) -> OAuthToken | None:
    prefixes = {TokenKind.ACCESS: tokens.ACCESS_PREFIX, TokenKind.REFRESH: tokens.REFRESH_PREFIX}
    if kind is not None and not tokens.looks_like(raw, prefixes[kind]):
        return None
    if kind is None and not any(tokens.looks_like(raw, p) for p in prefixes.values()):
        return None
    statement = select(OAuthToken).where(OAuthToken.token_hash == tokens.hash_token(raw))
    if kind is not None:
        statement = statement.where(OAuthToken.kind == kind.value)
    if for_update:
        statement = statement.with_for_update()
    with tenant_bypass_scope():
        return (await session.scalars(statement)).one_or_none()


async def member_role(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> Role | None:
    """The member's role now, or None when they're not in the workspace (or it isn't active)."""
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None or workspace.status != WorkspaceStatus.ACTIVE:
        return None
    with workspace_scope(workspace_id):
        role = await session.scalar(
            select(WorkspaceMember.role).where(WorkspaceMember.user_id == user_id)
        )
    return Role(role) if role is not None else None


def challenge_style(client: OAuthClient) -> str:
    hosts = {tokens_host(uri) for uri in client.redirect_uris}
    if any(h == t or h.endswith("." + t) for h in hosts for t in TOOL_RESULT_CHALLENGE_HOSTS):
        return "tool_result"
    return "http"


def tokens_host(uri: str) -> str:
    try:
        return (urlsplit(uri).hostname or "").lower()
    except ValueError:
        return ""


async def principal_for_access_token(
    session: AsyncSession, redis: Redis, raw: str, *, resource: str, now: datetime | None = None
) -> McpPrincipal:
    now = now or datetime.now(UTC)
    token = await find_token(session, raw, TokenKind.ACCESS)
    if token is None:
        raise OAuthRefused(INVALID, unknown=True)
    if token.revoked_at is not None:
        raise OAuthRefused(tokens.REVOKED)
    if now >= token.expires_at:
        raise OAuthRefused(EXPIRED_TOKEN)
    with workspace_scope(token.workspace_id):
        connection = await session.get(McpConnection, token.connection_id)
        if connection is None:
            raise OAuthRefused(INVALID)
        problem = tokens.connection_problem(connection, now)
        if problem is not None:
            raise OAuthRefused(problem)
        if connection.resource != resource:
            raise OAuthRefused(WRONG_AUDIENCE)
        client = await session.get(OAuthClient, connection.oauth_client_id)
        if client is None or client.blocked_at is not None:
            raise OAuthRefused(tokens.REVOKED)
        role = await member_role(session, connection.workspace_id, connection.user_id)
        if role is None:
            raise OAuthRefused(MEMBER_LEFT)
        await _touch(redis, session, connection, client, now)
        return McpPrincipal(
            workspace_id=connection.workspace_id,
            user_id=connection.user_id,
            role=role,
            scopes=frozenset({*connection.scopes, ALWAYS_GRANTED}),
            credential=CredentialKind.OAUTH,
            credential_id=connection.id,
            credential_label=f"{connection.client_name} (connected app)",
            scope_challenge=challenge_style(client),
        )


async def _touch(
    redis: Redis,
    session: AsyncSession,
    connection: McpConnection,
    client: OAuthClient,
    now: datetime,
) -> None:
    """``last_used_at`` on the connection and its client, at most once a minute; a Valkey
    outage never blocks a request."""
    try:
        first = await redis.set(f"mcpconn-used:{connection.id}", "1", nx=True, ex=LAST_USED_EVERY_S)
    except Exception:
        return
    if first:
        connection.last_used_at = now
        client.last_used_at = now
        await session.commit()
