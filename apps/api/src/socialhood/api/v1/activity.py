"""The Activity page API (GR-05): what automations and sends did, what failed and why.

Owners and admins, like the automations it reports on and Settings, Integrations: the list names
contacts and webhook endpoints. Agents can still retry a failed message from the inbox (the
message retry route), which the Activity page also uses. One read route; retries go through the
existing message retry and webhook replay routes (each item says which and for what).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from socialhood.auth.deps import Admin, Session
from socialhood.schemas.activity import ActivityList
from socialhood.services.activity import feed as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["activity"])

KindFilter = service.Kind


@router.get("/activity", operation_id="list_activity")
async def list_activity(
    ctx: Admin,
    session: Session,
    failures_only: Annotated[bool, Query()] = True,
    kind: Annotated[KindFilter | None, Query()] = None,
    automation_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ActivityList:
    """Automation runs, failed sends, failed webhook deliveries and accounts that need
    attention, newest first. ``failures_only`` (the default) leaves out runs that worked."""
    return await service.feed(
        session,
        failures_only=failures_only,
        kind=kind,
        automation_id=automation_id,
        account_id=account_id,
        cursor=cursor,
        limit=limit,
    )
