"""Comment actions (T6.3; FR-CMT-04, TR-API-05, TR-PL-03, TR-RT-03): public reply, private reply,
hide, unhide and delete from the post detail (UX-SCR-05).

Each locks the comment, checks it is still there and the account can act (reconnect needed: 409
account_needs_reconnect; no comments on the platform: 409 capability_unavailable), changes it on
Instagram first, then here, and queues comment.updated with the new ``Comment``. The caller commits
with ``commit_and_publish``. A platform refusal becomes an API error: a broken connection marks the
account (F-05) and is 409 account_needs_reconnect, a rate limit is 429 rate_limited, anything else
502 platform_error with the §4.7 reason.

- Public reply: the adapter's ``reply_to_comment``; the comment's ``public_reply`` holds it. The
  same text again within 2 minutes returns the comment as it is (a double click, whatever its
  Idempotency-Key), so nothing is posted twice.
- Private reply: Instagram allows one per comment, within 7 days of it. The reply is stored as a
  queued outbound message (source human) in the commenter's conversation, created if needed,
  linked from ``comments.private_reply_message_id`` at once (so a second private reply is 409
  conflict), and sent by ``send_private_reply`` through the account's private-reply bucket
  (services/comments/private_replies). A comment with an automation's private reply waiting in
  the queue is 409 too. The request's Idempotency-Key names the message (its client_id), so the
  same request again returns the comment and queues nothing more.
- Hide and unhide: a comment already in that state is returned as it is, without a call.
- Delete (admins): ``deleted_at`` is set, the post's stats recounted and post.updated published;
  deleting a deleted comment does nothing.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.automations import Comment
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import (
    Contact,
    Direction,
    Message,
    MessageKind,
    MessageSource,
    MessageStatus,
)
from socialhood.platforms.base import PlatformAdapter
from socialhood.platforms.capabilities import Capability, require
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.platforms.registry import adapter_for
from socialhood.realtime import events
from socialhood.repositories import comment_analyses as stats
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import inbox
from socialhood.repositories import ingest as ingest_rows
from socialhood.repositories import messages as messages_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.posts import Comment as CommentOut
from socialhood.services import sending
from socialhood.services.comments import views
from socialhood.services.inbox_views import conversation_touch, human_agent_allowed

PRIVATE_REPLY_LIMIT = timedelta(days=7)  # Instagram's limit for a private reply
DOUBLE_REPLY_WINDOW = timedelta(minutes=2)
CLIENT_ID_NAMESPACE = uuid.UUID("6b1f7a52-8e0c-4c55-a2de-3f9e1b7d4c20")

DELETED = "This comment was deleted."
ONE_PER_COMMENT = "This comment already has a private reply."
AUTOMATION_QUEUED = "An automation is already sending this person a private reply."
TOO_OLD = "Instagram only allows a private reply within 7 days of the comment."
NO_COMMENTER = "The commenter is unknown, so no private reply can be sent."
RECONNECT = "Instagram stopped accepting this connection."
UNCONFIRMED = "Instagram didn't confirm this. Check the post in Instagram before trying again."


@dataclass(frozen=True)
class QueuedPrivateReply:
    """A private reply stored as queued; the caller enqueues its send once committed."""

    comment: CommentOut
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    created: bool  # False: the same request again, nothing new was queued


def private_reply_client_id(comment_id: uuid.UUID, user_id: uuid.UUID, key: str) -> uuid.UUID:
    """The private reply's message client_id: one per comment, member and Idempotency-Key."""
    return uuid.uuid5(CLIENT_ID_NAMESPACE, f"comment-private-reply:{comment_id}:{user_id}:{key}")


# ---------------------------------------------------------------- shared checks


async def _lock(session: AsyncSession, comment_id: uuid.UUID) -> Comment:
    comment = await comments_repo.lock(session, comment_id)
    if comment is None:
        raise ApiError("not_found")
    return comment


