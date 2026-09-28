"""Workspace settings (FR-ACC-03) and the Home overview (FR-ACC-04; metrics arrive in T9.1)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.models.billing import Subscription
from socialhood.repositories import users
from socialhood.schemas.workspaces import Overview, WorkspaceOut, WorkspacePatch
from socialhood.services import workspaces as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["workspaces"])


async def _out(session: Session, ctx: AnyMember) -> WorkspaceOut:
    plan = await session.scalar(select(Subscription.plan))  # filtered to this workspace
    ws = ctx.workspace
    return WorkspaceOut.model_validate(
        {
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "timezone": ws.timezone,
            "reply_language": ws.reply_language,
            "status": ws.status,
            "role": ctx.role.value,
            "plan": plan or "free",
            "automation_disclosure": ws.automation_disclosure,
            "checklist_dismissed_at": ws.checklist_dismissed_at,
            "created_at": ws.created_at,
        }
    )


@router.get("", operation_id="get_workspace")
async def get_workspace(ctx: AnyMember, session: Session) -> WorkspaceOut:
    """Also remembers this workspace as the user's last one, for /app (F-02)."""
    await users.set_last_workspace(session, ctx.user.id, ctx.workspace_id)
    await session.commit()
    return await _out(session, ctx)


@router.patch("", operation_id="update_workspace")
async def update_workspace(body: WorkspacePatch, ctx: Admin, session: Session) -> WorkspaceOut:
    await service.update_workspace(session, ctx.workspace, body)
    return await _out(session, ctx)


@router.get("/overview", operation_id="get_overview")
async def get_overview(
    ctx: AnyMember, session: Session, range: Literal["7d", "30d"] = "7d"
) -> Overview:
    return Overview(range=range, checklist=await service.checklist(session, ctx.workspace))
