"""Business hours routes (GR-22). Any member reads the schedules; owners and admins change them.
The rules are in services/business_hours.py. Another workspace's account is 404 not_found."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.schemas.business_hours import (
    BusinessHours,
    BusinessHoursOverview,
    BusinessHoursUpdate,
)
from socialhood.services import business_hours as service
from socialhood.services import connections

router = APIRouter(prefix="/v1/w/{wid}", tags=["business-hours"])


@router.get("/business-hours", operation_id="get_business_hours")
async def get_business_hours(ctx: AnyMember, session: Session) -> BusinessHoursOverview:
    """The workspace's schedule (in its time zone), and each account's own when it differs."""
    return await service.overview(session, now=datetime.now(UTC))


@router.put("/business-hours", operation_id="update_business_hours")
async def update_business_hours(
    body: BusinessHoursUpdate, ctx: Admin, session: Session
) -> BusinessHours:
    """Replace the workspace's schedule. 422 names each field: an overlapping range, a closing
    time before the opening one, an away message left empty, hours switched on with no range."""
    out = await service.save(session, body, account_id=None, now=datetime.now(UTC))
    await session.commit()
    return out


@router.put("/social-accounts/{account_id}/business-hours", operation_id="update_account_hours")
async def update_account_hours(
    account_id: uuid.UUID, body: BusinessHoursUpdate, ctx: Admin, session: Session
) -> BusinessHours:
    """Give the account its own schedule, which replaces the workspace's for it. Switched off, it
    has no hours and is always open."""
    acct = await connections.get_or_404(session, account_id)
    out = await service.save(session, body, account_id=acct.id, now=datetime.now(UTC))
    await session.commit()
    return out


@router.delete(
    "/social-accounts/{account_id}/business-hours",
    status_code=204,
    operation_id="delete_account_hours",
)
async def delete_account_hours(account_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    """The account goes back to the workspace's schedule."""
    acct = await connections.get_or_404(session, account_id)
    await service.remove_override(session, acct.id)
    await session.commit()
    return Response(status_code=204)
