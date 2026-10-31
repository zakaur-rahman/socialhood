"""Settings, Connected AI apps (C-165 phase C; 01-design.md §3.5, §6.3, §6.7): a workspace's
OAuth connections, their recent tool calls, and revoking them. Nothing here commits.

- Owners and admins (the integrations permission, like API keys) see and revoke every
  connection; any other member sees and revokes their own (§3.5 "Who can connect").
- Only live connections are listed: revoked, expired and idle ones are gone for good (their
  tokens already stopped).
- Revoking takes effect on the next request of every token of the connection: access tokens
  and refresh tokens are checked against their connection each time (auth/mcp_oauth.py).
- Activity comes from the MCP audit, ``mcp_tool_calls`` (kept 90 days): tool, outcome and time,
  never arguments or results.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.identity import User
from socialhood.models.mcp import McpToolCall
from socialhood.models.oauth import ClientKind, McpConnection, OAuthClient, RevokeReason
from socialhood.oauth import clients, tokens
from socialhood.oauth.service import revoke_connection
from socialhood.schemas.ai_connections import (
    AiConnection,
    AiConnectionCall,
    AiConnectionMember,
)

RECENT = 5
ACTIVITY = 50


def verified_host(client: OAuthClient) -> str | None:
    return clients.redirect_host(client.client_id) if client.kind == ClientKind.CIMD.value else None


async def _live(
    session: AsyncSession, now: datetime, user_id: uuid.UUID | None
) -> list[tuple[McpConnection, OAuthClient, User]]:
    statement = (
        select(McpConnection, OAuthClient, User)
        .join(OAuthClient, OAuthClient.id == McpConnection.oauth_client_id)
        .join(User, User.id == McpConnection.user_id)
        .where(McpConnection.revoked_at.is_(None), McpConnection.expires_at > now)
        .order_by(McpConnection.created_at.desc())
    )
    if user_id is not None:
        statement = statement.where(McpConnection.user_id == user_id)
    rows = (await session.execute(statement)).tuples().all()
    return [r for r in rows if tokens.connection_problem(r[0], now) is None]


def _call(row: McpToolCall) -> AiConnectionCall:
    return AiConnectionCall.model_validate(row)


async def list_connections(
    session: AsyncSession, now: datetime, viewer_id: uuid.UUID, *, all_members: bool
) -> list[AiConnection]:
    rows = await _live(session, now, None if all_members else viewer_id)
    ids = [connection.id for connection, _, _ in rows]
    since = now - timedelta(days=7)
    counts: dict[uuid.UUID, int] = {}
    recent: dict[uuid.UUID, list[AiConnectionCall]] = defaultdict(list)
    if ids:
        counted = await session.execute(
            select(McpToolCall.connection_id, func.count())
            .where(McpToolCall.connection_id.in_(ids), McpToolCall.created_at >= since)
            .group_by(McpToolCall.connection_id)
        )
        counts = {cid: n for cid, n in counted.tuples().all() if cid is not None}
        ranked = (
            select(
                McpToolCall,
                func.row_number()
                .over(
                    partition_by=McpToolCall.connection_id, order_by=McpToolCall.created_at.desc()
                )
                .label("rank"),
            )
            .where(McpToolCall.connection_id.in_(ids))
            .subquery()
        )
        latest = await session.execute(
            select(McpToolCall)
            .join(ranked, ranked.c.id == McpToolCall.id)
            .where(ranked.c.rank <= RECENT)
            .order_by(McpToolCall.created_at.desc())
        )
        for call in latest.scalars().all():
            if call.connection_id is not None:
                recent[call.connection_id].append(_call(call))
    return [
        AiConnection(
            id=connection.id,
            client_name=connection.client_name,
            verified_host=verified_host(client),
            redirect_host=clients.redirect_host(connection.redirect_uri),
            member=AiConnectionMember(id=user.id, name=user.name, email=user.email),
            is_yours=connection.user_id == viewer_id,
            scopes=list(connection.scopes),
            created_at=connection.created_at,
            last_used_at=connection.last_used_at,
            expires_at=min(
                connection.expires_at,
                (connection.last_used_at or connection.created_at) + tokens.IDLE_LIMIT,
            ),
            calls_7d=counts.get(connection.id, 0),
            recent_calls=recent.get(connection.id, []),
        )
        for connection, client, user in rows
    ]


async def get_visible(
    session: AsyncSession, connection_id: uuid.UUID, viewer_id: uuid.UUID, *, all_members: bool
) -> McpConnection:
    """The connection, when the viewer may see it; 404 otherwise (never 403, TR-API-03)."""
    connection = await session.get(McpConnection, connection_id)
    if connection is None or (not all_members and connection.user_id != viewer_id):
        raise ApiError("not_found", "That connection doesn't exist.")
    return connection


async def activity(session: AsyncSession, connection_id: uuid.UUID) -> list[AiConnectionCall]:
    rows = await session.scalars(
        select(McpToolCall)
        .where(McpToolCall.connection_id == connection_id)
        .order_by(McpToolCall.created_at.desc())
        .limit(ACTIVITY)
    )
    return [_call(row) for row in rows.all()]


async def revoke_all(session: AsyncSession, now: datetime, by_user_id: uuid.UUID) -> int:
    rows = await session.scalars(select(McpConnection).where(McpConnection.revoked_at.is_(None)))
    return sum(revoke_connection(c, RevokeReason.ALL, now, by_user_id) for c in rows.all())


async def revoke_one(
    session: AsyncSession, connection: McpConnection, now: datetime, by_user_id: uuid.UUID
) -> bool:
    return revoke_connection(connection, RevokeReason.MEMBER, now, by_user_id)
