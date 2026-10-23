"""Reports (GR-34; roadmap P3): the weekly report, the page behind the digest email's link. Any
member reads it; there is no public link (the page needs a signed-in workspace member). The rules
are in services/reports.py."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request

from socialhood.auth.deps import AnyMember, Session
from socialhood.platforms.deps import deps_from
from socialhood.schemas.reports import WeeklyReport
from socialhood.services import reports
from socialhood.services.analytics.common import View, capabilities_from

router = APIRouter(prefix="/v1/w/{wid}", tags=["reports"])


@router.get("/reports/weekly", operation_id="get_weekly_report")
async def get_weekly_report(
    request: Request,
    ctx: AnyMember,
    session: Session,
    week: Annotated[date | None, Query()] = None,
) -> WeeklyReport:
    """A finished week against the week before, and the last 8 weeks of each count. ``week`` is
    the Monday it starts (default: the latest finished week); a day that is not a Monday, a week
    still running or one over a year back is 422. Gaps are null with the days they cover, never
    zeros."""
    deps = deps_from(request.app.state.http, request.app.state.settings)
    now = datetime.now(UTC)
    view = View(timezone=ctx.workspace.timezone, now=now, capabilities=capabilities_from(deps))
    monday = reports.ask_for(week, ctx.workspace.timezone, now)
    return await reports.build(session, view, ctx.workspace, week_start=monday)
