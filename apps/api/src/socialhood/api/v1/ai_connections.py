"""AI connections settings (C-165; 01-design.md §6.7): the workspace's switch for what AI apps
connected over MCP (/mcp) may do. Owners and admins, with the integrations permission like API
keys. Settings, Connected AI apps (phase C) shows it.

- ``off``: no tool runs (get_workspace still answers, to say so);
- ``read_only``: reads; ``read_drafts``: reads and drafts; ``full``: writes too.

The plan caps it (``ai_connections``, D2): Free can choose up to ``read_drafts`` (402
entitlement_required beyond it). A workspace that moves to Free keeps its setting and is capped;
back on Pro, the setting applies again.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from socialhood.auth.deps import CanManageIntegrations, Session
from socialhood.billing.entitlements import entitlement_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.mcp.calls import effective_mode
from socialhood.models.identity import Workspace
from socialhood.schemas.common import RequestModel, ResponseModel
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
