"""Sending (T3.6; FR-INB-06, 07, 10; TR-API-05, TR-JOB-04, TR-JOB-05, TR-PL-10): POST a reply
(idempotent; role, account and window checks; 202 with the queued message) and retry a failed one.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request

from socialhood.auth.deps import AnyMember, Session
from socialhood.errors import ApiError
from socialhood.platforms.base import OutboundTemplate
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.repositories import messages as messages_repo
from socialhood.schemas.inbox import Message, SendMessage
from socialhood.services import idempotency, sending
from socialhood.services.inbox_views import message_out

router = APIRouter(prefix="/v1/w/{wid}", tags=["inbox"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=202,
    operation_id="send_message",
)
async def send_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: SendMessage,
    idempotency_key: IdempotencyKey,
    ctx: AnyMember,
    session: Session,
) -> Message:
    """Queue a reply; it is sent by the worker and progress arrives as message.updated events.

    Any member may reply. The same Idempotency-Key with the same body returns the first response
    and sends nothing more; with a different body it is 409 idempotency_conflict.
    """
    conv = await inbox.get_conversation(session, conversation_id)
    if conv is None:
        raise ApiError("not_found")
    redis = request.app.state.redis
    claim = idempotency.IdempotencyKey(
        redis,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        key=idempotency_key,
        fingerprint=idempotency.fingerprint("POST", request.url.path, body.model_dump(mode="json")),
    )
    stored = await claim.begin()
    if stored is not None:
        return Message.model_validate(stored.body)
    try:
        msg = await sending.queue_outbound(
            session,
            conv,
            source="human",
            client_id=body.client_id,
            text=body.text,
            attachment_asset_ids=body.attachment_asset_ids,
            template=(
                OutboundTemplate(
                    name=body.template.name,
                    language=body.template.language,
                    params=tuple(body.template.params),
                )
                if body.template is not None
                else None
            ),
            sent_by_user_id=ctx.user.id,
            sticker=body.sticker,
            sticker_asset_id=body.sticker_asset_id,
            suggestion_id=body.suggestion_id,
            deps=_deps(request),
        )
        await events.commit_and_publish(session, redis)
    except BaseException:
        await claim.release()
        raise
    out = message_out(msg, sent_by_name=await sending.sender_name(session, msg.sent_by_user_id))
    await claim.complete(202, out.model_dump(mode="json"))
    return out


@router.post(
    "/messages/{message_id}/retry",
    status_code=202,
    operation_id="retry_message",
)
async def retry_message(
    request: Request, message_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Message:
    """Send a failed message again (the same row). A message already queued or sending is
    returned as it is, so a second click never sends it twice."""
    msg = await messages_repo.get(session, message_id)
    if msg is None:
        raise ApiError("not_found")
    msg, requeued = await sending.retry(session, msg, deps=_deps(request))
    await events.commit_and_publish(session, request.app.state.redis)
    if requeued:
        # After the commit, so the job sees the message queued.
        await sending.enqueue_send(msg.id, msg.conversation_id, msg.workspace_id)
    return message_out(msg, sent_by_name=await sending.sender_name(session, msg.sent_by_user_id))
