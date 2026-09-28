"""Scheduled messages (T3.13; F-10, FR-SMS-01...03): schedule a reply in a conversation, list
them (per conversation and in the inbox's Scheduled tab), edit and cancel.

The signatures below are the P3 contract; T3.13 implements the bodies.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.inbox import (
    ScheduledMessage,
    ScheduledMessageCreate,
    ScheduledMessageList,
    ScheduledMessagePatch,
)

router = APIRouter(prefix="/v1/w/{wid}", tags=["scheduled"])


# Stub until T3.13 lands: the tenancy suite skips x-pending routes. Delete this and the
# openapi_extra arguments when implementing.
PENDING = {"x-pending": "T3.13"}


@router.get("/scheduled-messages", operation_id="list_scheduled_messages", openapi_extra=PENDING)
async def list_scheduled_messages(
    ctx: AnyMember,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ScheduledMessageList:
    """The Scheduled tab: pending first by send time, then recent sent, failed and expired."""
    raise NotImplementedError("T3.13")


@router.get(
    "/conversations/{conversation_id}/scheduled-messages",
    operation_id="list_conversation_scheduled_messages",
    openapi_extra=PENDING,
)
async def list_conversation_scheduled_messages(
    conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> ScheduledMessageList:
    raise NotImplementedError("T3.13")


@router.post(
    "/conversations/{conversation_id}/scheduled-messages",
    status_code=201,
    operation_id="create_scheduled_message",
    openapi_extra=PENDING,
)
async def create_scheduled_message(
    conversation_id: uuid.UUID, body: ScheduledMessageCreate, ctx: AnyMember, session: Session
) -> ScheduledMessage:
    raise NotImplementedError("T3.13")


@router.patch(
    "/scheduled-messages/{scheduled_message_id}",
    operation_id="update_scheduled_message",
    openapi_extra=PENDING,
)
async def update_scheduled_message(
    scheduled_message_id: uuid.UUID,
    body: ScheduledMessagePatch,
    ctx: AnyMember,
    session: Session,
) -> ScheduledMessage:
    raise NotImplementedError("T3.13")


@router.delete(
    "/scheduled-messages/{scheduled_message_id}",
    status_code=204,
    operation_id="cancel_scheduled_message",
    openapi_extra=PENDING,
)
async def cancel_scheduled_message(
    scheduled_message_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    raise NotImplementedError("T3.13")
