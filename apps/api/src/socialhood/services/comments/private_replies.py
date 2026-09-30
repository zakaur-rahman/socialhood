"""Sending a member's private reply to a comment (T6.3; FR-CMT-04, TR-JOB-07, TR-PL-09, TR-JOB-04,
TR-JOB-05).

The P4 private-reply path, for one reply a member wrote: the message is already stored (queued, in
the commenter's conversation, linked from ``comments.private_reply_message_id``, see
services/comments/actions). ``send_private_reply`` (interactive lane, queueing lock
``send:{message_id}`` so the message sweeper sees its job, run lock ``conv:{conversation_id}`` like
any send in the conversation) then:

1. claims the message (queued to sending) before anything else, so no other send picks it up;
   an account that is read-only after a downgrade (FR-BIL-07) holds it instead: it stays queued
   and the job looks again every HOLD_RETRY_S, as the automations' private-reply queue holds
   theirs, until the account may send or the comment is past 7 days (step 2 then fails it);
2. checks the account, the PRIVATE_REPLY capability and Instagram's 7-day limit again;
3. takes a token from the account's IG_PRIVATE_REPLY bucket, shared with the automation queue
   (never more than 750 private replies an hour); without one soon it defers itself until a token
   is due, which is not a retry;
4. calls the adapter's ``private_reply`` addressed by the comment, and records the outcome like the
   send pipeline: sent with the platform id (an echo stored first keeps it, C-011), retried while
   the platform error is temporary and tries remain (the row stays sending), otherwise failed with
   a readable reason. A failure after the request went out is ``delivery_unknown`` and is never
   retried (TR-JOB-05). A definite refusal unlinks the message from the comment, so a member can
   try again; the failed message stays in the conversation.

message.updated, comment.updated and conversation.updated follow each change.

A queued reply whose job was lost (a worker that died before the claim) goes back to
``send_private_reply`` from the message sweeper (``requeue``, jobs/tasks/send.py), never to
``send_message``, which would send it as a plain DM. One left ``sending`` is the sweeper's
delivery_unknown like any send (TR-JOB-05): Instagram may have it, and allows one per comment.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.entitlements import read_only_error
from socialhood.models.automations import Comment
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Message, MessageStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import OutboundMessage
from socialhood.platforms.buckets import Bucket, TokenBuckets
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.platforms.registry import adapter_for
from socialhood.realtime import events
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import inbox
from socialhood.repositories import messages as messages_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services import sending
from socialhood.services.comments import views
from socialhood.services.comments.actions import PRIVATE_REPLY_LIMIT, TOO_OLD

log = get_logger(__name__)

MAX_INLINE_WAIT_S = 2.0  # waiting this long for a token happens in the job
HOLD_RETRY_S = 600.0  # a reply held for a read-only account looks again (as the automations' queue)
PRIVATE_REPLY_EXPIRED = "reply_window_closed"
NOT_QUEUED = "Couldn't queue the private reply. Try again."

Outcome = Literal["sent", "failed", "skipped", "deferred", "held"]
Sleep = Callable[[float], Awaitable[Any]]


def send_key(message_id: uuid.UUID) -> str:
    """The message sweeper's name for a message's send job (jobs/tasks/send.py)."""
    return f"send:{message_id}"


async def cancel_queued(
    session: AsyncSession, redis: Redis, comment_id: uuid.UUID, message_id: uuid.UUID
) -> None:
    """Its send could not be queued (the API): the message fails and the comment is free for
    another private reply, rather than wait for the message sweeper's normal-DM retry."""
    if not await messages_repo.mark_failed(
        session,
        message_id,
        code="platform_unavailable",
        message=NOT_QUEUED,
        only_from=(MessageStatus.QUEUED,),
    ):
        await session.rollback()
        return
    locked = await comments_repo.lock(session, comment_id)
    if locked is not None and locked.private_reply_message_id == message_id:
        locked.private_reply_message_id = None
        await session.flush()
    await _publish(session, redis, message_id, comment_id)