def _alive(comment: Comment) -> None:
    if comment.deleted_at is not None:
        raise ApiError("conflict", DELETED)


async def _account(
    session: AsyncSession, deps: PlatformDeps, comment: Comment, needs: Capability
) -> tuple[SocialAccount, PlatformAdapter]:
    acct = await accounts.get(session, comment.social_account_id)
    if acct is None:
        raise ApiError("not_found")
    sending.check_account(acct)
    try:
        adapter = adapter_for(acct, deps)
    except PlatformError as error:
        raise ApiError("capability_unavailable", error.message or None) from error
    require(adapter.capabilities_for(acct), needs)
    return acct, adapter


async def _refused(
    session: AsyncSession, redis: Redis, acct: SocialAccount, error: PlatformError
) -> ApiError:
    """The API error for a platform refusal (TR-PL-03)."""
    if error.code == "account_needs_reconnect":
        from socialhood.services.connections import mark_needs_reconnect

        await mark_needs_reconnect(session, acct, RECONNECT)
        await events.commit_and_publish(session, redis)
        handle = f"@{acct.username}" if acct.username else "This account"
        return ApiError("account_needs_reconnect", f"{handle} needs reconnecting.")
    if error.code == "capability_unavailable":
        return ApiError("capability_unavailable", error.message or None)
    if error.is_rate_limit:
        headers = (
            {"Retry-After": str(math.ceil(error.retry_after_s))} if error.retry_after_s else {}
        )
        return ApiError(
            "rate_limited",
            "Instagram is limiting this account. Try again in a few minutes.",
            headers=headers,
        )
    if error.code == DELIVERY_UNKNOWN:
        return ApiError("platform_error", UNCONFIRMED)
    reason = sending.readable_error(
        error.code, acct.platform, platform_message=error.message, username=acct.username
    )
    return ApiError("platform_error", reason)


async def _out(session: AsyncSession, comment_id: uuid.UUID, *, publish: bool) -> CommentOut:
    if publish:
        [out] = await views.queue_comments(session, [comment_id])
        return out
    [out] = await views.comments_out(session, [comment_id])
    return out


# ---------------------------------------------------------------- public reply


async def reply(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    comment_id: uuid.UUID,
    text: str,
    *,
    now: datetime,
) -> CommentOut:
    comment = await _lock(session, comment_id)
    _alive(comment)
    replied = comment.our_replied_at
    if comment.our_reply_text == text and replied and now - replied < DOUBLE_REPLY_WINDOW:
        return await _out(session, comment.id, publish=False)
    acct, adapter = await _account(session, deps, comment, Capability.COMMENTS)
    try:
        reply_id = await adapter.reply_to_comment(acct, comment.platform_comment_id, text)
    except PlatformError as error:
        raise await _refused(session, redis, acct, error) from error
    comment.our_reply_platform_id = reply_id
    comment.our_reply_text = text
    comment.our_replied_at = now
    await session.flush()
    return await _out(session, comment.id, publish=True)


# ---------------------------------------------------------------- hide, unhide, delete


async def set_hidden(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    comment_id: uuid.UUID,
    *,
    hidden: bool,
) -> CommentOut:
    comment = await _lock(session, comment_id)
    _alive(comment)
    if comment.hidden == hidden:
        return await _out(session, comment.id, publish=False)
    acct, adapter = await _account(session, deps, comment, Capability.COMMENTS)
    try:
        if hidden:
            await adapter.hide_comment(acct, comment.platform_comment_id)
        else:
            await adapter.unhide_comment(acct, comment.platform_comment_id)
    except PlatformError as error:
        raise await _refused(session, redis, acct, error) from error
    comment.hidden = hidden
    await session.flush()
    return await _out(session, comment.id, publish=True)


