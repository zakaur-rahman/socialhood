"""Saved replies routes (GR-21). Any member reads them and fills one for a conversation (agents
use them in the composer); owners and admins create, change and delete. The rules are in
services/saved_replies.py."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.schemas.saved_replies import (
    SavedReply,
    SavedReplyCreate,
    SavedReplyFill,
    SavedReplyFilled,
    SavedReplyList,
    SavedReplyUpdate,
)
from socialhood.services import saved_replies as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["saved-replies"])


@router.get("/saved-replies", operation_id="list_saved_replies")
async def list_saved_replies(ctx: AnyMember, session: Session) -> SavedReplyList:
    """Every saved reply by shortcut, with the workspace's limit."""
    return await service.list_replies(session)


@router.post("/saved-replies", status_code=201, operation_id="create_saved_reply")
async def create_saved_reply(body: SavedReplyCreate, ctx: Admin, session: Session) -> SavedReply:
    """409 when another reply has the shortcut; 422 names the field that doesn't fit."""
    out = await service.create(session, body, user_id=ctx.user.id)
    await session.commit()
    return out


@router.patch("/saved-replies/{reply_id}", operation_id="update_saved_reply")
async def update_saved_reply(
    reply_id: uuid.UUID, body: SavedReplyUpdate, ctx: Admin, session: Session
) -> SavedReply:
    out = await service.update(session, reply_id, body)
    await session.commit()
    return out


@router.delete("/saved-replies/{reply_id}", status_code=204, operation_id="delete_saved_reply")
async def delete_saved_reply(reply_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    """A flow step that sends this reply then fails with a plain reason in Activity."""
    await service.delete(session, reply_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/saved-replies/{reply_id}/fill", operation_id="fill_saved_reply")
async def fill_saved_reply(
    reply_id: uuid.UUID, body: SavedReplyFill, ctx: AnyMember, session: Session
) -> SavedReplyFilled:
    """The reply with the conversation's contact filled in. Unknown fields are empty and no
    ``{braces}`` are left; 404 for a reply or conversation of another workspace."""
    return SavedReplyFilled(
        text=await service.fill_for_conversation(session, reply_id, body.conversation_id)
    )
