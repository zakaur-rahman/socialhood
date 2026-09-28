"""Sending (T3.6; FR-INB-06, 07, 10; TR-API-05, TR-JOB-04, TR-JOB-05, TR-PL-10): POST a reply
(idempotent; role, account and window checks; 202 with the queued message) and retry a failed one.

The signatures below are the P3 contract; T3.6 implements the bodies.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.inbox import Message, SendMessage

router = APIRouter(prefix="/v1/w/{wid}", tags=["inbox"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


# Stub until T3.6 lands: the tenancy suite skips x-pending routes. Delete this and the
# openapi_extra arguments when implementing.
PENDING = {"x-pending": "T3.6"}


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=202,
    operation_id="send_message",
    openapi_extra=PENDING,
)
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessage,
    idempotency_key: IdempotencyKey,
    ctx: AnyMember,
    session: Session,
) -> Message:
    raise NotImplementedError("T3.6")


@router.post(
    "/messages/{message_id}/retry",
    status_code=202,
    operation_id="retry_message",
    openapi_extra=PENDING,
)
async def retry_message(message_id: uuid.UUID, ctx: AnyMember, session: Session) -> Message:
    raise NotImplementedError("T3.6")
