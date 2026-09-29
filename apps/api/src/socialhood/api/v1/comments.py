"""Comment actions (§2.15; FR-CMT-04, UX-SCR-05, T6.3): public reply, private reply, hide, unhide
and delete. Each changes the comment on Instagram first, then here, and publishes comment.updated
with the new ``Comment`` (TR-RT-03). Platform refusals: account_needs_reconnect (409),
rate_limited (429) or platform_error (502) with the reason (TR-PL-03); an account without comments
(WhatsApp) is 409 capability_unavailable; another workspace's comment is 404 not_found. The rules
are in services/comments/actions.py.

Replies take an Idempotency-Key (TR-API-05, as sends and scheduled messages do): the same key with
the same body returns the first answer and does nothing more; with a different body it is 409
idempotency_conflict.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.errors import ApiError
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.posts import Comment, CommentReplyCreate, PrivateReplyCreate
from socialhood.services import idempotency
from socialhood.services.comments import actions, private_replies

router = APIRouter(prefix="/v1/w/{wid}", tags=["comments"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


def _claim(
    request: Request, ctx: AnyMember, key: str, body: CommentReplyCreate | PrivateReplyCreate
) -> idempotency.IdempotencyKey:
    return idempotency.IdempotencyKey(
        request.app.state.redis,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        key=key,
        fingerprint=idempotency.fingerprint("POST", request.url.path, body.model_dump(mode="json")),
    )


@router.post("/comments/{comment_id}/reply", operation_id="reply_to_comment")
async def reply_to_comment(
    request: Request,
    comment_id: uuid.UUID,
    body: CommentReplyCreate,
    idempotency_key: IdempotencyKey,
    ctx: AnyMember,
    session: Session,
) -> Comment:
    """A public reply under the comment, posted on Instagram before the answer (the comment's
    ``public_reply`` holds it). The same Idempotency-Key with the same body returns the first
    answer and posts nothing more (TR-API-05)."""
    redis = request.app.state.redis
    claim = _claim(request, ctx, idempotency_key, body)
    stored = await claim.begin()
    if stored is not None:
        return Comment.model_validate(stored.body)
    try:
        out = await actions.reply(
            session, redis, _deps(request), comment_id, body.text, now=datetime.now(UTC)
        )
        await commit_and_publish(session, redis)
    except BaseException:
        await claim.release()
        raise
    await claim.complete(200, out.model_dump(mode="json"))
    return out


@router.post(
    "/comments/{comment_id}/private-reply",
    status_code=202,
    operation_id="private_reply_to_comment",
)
async def private_reply_to_comment(
    request: Request,
    comment_id: uuid.UUID,
    body: PrivateReplyCreate,
    idempotency_key: IdempotencyKey,
    ctx: AnyMember,
    session: Session,
) -> Comment:
    """A DM to the commenter, addressed by the comment: queued as an outbound message in their
    conversation (created if needed), which message.* events follow. The answer is the comment
    with ``private_reply`` set. Instagram allows one per comment within 7 days: a second is 409
    conflict. Idempotency-Key as for ``reply_to_comment``."""
    redis = request.app.state.redis
    claim = _claim(request, ctx, idempotency_key, body)
    stored = await claim.begin()
    if stored is not None:
        return Comment.model_validate(stored.body)
    try:
        queued = await actions.private_reply(
            session,
            _deps(request),
            comment_id,
            body.text,
            user_id=ctx.user.id,
            idempotency_key=idempotency_key,
            now=datetime.now(UTC),
        )
        await commit_and_publish(session, redis)
    except BaseException:
        await claim.release()
        raise
    if queued.created:  # after the commit, so the job finds the message queued
        try:
            await private_replies.enqueue_send(
                ctx.workspace_id, comment_id, queued.message_id, queued.conversation_id
            )
        except Exception as error:
            await private_replies.cancel_queued(session, redis, comment_id, queued.message_id)
            await claim.release()
            raise ApiError("service_unavailable", private_replies.NOT_QUEUED) from error
    await claim.complete(202, queued.comment.model_dump(mode="json"))
    return queued.comment


@router.post("/comments/{comment_id}/hide", operation_id="hide_comment")
async def hide_comment(
    request: Request, comment_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Comment:
    """Hide the comment on Instagram (others no longer see it; the commenter still does).
    Hiding a hidden comment returns it as it is."""
    redis = request.app.state.redis
    out = await actions.set_hidden(session, redis, _deps(request), comment_id, hidden=True)
    await commit_and_publish(session, redis)
    return out


@router.post("/comments/{comment_id}/unhide", operation_id="unhide_comment")
async def unhide_comment(
    request: Request, comment_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Comment:
    """Show a hidden comment again."""
    redis = request.app.state.redis
    out = await actions.set_hidden(session, redis, _deps(request), comment_id, hidden=False)
    await commit_and_publish(session, redis)
    return out


@router.delete("/comments/{comment_id}", status_code=204, operation_id="delete_comment")
async def delete_comment(
    request: Request, comment_id: uuid.UUID, ctx: Admin, session: Session
) -> Response:
    """Delete the comment on Instagram (admins). The row keeps ``deleted_at`` and leaves every
    list and count; comment.updated (with ``deleted_at`` set) tells open pages to drop it."""
    redis = request.app.state.redis
    await actions.delete(session, redis, _deps(request), comment_id, now=datetime.now(UTC))
    await commit_and_publish(session, redis)
    return Response(status_code=204)