async def delete(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    comment_id: uuid.UUID,
    *,
    now: datetime,
) -> None:
    comment = await _lock(session, comment_id)
    if comment.deleted_at is not None:
        return
    acct, adapter = await _account(session, deps, comment, Capability.COMMENTS)
    try:
        await adapter.delete_comment(acct, comment.platform_comment_id)
    except PlatformError as error:
        raise await _refused(session, redis, acct, error) from error
    comment.deleted_at = now
    await session.flush()
    await _out(session, comment.id, publish=True)
    for item in await stats.recount(session, [comment.media_item_id]):
        views.queue_post(session, item)


# ---------------------------------------------------------------- private reply


async def private_reply(
    session: AsyncSession,
    deps: PlatformDeps,
    comment_id: uuid.UUID,
    text: str,
    *,
    user_id: uuid.UUID,
    idempotency_key: str,
    now: datetime,
) -> QueuedPrivateReply:
    """Store the private reply as queued (see the module docstring); the caller commits and then
    calls ``private_replies.enqueue_send``."""
    comment = await _lock(session, comment_id)
    _alive(comment)
    client_id = private_reply_client_id(comment.id, user_id, idempotency_key)
    if comment.private_reply_message_id is not None:
        existing = await messages_repo.get(session, comment.private_reply_message_id)
        if existing is not None and existing.client_id == client_id:
            return QueuedPrivateReply(
                await _out(session, comment.id, publish=False),
                existing.id,
                existing.conversation_id,
                created=False,
            )
        raise ApiError("conflict", ONE_PER_COMMENT)
    if await comments_repo.automation_reply_queued(session, comment.id):
        raise ApiError("conflict", AUTOMATION_QUEUED)
    if now - comment.commented_at > PRIVATE_REPLY_LIMIT:
        raise ApiError("conflict", TOO_OLD)
    acct, _ = await _account(session, deps, comment, Capability.PRIVATE_REPLY)
    problem = sending.text_limit_error(acct.platform, text)
    if problem:
        raise ApiError("validation_error", errors=[FieldError("text", problem)])
    contact = await _commenter(session, acct, comment)
    conv, _ = await ingest_rows.get_or_create_conversation(
        session, social_account_id=acct.id, contact_id=contact.id, platform=acct.platform
    )
    msg = Message(
        conversation_id=conv.id,
        social_account_id=acct.id,
        direction=Direction.OUTBOUND,
        source=MessageSource.HUMAN,
        kind=MessageKind.TEXT,
        text=text,
        attachments=[],
        buttons=[],
        quick_replies=[],
        occurred_at=now,
        client_id=client_id,
        status=MessageStatus.QUEUED,
        attempts=0,
        sent_by_user_id=user_id,
        reactions=[],
    )
    session.add(msg)
    await session.flush()
    comment.private_reply_message_id = msg.id
    for key, value in conversation_touch(msg).items():
        setattr(conv, key, value)
    conv.last_outbound_at = now
    conv.awaiting_reply = False
    await sending.human_takeover(session, conv, now=now)  # a person replied (FR-SUG-05, F-09)
    await session.flush()
    events.queue_message(
        session, msg, created=True, sent_by_name=await sending.sender_name(session, user_id)
    )
    await events.queue_conversation(
        session,
        conv,
        now=now,
        contact=contact,
        human_agent=human_agent_allowed(
            acct, ig_human_agent_enabled=deps.settings.ig_human_agent_enabled
        ),
    )
    out = await _out(session, comment.id, publish=True)
    return QueuedPrivateReply(out, msg.id, conv.id, created=True)


async def _commenter(session: AsyncSession, acct: SocialAccount, comment: Comment) -> Contact:
    if comment.contact_id is not None:
        contact = await inbox.get_contact(session, comment.contact_id)
        if contact is not None:
            return contact
    if not comment.author_platform_user_id:
        raise ApiError("conflict", NO_COMMENTER)
    contact, _ = await ingest_rows.get_or_create_contact(
        session,
        social_account_id=acct.id,
        platform_user_id=comment.author_platform_user_id,
        first_seen_at=comment.commented_at,
    )
    comment.contact_id = contact.id
    return contact
