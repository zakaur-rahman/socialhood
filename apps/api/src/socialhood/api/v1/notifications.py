"""In-app notifications for the signed-in member (FR-NOT-01, UX-SH-04)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.accounts import MarkRead, NotificationList, NotificationOut
from socialhood.services import notifications as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["notifications"])


@router.get("/notifications", operation_id="list_notifications")
async def list_notifications(
    ctx: AnyMember,
    session: Session,
    cursor: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> NotificationList:
    items, unread = await service.list_for(session, ctx.user.id, limit=limit, before=cursor)
    page, more = items[:limit], len(items) > limit
    return NotificationList(
        items=[NotificationOut.model_validate(n) for n in page],
        next_cursor=page[-1].created_at.isoformat() if more else None,
        unread_count=unread,
    )


@router.post("/notifications/read", status_code=204, operation_id="mark_notifications_read")
async def mark_notifications_read(body: MarkRead, ctx: AnyMember, session: Session) -> Response:
    await service.mark_read(session, ctx.user.id, None if body.all else (body.ids or []))
    await session.commit()
    return Response(status_code=204)