async def enqueue_send(
    workspace_id: uuid.UUID,
    comment_id: uuid.UUID,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    delay_s: float = 0,
    resume: bool = False,
) -> bool:
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.comments import send_private_reply

    return await enqueue(
        send_private_reply,
        key=send_key(message_id),
        lock=f"conv:{conversation_id}",
        delay_s=delay_s,
        workspace_id=str(workspace_id),
        comment_id=str(comment_id),
        message_id=str(message_id),
        conversation_id=str(conversation_id),
        resume=resume,
    )


async def requeue(
    workspace_id: uuid.UUID,
    comment_id: uuid.UUID,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    """The message sweeper's path for a queued private reply that lost its job: its own job again
    (a waiting one makes this a no-op). A failed enqueue is logged; the next sweep tries again."""
    try:
        return await enqueue_send(workspace_id, comment_id, message_id, conversation_id)
    except Exception:
        log.warning("private_reply_enqueue_failed", message_id=str(message_id))
        return False


async def send(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    comment_id: uuid.UUID,
    message_id: uuid.UUID,
    attempt: int = 0,
    resume: bool = False,
    will_retry: Callable[[PlatformError], bool],
    sleep: Sleep = asyncio.sleep,
    now: datetime | None = None,
) -> Outcome:
    """The send_private_reply job, in the message's workspace scope (steps 1 to 4)."""
    async with sessionmaker() as session:
        msg = await messages_repo.get(session, message_id)
        comment = await comments_repo.get(session, comment_id)
        if msg is None or comment is None or comment.private_reply_message_id != msg.id:
            return "skipped"
        now = now or datetime.now(UTC)
        if msg.status == MessageStatus.QUEUED:
            if await _held(session, msg, comment, now):
                conversation_id = msg.conversation_id
                await session.rollback()
                await enqueue_send(
                    workspace_id, comment_id, message_id, conversation_id, delay_s=HOLD_RETRY_S
                )
                log.info("private_reply_held", message_id=str(message_id), error_code="read_only")
                return "held"
            if not await messages_repo.claim(
                session, msg.id, from_status=MessageStatus.QUEUED, attempts=msg.attempts + 1
            ):
                await session.rollback()
                return "skipped"
            await session.commit()
        elif not (msg.status == MessageStatus.SENDING and (attempt > 0 or resume)):
            return "skipped"
        acct = await accounts.get(session, msg.social_account_id)
        if acct is None:
            return "skipped"
        refusal = _check(acct, comment, deps, now)
        if refusal is not None:
            return await _fail(session, redis, acct, comment, msg, *refusal)

        wait = await _take_token(TokenBuckets(redis), acct.id, sleep)
        if wait:
            await enqueue_send(
                workspace_id, comment.id, msg.id, msg.conversation_id, delay_s=wait, resume=True
            )
            await session.rollback()
            return "deferred"

        try:
            result = await adapter_for(acct, deps).private_reply(
                acct, comment.platform_comment_id, OutboundMessage(text=msg.text)
            )
        except PlatformError as error:
            if error.retryable and will_retry(error):
                log.info("private_reply_retry", message_id=str(msg.id), error_code=error.code)
                raise
            return await _fail(session, redis, acct, comment, msg, error.code, error.message)
        except Exception:
            log.exception("private_reply_unexpected_error", message_id=str(msg.id))
            return await _fail(session, redis, acct, comment, msg, DELIVERY_UNKNOWN, "")
        await _mark_sent(session, msg.id, result.platform_message_id, now=datetime.now(UTC))
        await _publish(session, redis, msg.id, comment.id)
    log.info("private_reply_sent", message_id=str(message_id))
    return "sent"


async def _held(session: AsyncSession, msg: Message, comment: Comment, now: datetime) -> bool:
    """The queued reply waits: its account is read-only after a downgrade (FR-BIL-07) and the
    comment can still get it. Past Instagram's 7 days it goes on, and ``_check`` fails it."""
    if _expired(comment, now):
        return False
    acct = await accounts.get(session, msg.social_account_id)
    return acct is not None and await read_only_error(session, acct) is not None


def _expired(comment: Comment, now: datetime) -> bool:
    return now - comment.commented_at > PRIVATE_REPLY_LIMIT or comment.deleted_at is not None


def _check(
    acct: SocialAccount, comment: Comment, deps: PlatformDeps, now: datetime
) -> tuple[str, str] | None:
    """Why the reply cannot go now, as (code, platform message), or None."""
    if acct.status in sending.BLOCKED_STATUSES:
        return "account_needs_reconnect", ""
    try:
        caps = adapter_for(acct, deps).capabilities_for(acct)
    except PlatformError as error:
        return "capability_unavailable", error.message
    if Capability.PRIVATE_REPLY not in caps:
        return "capability_unavailable", ""
    if _expired(comment, now):
        return PRIVATE_REPLY_EXPIRED, ""
    return None


async def _take_token(buckets: TokenBuckets, account_id: uuid.UUID, sleep: Sleep) -> float:
    """0 once a token is taken, else the seconds until one is due. A Valkey outage never blocks
    this one reply (Instagram still enforces its own limit)."""
    waited = 0.0
    while True:
        try:
            wait = await buckets.take(Bucket.IG_PRIVATE_REPLY, str(account_id))
        except Exception:
            log.warning("token_bucket_unavailable", bucket=str(Bucket.IG_PRIVATE_REPLY))
            return 0.0
        if wait <= 0:
            return 0.0
        if waited + wait > MAX_INLINE_WAIT_S:
            return wait
        await sleep(wait)
        waited += wait


def _reason(code: str, acct: SocialAccount, platform_message: str) -> str:
    if code == PRIVATE_REPLY_EXPIRED:
        return TOO_OLD
    return sending.readable_error(
        code, acct.platform, platform_message=platform_message, username=acct.username
    )


async def _fail(
    session: AsyncSession,
    redis: Redis,
    acct: SocialAccount,
    comment: Comment,
    msg: Message,
    code: str,
    platform_message: str,
) -> Outcome:
    from socialhood.services.connections import mark_needs_reconnect

    log.info("private_reply_failed", message_id=str(msg.id), error_code=code)
    failed = await messages_repo.mark_failed(
        session,
        msg.id,
        code=code,
        message=_reason(code, acct, platform_message),
        only_from=(MessageStatus.SENDING,),
    )
    if not failed:
        await session.rollback()
        return "skipped"
    if code != DELIVERY_UNKNOWN:  # Instagram did not take it: the comment may get another try
        locked = await comments_repo.lock(session, comment.id)
        if locked is not None and locked.private_reply_message_id == msg.id:
            locked.private_reply_message_id = None
            await session.flush()
    if code == "account_needs_reconnect" and acct.status not in sending.BLOCKED_STATUSES:
        await mark_needs_reconnect(session, acct, "Instagram stopped accepting this connection.")
    await _publish(session, redis, msg.id, comment.id)
    return "failed"


async def _mark_sent(
    session: AsyncSession, message_id: uuid.UUID, platform_message_id: str | None, *, now: datetime
) -> None:
    """Record the platform's id; an echo stored first as its own row holds it (C-011)."""
    try:
        async with session.begin_nested():
            await messages_repo.mark_sent(
                session, message_id, platform_message_id=platform_message_id, at=now
            )
    except IntegrityError:
        log.warning("private_reply_echo_stored_first", message_id=str(message_id))
        await messages_repo.mark_sent(session, message_id, platform_message_id=None, at=now)


async def _publish(
    session: AsyncSession, redis: Redis, message_id: uuid.UUID, comment_id: uuid.UUID
) -> None:
    msg = await messages_repo.get(session, message_id)
    await session.flush()
    if msg is not None:
        await session.refresh(msg)
        events.queue_message(
            session,
            msg,
            created=False,
            sent_by_name=await sending.sender_name(session, msg.sent_by_user_id),
        )
        conv = await inbox.get_conversation(session, msg.conversation_id)
        if conv is not None:
            sent_at = msg.sent_at if msg.status == MessageStatus.SENT else None
            if sent_at and (conv.last_outbound_at is None or sent_at > conv.last_outbound_at):
                conv.last_outbound_at = sent_at
                await session.flush()
            await events.queue_conversation(session, conv, now=datetime.now(UTC))
    await views.queue_comments(session, [comment_id])
    await events.commit_and_publish(session, redis)
