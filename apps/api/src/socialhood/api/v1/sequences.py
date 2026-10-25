"""Sequences (GR-24): timed follow-up messages after an entry event. Owners and admins manage them
(the automations permission, GR-19); the rules are in services/sequences.

Plans: Free, Pro and Max with limits on how many sequences run at once and how many steps one has
(``active_sequences`` and ``sequence_steps``, pending the owner's confirmation, C-118). Past a
limit a write is 402 ``quota_exceeded``.

Steps and rules change only while a sequence is a draft or paused (409 otherwise). A contact's
sequences are readable by any member, on the contact's page.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import AnyMember, CanManageAutomations, Session
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.schemas.sequences import (
    ContactSequenceList,
    Enrolment,
    EnrolmentList,
    EnrolmentStatusName,
    Sequence,
    SequenceAnalytics,
    SequenceBody,
    SequenceList,
    SequencePreview,
)
from socialhood.services import audit
from socialhood.services.sequences import analytics, service

router = APIRouter(prefix="/v1/w/{wid}", tags=["sequences"])


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


@router.get("/sequences", operation_id="list_sequences")
async def list_sequences(ctx: CanManageAutomations, session: Session) -> SequenceList:
    """Newest first, each with its enrolment counts, and the plan's limits."""
    return await service.list_out(session)


@router.post("/sequences", status_code=201, operation_id="create_sequence")
async def create_sequence(
    request: Request, body: SequenceBody, ctx: CanManageAutomations, session: Session
) -> Sequence:
    """A draft. The steps are checked against the account (a template must be approved on the
    number) and the plan's step limit."""
    out = await service.create(
        session, request.app.state.redis, _deps(request), body, user_id=ctx.user.id
    )
    await audit.record(session, ctx, "sequence.created", "sequence", out.id)
    await session.commit()
    return out


@router.post("/sequences/preview", operation_id="preview_sequence")
async def preview_sequence(
    request: Request, body: SequenceBody, ctx: CanManageAutomations, session: Session
) -> SequencePreview:
    """The steps as a sample contact would meet them: when each is due after entry and what it
    would send. Nothing is saved or sent."""
    return await service.preview(session, request.app.state.redis, _deps(request), body)


@router.get("/sequences/{sequence_id}", operation_id="get_sequence")
async def get_sequence(
    sequence_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Sequence:
    return await service.get_out(session, sequence_id)


@router.put("/sequences/{sequence_id}", operation_id="update_sequence")
async def update_sequence(
    request: Request,
    sequence_id: uuid.UUID,
    body: SequenceBody,
    ctx: CanManageAutomations,
    session: Session,
) -> Sequence:
    """Replace the sequence and its steps. Only a draft or paused sequence (409 otherwise)."""
    out = await service.update(session, request.app.state.redis, _deps(request), sequence_id, body)
    await audit.record(session, ctx, "sequence.updated", "sequence", sequence_id)
    await session.commit()
    return out


@router.delete("/sequences/{sequence_id}", status_code=204, operation_id="delete_sequence")
async def delete_sequence(
    sequence_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Response:
    """With its enrolments and history. Not while it is active (409)."""
    await service.delete(session, sequence_id)
    await audit.record(session, ctx, "sequence.deleted", "sequence", sequence_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/sequences/{sequence_id}/activate", operation_id="activate_sequence")
async def activate_sequence(
    sequence_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Sequence:
    """Start taking people in (and carry on those already in it). 402 past the plan's limit."""
    out = await service.activate(session, sequence_id, now=datetime.now(UTC))
    await audit.record(session, ctx, "sequence.activated", "sequence", sequence_id)
    await session.commit()
    return out


@router.post("/sequences/{sequence_id}/pause", operation_id="pause_sequence")
async def pause_sequence(
    sequence_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Sequence:
    """Stop taking people in and sending steps. Those already in it keep their place."""
    out = await service.pause(session, sequence_id)
    await audit.record(session, ctx, "sequence.paused", "sequence", sequence_id)
    await session.commit()
    return out


@router.get("/sequences/{sequence_id}/enrolments", operation_id="list_sequence_enrolments")
async def list_sequence_enrolments(
    sequence_id: uuid.UUID,
    ctx: CanManageAutomations,
    session: Session,
    status: EnrolmentStatusName | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> EnrolmentList:
    """The people in the sequence, newest first: where each is, when the next step is due, and why
    a stopped one stopped."""
    return await service.enrolments(session, sequence_id, status=status, limit=limit, offset=offset)


@router.post(
    "/sequences/{sequence_id}/enrolments/{enrolment_id}/stop",
    operation_id="stop_sequence_enrolment",
)
async def stop_sequence_enrolment(
    sequence_id: uuid.UUID, enrolment_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> Enrolment:
    """Take one person out of the sequence."""
    out = await service.stop_enrolment(session, sequence_id, enrolment_id, now=datetime.now(UTC))
    await audit.record(session, ctx, "sequence.person_removed", "sequence", sequence_id)
    await session.commit()
    return out


@router.get("/sequences/{sequence_id}/analytics", operation_id="get_sequence_analytics")
async def get_sequence_analytics(
    request: Request, sequence_id: uuid.UUID, ctx: CanManageAutomations, session: Session
) -> SequenceAnalytics:
    """Who entered, how it went per step (sent, skipped and why, failed, replied) and the funnel.
    Computed on the server; cached for a few minutes."""
    return await analytics.get(session, request.app.state.redis, sequence_id, now=datetime.now(UTC))


@router.get("/contacts/{contact_id}/sequences", operation_id="list_contact_sequences")
async def list_contact_sequences(
    contact_id: uuid.UUID, ctx: AnyMember, session: Session
) -> ContactSequenceList:
    """The sequences a contact is in or has been in, with what happened at each step."""
    return await service.contact_sequences(session, contact_id)
