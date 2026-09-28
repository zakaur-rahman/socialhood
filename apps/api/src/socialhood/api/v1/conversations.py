"""Inbox read APIs (T3.5; FR-INB-01, 02, 04, 05; TR-API-04): the conversation list with views,
filters, search and cursor; conversation detail with the reply window; messages (keyset, newest
first); read, unread and archive. The queries are in ``services/conversations.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import AnyMember, Session
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.inbox import (
    Conversation,
    ConversationList,
    ConversationPatch,
    InboxCounts,
    InboxView,
    MessageList,
    PlatformName,
)
from socialhood.services import conversations as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["inbox"])


def _human_agent_enabled(request: Request) -> bool:
    return bool(request.app.state.settings.ig_human_agent_enabled)


@router.get("/conversations", operation_id="list_conversations")
async def list_conversations(
    request: Request,
    ctx: AnyMember,
    session: Session,
    view: Annotated[InboxView, Query()] = "all",
    platform: Annotated[PlatformName | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ConversationList:
    return await service.list_conversations(
        session,
        service.ListFilters(view=view, platform=platform, account_id=account_id, q=q),
        cursor=cursor,
        limit=limit,
        ig_human_agent_enabled=_human_agent_enabled(request),
        now=datetime.now(UTC),
    )


@router.get("/conversations/counts", operation_id="get_inbox_counts")
async def get_inbox_counts(ctx: AnyMember, session: Session) -> InboxCounts:
    return await service.inbox_counts(session)


@router.get("/conversations/{conversation_id}", operation_id="get_conversation")
async def get_conversation(
    request: Request, conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Conversation:
    conv = await service.get_or_404(session, conversation_id)
    return await service.conversation_detail(
        session, conv, ig_human_agent_enabled=_human_agent_enabled(request), now=datetime.now(UTC)
    )


@router.patch("/conversations/{conversation_id}", operation_id="update_conversation")
async def update_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    body: ConversationPatch,
    ctx: AnyMember,
    session: Session,
) -> Conversation:
    """Archive or unarchive; set or clear the conversation's AI mode override."""
    conv = await service.get_or_404(session, conversation_id)
    enabled, now = _human_agent_enabled(request), datetime.now(UTC)
    if await service.update_conversation(
        session, conv, body, ig_human_agent_enabled=enabled, now=now
    ):
        await commit_and_publish(session, request.app.state.redis)
    return await service.conversation_detail(session, conv, ig_human_agent_enabled=enabled, now=now)


@router.post(
    "/conversations/{conversation_id}/read",
    status_code=204,
    operation_id="mark_conversation_read",
)
async def mark_conversation_read(
    request: Request, conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    conv = await service.get_or_404(session, conversation_id)
    if await service.mark_read(
        session, conv, ig_human_agent_enabled=_human_agent_enabled(request), now=datetime.now(UTC)
    ):
        await commit_and_publish(session, request.app.state.redis)
    return Response(status_code=204)


@router.post(
    "/conversations/{conversation_id}/unread",
    status_code=204,
    operation_id="mark_conversation_unread",
)
async def mark_conversation_unread(
    request: Request, conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    conv = await service.get_or_404(session, conversation_id)
    if await service.mark_unread(
        session, conv, ig_human_agent_enabled=_human_agent_enabled(request), now=datetime.now(UTC)
    ):
        await commit_and_publish(session, request.app.state.redis)
    return Response(status_code=204)


@router.get("/conversations/{conversation_id}/messages", operation_id="list_messages")
async def list_messages(
    conversation_id: uuid.UUID,
    ctx: AnyMember,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessageList:
    """Newest first; next_cursor loads older messages (upward infinite scroll)."""
    conv = await service.get_or_404(session, conversation_id)
    return await service.list_messages(session, conv, cursor=cursor, limit=limit)
