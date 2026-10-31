"""AI connections settings (C-165; 01-design.md §6.7): the workspace's switch for what AI apps
connected over MCP (/mcp) may do. Owners and admins, with the integrations permission like API
keys. Settings, Connected AI apps shows it.

Phase C adds the OAuth connections themselves: the list (with recent activity from the MCP
audit), one connection's activity, Disconnect, and Disconnect all.

- ``off``: no tool runs (get_workspace still answers, to say so);
- ``read_only``: reads; ``read_drafts``: reads and drafts; ``full``: writes too.

The plan caps it (``ai_connections``, D2): Free can choose up to ``read_drafts`` (402
entitlement_required beyond it). A workspace that moves to Free keeps its setting and is capped;
back on Pro, the setting applies again.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter

from socialhood.auth.deps import (
    AnyMember,
    CanManageIntegrations,
    CanSelf,
    Session,
    WorkspaceContext,
)
from socialhood.auth.permissions import Permission, has_permission
from socialhood.billing.entitlements import entitlement_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.mcp.calls import effective_mode
from socialhood.models.identity import Workspace
from socialhood.schemas.ai_connections import (
    AiConnectionActivity,
    AiConnectionList,
    AiConnectionsRevoked,
)
from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.services import ai_connections as connections
from socialhood.services import audit

router = APIRouter(prefix="/v1/w/{wid}", tags=["integrations"])

ModeName = Literal["off", "read_only", "read_drafts", "full"]


class AiConnectionsSettings(ResponseModel):
    mode: ModeName  # the workspace's setting
    effective_mode: ModeName  # the setting, capped by the plan: what AI apps may do now
    plan_allows: list[ModeName]  # the modes this plan can choose


class AiConnectionsUpdate(RequestModel):
    mode: ModeName


async def _out(session: Session, mode: str) -> AiConnectionsSettings:
    plan = await current_plan(session)
    return AiConnectionsSettings(
        mode=mode,
        effective_mode=effective_mode(mode, plan).value,
        plan_allows=list(entitlement(plan, "ai_connections")),
    )


@router.get("/ai-connections/settings", operation_id="get_ai_connections_settings")
async def get_settings(ctx: CanManageIntegrations, session: Session) -> AiConnectionsSettings:
    return await _out(session, ctx.workspace.ai_connections_mode)


@router.put("/ai-connections/settings", operation_id="update_ai_connections_settings")
async def update_settings(
    body: AiConnectionsUpdate, ctx: CanManageIntegrations, session: Session
) -> AiConnectionsSettings:
    """Takes effect on the next call of every connection. 402 entitlement_required for a mode
    beyond the plan (``full`` on Free)."""
    plan = await current_plan(session)
    if body.mode not in entitlement(plan, "ai_connections"):
        raise entitlement_error("ai_connections")
    workspace = await session.get(Workspace, ctx.workspace_id)
    assert workspace is not None  # the route's membership check found it
    before = workspace.ai_connections_mode
    if before != body.mode:
        workspace.ai_connections_mode = body.mode
        await audit.record(
            session,
            ctx,
            "ai_connections.mode_changed",
            "workspace",
            ctx.workspace_id,
            mode=body.mode,
            previous=before,
        )
        await session.commit()
    return await _out(session, body.mode)


# ---------------------------------------------------------------- connections (phase C)


def _manages_all(ctx: WorkspaceContext) -> bool:
    return has_permission(ctx.role, Permission.INTEGRATIONS_MANAGE)


@router.get("/ai-connections", operation_id="list_ai_connections")
async def list_connections(ctx: AnyMember, session: Session) -> AiConnectionList:
    """Live OAuth connections, newest first, with each one's tool calls in the last 7 days and
    its 5 latest. Owners and admins see everyone's; other members see their own."""
    manages = _manages_all(ctx)
    items = await connections.list_connections(
        session, datetime.now(UTC), ctx.user.id, all_members=manages
    )
    return AiConnectionList(items=items, can_manage_all=manages)


@router.get("/ai-connections/{connection_id}/activity", operation_id="get_ai_connection_activity")
async def get_activity(
    connection_id: uuid.UUID, ctx: AnyMember, session: Session
) -> AiConnectionActivity:
    """The connection's latest 50 tool calls (the MCP audit keeps 90 days)."""
    await connections.get_visible(
        session, connection_id, ctx.user.id, all_members=_manages_all(ctx)
    )
    return AiConnectionActivity(items=await connections.activity(session, connection_id))


@router.delete(
    "/ai-connections/{connection_id}",
    operation_id="revoke_ai_connection",
    status_code=204,
)
async def revoke_connection(connection_id: uuid.UUID, ctx: CanSelf, session: Session) -> None:
    """Disconnect: every token of it stops on its next request. Revoking again is a no-op.
    Every member may disconnect their own (``self.preferences``); owners and admins anyone's."""
    connection = await connections.get_visible(
        session, connection_id, ctx.user.id, all_members=_manages_all(ctx)
    )
    if await connections.revoke_one(session, connection, datetime.now(UTC), ctx.user.id):
        await audit.record(
            session,
            ctx,
            "ai_connections.revoked",
            "ai_connection",
            connection.id,
            client=connection.client_name,
        )
        await session.commit()


@router.post("/ai-connections/revoke-all", operation_id="revoke_all_ai_connections")
async def revoke_all(ctx: CanManageIntegrations, session: Session) -> AiConnectionsRevoked:
    """ "Disconnect all": every AI app connection in the workspace, at once (§6.7). API keys
    are separate (Settings, API keys)."""
    count = await connections.revoke_all(session, datetime.now(UTC), ctx.user.id)
    if count:
        await audit.record(
            session, ctx, "ai_connections.revoked_all", "workspace", ctx.workspace_id, count=count
        )
        await session.commit()
    return AiConnectionsRevoked(revoked=count)
