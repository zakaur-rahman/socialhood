"""Automations API (T4.3; FR-AUT-01…04, 12…17, 19; F-11): templates, drafts, the whole-definition
PUT with overlap warnings, activation with every missing field, pause, priorities, duplicate,
delete, runs, stats and a test that sends nothing. Admins only (§2.15).

The signatures below are the P4 contract; T4.3 implements the bodies.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from socialhood.auth.deps import Admin, Session
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

router = APIRouter(prefix="/v1/w/{wid}", tags=["automations"])

# Stub until T4.3 lands: the tenancy suite skips x-pending routes. Delete this and the
# openapi_extra arguments when implementing.
PENDING = {"x-pending": "T4.3"}

SortName = Literal["recent_runs", "name", "created"]


@router.get(
    "/automation-templates", operation_id="list_automation_templates", openapi_extra=PENDING
)
async def list_automation_templates(ctx: Admin) -> AutomationTemplateList:
    raise NotImplementedError("T4.3")


@router.get("/automations", operation_id="list_automations", openapi_extra=PENDING)
async def list_automations(
    ctx: Admin,
    session: Session,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[StatusName | None, Query()] = None,
    trigger: Annotated[TriggerName | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[SortName, Query()] = "recent_runs",
) -> AutomationList:
    raise NotImplementedError("T4.3")


@router.get("/automations/summary", operation_id="get_automations_summary", openapi_extra=PENDING)
async def get_automations_summary(ctx: Admin, session: Session) -> AutomationsSummary:
    raise NotImplementedError("T4.3")


@router.post(
    "/automations", status_code=201, operation_id="create_automation", openapi_extra=PENDING
)
async def create_automation(body: AutomationCreate, ctx: Admin, session: Session) -> Automation:
    """A draft, blank or filled from a template (FR-AUT-12)."""
    raise NotImplementedError("T4.3")


@router.put(
    "/automations/priorities",
    status_code=204,
    operation_id="update_automation_priorities",
    openapi_extra=PENDING,
)
async def update_automation_priorities(
    body: PrioritiesUpdate, ctx: Admin, session: Session
) -> Response:
    """The account's automations in their new order (FR-AUT-15)."""
    raise NotImplementedError("T4.3")


@router.post(
    "/automations/pause", status_code=204, operation_id="pause_automations", openapi_extra=PENDING
)
async def pause_automations(body: BulkPause, ctx: Admin, session: Session) -> Response:
    """Bulk pause from the list (FR-AUT-19)."""
    raise NotImplementedError("T4.3")


@router.get("/automations/{automation_id}", operation_id="get_automation", openapi_extra=PENDING)
async def get_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Automation:
    raise NotImplementedError("T4.3")


@router.put("/automations/{automation_id}", operation_id="update_automation", openapi_extra=PENDING)
async def update_automation(
    automation_id: uuid.UUID, body: AutomationDefinition, ctx: Admin, session: Session
) -> Automation:
    """Replace the whole definition (autosave). Returns overlaps and what activation still needs."""
    raise NotImplementedError("T4.3")


@router.delete(
    "/automations/{automation_id}",
    status_code=204,
    operation_id="delete_automation",
    openapi_extra=PENDING,
)
async def delete_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    raise NotImplementedError("T4.3")


@router.post(
    "/automations/{automation_id}/activate",
    operation_id="activate_automation",
    openapi_extra=PENDING,
)
async def activate_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Automation:
    """Validate (FR-AUT-02) and entitlements; 422 lists every missing or invalid field."""
    raise NotImplementedError("T4.3")


@router.post(
    "/automations/{automation_id}/pause", operation_id="pause_automation", openapi_extra=PENDING
)
async def pause_automation(automation_id: uuid.UUID, ctx: Admin, session: Session) -> Automation:
    raise NotImplementedError("T4.3")


@router.post(
    "/automations/{automation_id}/duplicate",
    status_code=201,
    operation_id="duplicate_automation",
    openapi_extra=PENDING,
)
async def duplicate_automation(
    automation_id: uuid.UUID, ctx: Admin, session: Session
) -> Automation:
    raise NotImplementedError("T4.3")


@router.get(
    "/automations/{automation_id}/runs",
    operation_id="list_automation_runs",
    openapi_extra=PENDING,
)
async def list_automation_runs(
    automation_id: uuid.UUID,
    ctx: Admin,
    session: Session,
    result: Annotated[RunResultName | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AutomationRunList:
    raise NotImplementedError("T4.3")


@router.get(
    "/automations/{automation_id}/stats",
    operation_id="get_automation_stats",
    openapi_extra=PENDING,
)
async def get_automation_stats(
    automation_id: uuid.UUID,
    ctx: Admin,
    session: Session,
    days: Annotated[Literal[7, 30], Query()] = 7,
) -> AutomationStats:
    raise NotImplementedError("T4.3")


@router.post(
    "/automations/{automation_id}/test", operation_id="test_automation", openapi_extra=PENDING
)
async def test_automation(
    automation_id: uuid.UUID, body: AutomationTest, ctx: Admin, session: Session
) -> AutomationTestResult:
    """What would happen for this text; sends nothing."""
    raise NotImplementedError("T4.3")
