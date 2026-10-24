"""WhatsApp broadcasts (GR-23). Owners and admins only. The rules are in services/broadcasts.

With BROADCASTS_ENABLED off (the default until the legal check of marketing consent, O-11) every
route except ``GET /broadcasts/availability`` answers 404 "Broadcasts aren't available yet.", and
the availability route says ``enabled: false`` so the web shows nothing.

Plans: Pro and Max (PD-4). A write on a plan without broadcasts is 402 ``entitlement_required``;
one that would pass the month's recipients is 402 ``quota_exceeded``.

Every route needs the automations permission (GR-19): broadcasts are marketing sends, managed by
owners and admins as automations are.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import CanManageAutomations, Session
from socialhood.errors import ApiError
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.schemas.broadcasts import (
    Broadcast,
    BroadcastAvailability,
    BroadcastCreate,
    BroadcastDraft,
    BroadcastList,
    BroadcastPreview,
    BroadcastStart,
    BroadcastUpdate,
    RecipientList,
)
from socialhood.services.broadcasts import service

router = APIRouter(prefix="/v1/w/{wid}", tags=["broadcasts"])
log = get_logger(__name__)
log = get_logger(__name__)

StatusFilter = Literal[
    "draft", "scheduled", "sending", "paused", "completed", "cancelled", "failed"
]
RecipientFilter = Literal["queued", "sent", "delivered", "read", "failed", "skipped"]


def _enabled(request: Request) -> None:
    if not request.app.state.settings.broadcasts_enabled:
        raise ApiError("not_found", service.NOT_AVAILABLE)


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


async def _send_first_batch(ctx_workspace: uuid.UUID, broadcast_id: uuid.UUID) -> None:
    """Queue the first batch once the commit is done; the minutely sweeper is the safety net."""
    from socialhood.jobs.tasks.broadcasts import queue_batch

    try:
        await queue_batch(ctx_workspace, broadcast_id)
    except Exception:  # the sweeper picks it up within a minute
        log.warning("broadcast_enqueue_failed", broadcast_id=str(broadcast_id))


@router.get("/broadcasts/availability", operation_id="get_broadcast_availability")
async def get_broadcast_availability(
    request: Request, ctx: CanManageAutomations, session: Session
) -> BroadcastAvailability:
    """Whether broadcasts are switched on, what the plan allows this month and Meta's rate card."""
    return await service.availability(
        session,
        enabled=request.app.state.settings.broadcasts_enabled,
        now=datetime.now(UTC),
    )


@router.get("/broadcasts", operation_id="list_broadcasts")
async def list_broadcasts(
    request: Request,
    ctx: CanManageAutomations,
    session: Session,
    status: StatusFilter | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> BroadcastList:
    """Newest first, each with its counts."""
    _enabled(request)
    return await service.list_out(session, status=status, limit=limit, offset=offset)


@router.post("/broadcasts/preview", operation_id="preview_broadcast")
async def preview_broadcast(
    request: Request, body: BroadcastDraft, ctx: CanManageAutomations, session: Session
) -> BroadcastPreview:
    """Who would get it, who is skipped and why, what Meta's rate card says it costs, whether it
    fits the plan's recipients and the number's daily limit, and the message with a sample
    contact. 402 on a plan without broadcasts; 404 for a number or segment of another workspace;
    422 names what doesn't fit the template."""
    _enabled(request)
    return await service.preview(
        session, request.app.state.redis, _deps(request), body, now=datetime.now(UTC)
    )


@router.post("/broadcasts", status_code=201, operation_id="create_broadcast")
async def create_broadcast(
    request: Request, body: BroadcastCreate, ctx: CanManageAutomations, session: Session
) -> Broadcast:
    """Save a draft. Nothing is sent until it is started."""
    _enabled(request)
    out = await service.create(
        session,
        request.app.state.redis,
        _deps(request),
        body,
        user_id=ctx.user.id,
        now=datetime.now(UTC),
    )
    await session.commit()
    return out


@router.get("/broadcasts/{broadcast_id}", operation_id="get_broadcast")
async def get_broadcast(
    request: Request, broadcast_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Broadcast:
    _enabled(request)
    return await service.get_out(session, broadcast_id)


@router.patch("/broadcasts/{broadcast_id}", operation_id="update_broadcast")
async def update_broadcast(
    request: Request,
    broadcast_id: uuid.UUID,
    body: BroadcastUpdate,
    ctx: CanManageAutomations,
    session: Session,
) -> Broadcast:
    """Change a draft or scheduled broadcast; 409 once it has started."""
    _enabled(request)
    out = await service.update(session, request.app.state.redis, _deps(request), broadcast_id, body)
    await session.commit()
    return out


@router.delete("/broadcasts/{broadcast_id}", status_code=204, operation_id="delete_broadcast")
async def delete_broadcast(
    request: Request, broadcast_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Response:
    """Delete a draft, a cancelled or a failed broadcast; 409 for one that was sent."""
    _enabled(request)
    await service.delete(session, broadcast_id)
    await session.commit()
    return Response(status_code=204)


@router.get("/broadcasts/{broadcast_id}/recipients", operation_id="list_broadcast_recipients")
async def list_broadcast_recipients(
    request: Request,
    broadcast_id: uuid.UUID,
    ctx: CanManageAutomations,
    session: Session,
    status: RecipientFilter | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> RecipientList:
    """The audience, by position, with each person's status; failed and skipped ones say why."""
    _enabled(request)
    return await service.recipients(
        session, broadcast_id, status=status, limit=limit, offset=offset
    )


@router.post("/broadcasts/{broadcast_id}/start", operation_id="start_broadcast")
async def start_broadcast(
    request: Request,
    broadcast_id: uuid.UUID,
    body: BroadcastStart,
    ctx: CanManageAutomations,
    session: Session,
) -> Broadcast:
    """Send now, or at ``scheduled_at``. 402 without the plan or past the month's recipients, 409
    if it has already finished, 422 when no one can be sent to."""
    _enabled(request)
    out, sending = await service.start(
        session,
        request.app.state.redis,
        _deps(request),
        broadcast_id,
        scheduled_at=body.scheduled_at,
        now=datetime.now(UTC),
    )
    await session.commit()
    if sending:
        await _send_first_batch(ctx.workspace_id, broadcast_id)
    return out


@router.post("/broadcasts/{broadcast_id}/pause", operation_id="pause_broadcast")
async def pause_broadcast(
    request: Request, broadcast_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Broadcast:
    _enabled(request)
    out = await service.pause(session, broadcast_id)
    await session.commit()
    return out


@router.post("/broadcasts/{broadcast_id}/resume", operation_id="resume_broadcast")
async def resume_broadcast(
    request: Request, broadcast_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Broadcast:
    """Resume a paused broadcast; 409 while the number's quality is Low."""
    _enabled(request)
    out, sending = await service.resume(
        session, _deps(request), broadcast_id, now=datetime.now(UTC)
    )
    await session.commit()
    if sending:
        await _send_first_batch(ctx.workspace_id, broadcast_id)
    return out


@router.post("/broadcasts/{broadcast_id}/cancel", operation_id="cancel_broadcast")
async def cancel_broadcast(
    request: Request, broadcast_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Broadcast:
    """Stop for good: everyone still waiting is skipped. Messages already handed over still go."""
    _enabled(request)
    out = await service.cancel(session, broadcast_id)
    await session.commit()
    return out
