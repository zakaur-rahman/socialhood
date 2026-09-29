"""Comment actions (§2.15; FR-CMT-04, UX-SCR-05): public reply, private reply, hide, unhide and
delete. Each changes the comment on Instagram first, then here, and publishes comment.updated with
the new ``Comment`` (TR-RT-03). Platform refusals use the platform error codes (TR-PL-03); an
account without comments (WhatsApp) is 409 capability_unavailable.

The routes below are the P6 contract; T6.3 implements their bodies and removes each
``openapi_extra`` marker so the tenancy suite covers the route.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Response

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.schemas.posts import Comment, CommentReplyCreate, PrivateReplyCreate

router = APIRouter(prefix="/v1/w/{wid}", tags=["comments"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


@router.post(
    "/comments/{comment_id}/reply",
    operation_id="reply_to_comment",
    openapi_extra=pending("T6.3"),
)
async def reply_to_comment(
    comment_id: uuid.UUID,
    body: CommentReplyCreate,
    idempotency_key: IdempotencyKey,
    ctx: AnyMember,
    session: Session,
) -> Comment:
    """A public reply under the comment, posted on Instagram before the answer (the comment's
    ``public_reply`` holds it). The same Idempotency-Key with the same body returns the first
    answer and posts nothing more (TR-API-05)."""
    raise NotImplementedError("T6.3")


@router.post(
    "/comments/{comment_id}/private-reply",
    status_code=202,
    operation_id="private_reply_to_comment",
    openapi_extra=pending("T6.3"),
)
async def private_reply_to_comment(
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
    raise NotImplementedError("T6.3")


@router.post(
    "/comments/{comment_id}/hide",
    operation_id="hide_comment",
    openapi_extra=pending("T6.3"),
)
async def hide_comment(comment_id: uuid.UUID, ctx: AnyMember, session: Session) -> Comment:
    """Hide the comment on Instagram (others no longer see it; the commenter still does).
    Hiding a hidden comment returns it as it is."""
    raise NotImplementedError("T6.3")


@router.post(
    "/comments/{comment_id}/unhide",
    operation_id="unhide_comment",
    openapi_extra=pending("T6.3"),
)
async def unhide_comment(comment_id: uuid.UUID, ctx: AnyMember, session: Session) -> Comment:
    """Show a hidden comment again."""
    raise NotImplementedError("T6.3")


@router.delete(
    "/comments/{comment_id}",
    status_code=204,
    operation_id="delete_comment",
    openapi_extra=pending("T6.3"),
)
async def delete_comment(comment_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    """Delete the comment on Instagram (admins). The row keeps ``deleted_at`` and leaves every
    list and count; comment.updated (with ``deleted_at`` set) tells open pages to drop it."""
    raise NotImplementedError("T6.3")
