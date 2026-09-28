"""Scheduled messages (T3.13; F-10, FR-SMS-01...03, UX-INB-10): schedule a reply in a
conversation, list them (per conversation and in the inbox's Scheduled tab), edit and cancel.

The rules are in services/scheduled.py; sending at the due time is the dispatcher's job
(jobs/tasks/scheduled.py).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import AnyMember, Session
from socialhood.realtime import events
from socialhood.schemas.inbox import (
    ScheduledMessage,
    ScheduledMessageCreate,
    ScheduledMessageList,
    ScheduledMessagePatch,
)
from socialhood.services import scheduled as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["scheduled"])


def _human_agent_enabled(request: Request) -> bool:
    return bool(request.app.state.settings.ig_human_agent_enabled)


@router.get("/scheduled-messages", operation_id="list_scheduled_messages")
async def list_scheduled_messages(
    ctx: AnyMember,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ScheduledMessageList:
    """The Scheduled tab: pending first by send time, then recent sent, failed and expired."""
    return await service.list_tab(session, cursor=cursor, limit=limit, now=datetime.now(UTC))


@router.get(
    "/conversations/{conversation_id}/scheduled-messages",
    operation_id="list_conversation_scheduled_messages",
)
async def list_conversation_scheduled_messages(
    conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> ScheduledMessageList:
    """The conversation's pending (scheduled or sending) messages, soonest first."""
    return await service.list_for_conversation(session, conversation_id)


@router.post(
    "/conversations/{conversation_id}/scheduled-messages",
    status_code=201,
    operation_id="create_scheduled_message",
)
async def create_scheduled_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: ScheduledMessageCreate,
    ctx: AnyMember,
    session: Session,
) -> ScheduledMessage:
    """send_at must be at least 2 minutes away and 5 minutes before the reply window closes."""
    out = await service.create(
        session,
        conversation_id,
        body,
        user_id=ctx.user.id,
        human_agent_enabled=_human_agent_enabled(request),
        now=datetime.now(UTC),
    )
    await events.commit_and_publish(session, request.app.state.redis)
    return out


@router.patch("/scheduled-messages/{scheduled_message_id}", operation_id="update_scheduled_message")
async def update_scheduled_message(
    request: Request,
    scheduled_message_id: uuid.UUID,
    body: ScheduledMessagePatch,
    ctx: AnyMember,
    session: Session,
) -> ScheduledMessage:
    """Edit the text or time while the message is still scheduled (409 conflict after that)."""
    out = await service.update(
        session,
        scheduled_message_id,
        body,
        human_agent_enabled=_human_agent_enabled(request),
        now=datetime.now(UTC),
    )
    await events.commit_and_publish(session, request.app.state.redis)
    return out


@router.delete(
    "/scheduled-messages/{scheduled_message_id}",
    status_code=204,
    operation_id="cancel_scheduled_message",
)
async def cancel_scheduled_message(
    request: Request, scheduled_message_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    """Cancel while the message is still scheduled (409 conflict after that)."""
    await service.cancel(session, scheduled_message_id)
    await events.commit_and_publish(session, request.app.state.redis)
    return Response(status_code=204)
