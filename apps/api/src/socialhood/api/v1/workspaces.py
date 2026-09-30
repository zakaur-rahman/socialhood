"""Workspace settings (FR-ACC-03) and the Home overview (FR-HOME-01, UX-SCR-01: the metrics of
services/overview.py, the onboarding checklist of FR-ACC-04 and FR-KB-06's open questions)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import select

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.models.billing import Subscription
from socialhood.repositories import users
from socialhood.schemas.workspaces import Overview, OverviewRange, WorkspaceOut, WorkspacePatch
from socialhood.services import overview as overview_service
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
async def get_overview(ctx: AnyMember, session: Session, range: OverviewRange = "7d") -> Overview:
    """Home's metrics over the last 7 or 30 days (today included) in the workspace's time zone,
    with the same number of days before them for comparison."""
    return await overview_service.overview(
        session, ctx.workspace, range_=range, now=datetime.now(UTC)
    )
