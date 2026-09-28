"""Inbox read APIs (T3.5; FR-INB-01, 02, 04, 05; TR-API-04): the conversation list with views,
filters, search and cursor; conversation detail with the reply window; messages (keyset, newest
first); read, unread and archive.

The signatures below are the P3 contract; T3.5 implements the bodies.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.inbox import (
    Conversation,
    ConversationList,
    ConversationPatch,
    InboxCounts,
    InboxView,
    MessageList,
    PlatformName,
)

router = APIRouter(prefix="/v1/w/{wid}", tags=["inbox"])


# Stub until T3.5 lands: the tenancy suite skips x-pending routes. Delete this and the
# openapi_extra arguments when implementing.
PENDING = {"x-pending": "T3.5"}


@router.get("/conversations", operation_id="list_conversations", openapi_extra=PENDING)
async def list_conversations(
    ctx: AnyMember,
    session: Session,
    view: Annotated[InboxView, Query()] = "all",
    platform: Annotated[PlatformName | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ConversationList:
    raise NotImplementedError("T3.5")


@router.get("/conversations/counts", operation_id="get_inbox_counts", openapi_extra=PENDING)
async def get_inbox_counts(ctx: AnyMember, session: Session) -> InboxCounts:
    raise NotImplementedError("T3.5")


@router.get(
    "/conversations/{conversation_id}", operation_id="get_conversation", openapi_extra=PENDING
)
async def get_conversation(
    conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Conversation:
    raise NotImplementedError("T3.5")


@router.patch(
    "/conversations/{conversation_id}", operation_id="update_conversation", openapi_extra=PENDING
)
async def update_conversation(
    conversation_id: uuid.UUID, body: ConversationPatch, ctx: AnyMember, session: Session
) -> Conversation:
    """Archive or unarchive; set or clear the conversation's AI mode override."""
    raise NotImplementedError("T3.5")


@router.post(
    "/conversations/{conversation_id}/read",
    status_code=204,
    operation_id="mark_conversation_read",
    openapi_extra=PENDING,
)
async def mark_conversation_read(
    conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    raise NotImplementedError("T3.5")


@router.post(
    "/conversations/{conversation_id}/unread",
    status_code=204,
    operation_id="mark_conversation_unread",
    openapi_extra=PENDING,
)
async def mark_conversation_unread(
    conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    raise NotImplementedError("T3.5")


@router.get(
    "/conversations/{conversation_id}/messages", operation_id="list_messages", openapi_extra=PENDING
)
async def list_messages(
    conversation_id: uuid.UUID,
    ctx: AnyMember,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessageList:
    """Newest first; next_cursor loads older messages (upward infinite scroll)."""
    raise NotImplementedError("T3.5")
