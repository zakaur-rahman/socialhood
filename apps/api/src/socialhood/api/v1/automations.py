"""Automations API (T4.3; FR-AUT-01…04, 12…17, 19; F-11): templates, drafts, the whole-definition
PUT with overlap warnings, activation with every missing field, pause, priorities, duplicate,
delete, runs, stats and a test that sends nothing. Admins only (§2.15).

The rules are in services/automations/: definitions.py (writes), queries.py (the projection,
list and run log), stats.py (figures), dry_run.py (the test) and templates.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from socialhood.auth.deps import Admin, Session, WorkspaceContext
from socialhood.billing.plans import current_plan
from socialhood.schemas.automations import (
    Automation,
    AutomationCreate,
    AutomationDefinition,
    AutomationList,
    AutomationRunList,
    AutomationsSummary,
    AutomationStats,
    AutomationTemplateList,
    AutomationTest,
    AutomationTestResult,
    BulkPause,
    PrioritiesUpdate,
    RunResultName,
    StatusName,
    TriggerName,
)
from socialhood.services.automations import definitions, dry_run, queries, stats, templates

router = APIRouter(prefix="/v1/w/{wid}", tags=["automations"])

SortName = Literal["recent_runs", "name", "created"]


def _view(ctx: WorkspaceContext, now: datetime) -> queries.View:
    workspace = ctx.workspace
    return queries.View(
        disclosure=workspace.automation_disclosure, timezone=workspace.timezone, now=now
    )


@router.get("/automation-templates", operation_id="list_automation_templates")
async def list_automation_templates(ctx: Admin) -> AutomationTemplateList:
    return templates.gallery()


@router.get("/automations", operation_id="list_automations")
async def list_automations(
    ctx: Admin,
    session: Session,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[StatusName | None, Query()] = None,
    trigger: Annotated[TriggerName | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[SortName, Query()] = "recent_runs",
) -> AutomationList:
    """Every matching automation (no paging); ``q`` searches names and keywords."""
    return await queries.list_automations(
        session,
        account_id=account_id,
        status=status,
        trigger=trigger,
        q=q,
        sort=sort,
        view=_view(ctx, datetime.now(UTC)),
    )


@router.get("/automations/summary", operation_id="get_automations_summary")
async def get_automations_summary(ctx: Admin, session: Session) -> AutomationsSummary:
    return await stats.summary(session, timezone=ctx.workspace.timezone, now=datetime.now(UTC))


@router.post("/automations", status_code=201, operation_id="create_automation")
async def create_automation(body: AutomationCreate, ctx: Admin, session: Session) -> Automation:
    """A draft, blank or filled from a template (FR-AUT-12)."""
    now = datetime.now(UTC)
    automation = await definitions.create(session, body, user_id=ctx.user.id, now=now)
    await session.commit()
    return await queries.one(session, automation.id, _view(ctx, now))


@router.put("/automations/priorities", status_code=204, operation_id="update_automation_priorities")
async def update_automation_priorities(
    body: PrioritiesUpdate, ctx: Admin, session: Session
) -> Response:
    """The account's automations in their new order (FR-AUT-15)."""
    await definitions.reorder(session, body.social_account_id, body.ordered_ids)
    await session.commit()
    return Response(status_code=204)


@router.post("/automations/pause", status_code=204, operation_id="pause_automations")
async def pause_automations(body: BulkPause, ctx: Admin, session: Session) -> Response:
    """Bulk pause from the list (FR-AUT-19)."""
    await definitions.pause_many(session, body.ids, now=datetime.now(UTC))
    await session.commit()
    return Response(status_code=204)


@router.get("/automations/{automation_id}", operation_id="get_automation")
async def get_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Automation:
    return await queries.one(session, automation_id, _view(ctx, datetime.now(UTC)))


@router.put("/automations/{automation_id}", operation_id="update_automation")
async def update_automation(
    automation_id: uuid.UUID, body: AutomationDefinition, ctx: Admin, session: Session
) -> Automation:
    """Replace the whole definition (autosave). Returns overlaps and what activation still needs.
    An active automation must stay complete: 422 lists what the change would break."""
    now = datetime.now(UTC)
    await definitions.update(
        session,
        automation_id,
        body,
        disclosure=ctx.workspace.automation_disclosure,
        now=now,
    )
    await session.commit()
    return await queries.one(session, automation_id, _view(ctx, now))


@router.delete("/automations/{automation_id}", status_code=204, operation_id="delete_automation")
async def delete_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    await definitions.delete(session, automation_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/automations/{automation_id}/activate", operation_id="activate_automation")
async def activate_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Automation:
    """Validate (FR-AUT-02) and entitlements; 422 lists every missing or invalid field."""
    now = datetime.now(UTC)
    await definitions.activate(
        session,
        automation_id,
        plan=await current_plan(session),
        disclosure=ctx.workspace.automation_disclosure,
        now=now,
    )
    await session.commit()
    return await queries.one(session, automation_id, _view(ctx, now))


@router.post("/automations/{automation_id}/pause", operation_id="pause_automation")
async def pause_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Automation:
    now = datetime.now(UTC)
    await definitions.pause(session, automation_id, now=now)
    await session.commit()
    return await queries.one(session, automation_id, _view(ctx, now))


@router.post(
    "/automations/{automation_id}/duplicate",
    status_code=201,
    operation_id="duplicate_automation",
)
async def duplicate_automation(
    automation_id: uuid.UUID, ctx: Admin, session: Session
) -> Automation:
    """A draft copy named "… (copy)"."""
    now = datetime.now(UTC)
    copy = await definitions.duplicate(session, automation_id, user_id=ctx.user.id, now=now)
    await session.commit()
    return await queries.one(session, copy.id, _view(ctx, now))


@router.get("/automations/{automation_id}/runs", operation_id="list_automation_runs")
async def list_automation_runs(
    automation_id: uuid.UUID,
    ctx: Admin,
    session: Session,
    result: Annotated[RunResultName | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationRunList:
    """The run log, newest first (FR-AUT-04)."""
    await definitions.get_or_404(session, automation_id)
    return await queries.list_runs(
        session, automation_id, result=result, cursor=cursor, limit=limit
    )


@router.get("/automations/{automation_id}/stats", operation_id="get_automation_stats")
async def get_automation_stats(
    automation_id: uuid.UUID,
    ctx: Admin,
    session: Session,
    days: Annotated[Literal[7, 30], Query()] = 7,
) -> AutomationStats:
    """Figures and the daily series for the last 7 or 30 days (FR-AUT-16)."""
    automation = await definitions.get_or_404(session, automation_id)
    return await stats.automation_stats(
        session, automation, days=days, timezone=ctx.workspace.timezone, now=datetime.now(UTC)
    )


@router.post("/automations/{automation_id}/test", operation_id="test_automation")
async def test_automation(
    automation_id: uuid.UUID, body: AutomationTest, ctx: Admin, session: Session
) -> AutomationTestResult:
    """What would happen for this text; sends nothing."""
    automation = await definitions.get_or_404(session, automation_id)
    return await dry_run.run(
        session,
        automation,
        body,
        disclosure=ctx.workspace.automation_disclosure,
        now=datetime.now(UTC),
    )
