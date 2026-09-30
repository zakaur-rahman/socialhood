"""Workspace settings (FR-ACC-03) and the Home overview (FR-HOME-01, UX-SCR-01: the metrics of
services/overview.py, the onboarding checklist of FR-ACC-04 and FR-KB-06's open questions)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.errors import ApiError, FieldError
from socialhood.models.billing import Subscription
from socialhood.repositories import users
from socialhood.schemas.workspaces import Overview, OverviewPreset, WorkspaceOut, WorkspacePatch
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
async def get_overview(
    request: Request,
    ctx: AnyMember,
    session: Session,
    range: OverviewPreset | None = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> Overview:
    """Home's metrics over the last 7 or 30 days (``range``, 7d by default; today included), or
    the local days ``from`` to ``to`` (YYYY-MM-DD, both included, at most 90 days, ``to`` no
    later than today), in the workspace's time zone, with the same number of days before them
    for comparison. ``range`` with ``from`` or ``to`` is 422."""
    custom = from_ is not None or to is not None
    if custom and range is not None:
        raise ApiError(
            "validation_error",
            "Use range, or from and to.",
            errors=[FieldError("range", "Leave out range when giving from and to.")],
        )
    return await overview_service.overview(
        session,
        ctx.workspace,
        range_="custom" if custom else (range or "7d"),
        since=from_,
        until=to,
        now=datetime.now(UTC),
        human_agent=bool(request.app.state.settings.ig_human_agent_enabled),
    )
