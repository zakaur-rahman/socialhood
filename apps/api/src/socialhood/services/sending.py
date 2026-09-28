"""The outbound pipeline (T3.6; FR-INB-06, 07, 08, 10; TR-JOB-04, TR-JOB-05, TR-PL-09, TR-PL-10;
FR-SUG-05).

Contract (shared by the send endpoint, scheduled messages and, later, AI and automations):
``queue_outbound`` checks the account, capabilities, reply window and length limits, inserts the
message as ``queued``, updates the conversation, queues real-time events and enqueues
``send_message``. It runs in the caller's transaction and workspace scope and does not commit;
the caller commits with ``realtime.events.commit_and_publish``. Rule failures raise ``ApiError``
with the §4.7 codes (reply_window_closed, account_needs_reconnect, capability_unavailable,
validation_error, unsupported_media). Calling it again with the same client_id in the
conversation returns the existing message and sends nothing more.

``deliver`` is the send_message job: queued → sending → sent, or failed with a TR-PL-03 code and
a readable reason. Retryable errors keep the row ``sending`` and let the queue retry; the row
fails only when no retry is left (TR-JOB-04). A failure after the request went out is
``delivery_unknown`` and is never retried automatically (TR-JOB-05).

Attachments: a message may carry text and attachments, but a platform message holds one of them,
so each attachment is its own platform message, in order, and the text goes last (F-07). Each
sent part is recorded on the row at once, so a retry never sends a part twice.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, cast

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.errors import ApiError, FieldError
from socialhood.jobs.enqueue import enqueue
from socialhood.models.ai import AiSettings
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.identity import User
from socialhood.models.inbox import (
    Contact,
    Conversation,
    Direction,
    Message,
    MessageKind,
    MessageStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import (
    OutboundAttachment,
    OutboundMessage,
    OutboundTemplate,
    PlatformAdapter,
)
from socialhood.platforms.buckets import Bucket, TokenBuckets
from socialhood.platforms.capabilities import Capability, require
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.platforms.registry import adapter_for
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.repositories import messages as messages_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services import media_assets
from socialhood.services.connections import mark_needs_reconnect
from socialhood.services.inbox_views import conversation_touch
from socialhood.services.reply_window import (
    SendKind,
    may_send,
    needs_human_agent_tag,
    reply_window,
)

log = get_logger(__name__)

OutboundSource = Literal["human", "ai_auto", "automation"]

PLATFORM_NAMES = {"instagram": "Instagram", "whatsapp": "WhatsApp"}
DEFAULT_TAKEOVER_MINUTES = 120
# ai_paused_until = 'infinity' means "until resumed" (§5.4); asyncpg writes datetime.max as that.
UNTIL_RESUMED = datetime.max.replace(tzinfo=UTC)
BLOCKED_STATUSES = frozenset({AccountStatus.NEEDS_RECONNECT, AccountStatus.DISCONNECTED})

# Waiting this long for a token happens in the job; longer waits re-schedule it (TR-PL-09).
MAX_INLINE_WAIT_S = 2.0
# The job can start before the request that queued the message has committed: look again soon.
NOT_FOUND_RETRIES = 10
NOT_FOUND_DELAY_S = 0.3


@dataclass(frozen=True)
class TextLimit:
    max: int
    unit: Literal["bytes", "characters"]


# TR-PL-10: Instagram counts UTF-8 bytes, WhatsApp characters.
TEXT_LIMITS: dict[str, TextLimit] = {
    "instagram": TextLimit(1000, "bytes"),
    "whatsapp": TextLimit(4096, "characters"),
}
# FR-INB-08: images on both platforms; video and documents on WhatsApp.
ATTACHMENT_TYPES: dict[str, frozenset[str]] = {
    "instagram": frozenset({"image"}),
    "whatsapp": frozenset({"image", "video", "file"}),
}


def platform_name(platform: str) -> str:
    return PLATFORM_NAMES.get(platform, platform.capitalize())


def text_size(platform: str, text: str) -> int:
    limit = TEXT_LIMITS.get(platform)
    return len(text.encode()) if limit is not None and limit.unit == "bytes" else len(text)


def text_limit_error(platform: str, text: str) -> str | None:
    """The validation message when ``text`` is over the platform's limit (TR-PL-10), else None."""
    limit = TEXT_LIMITS.get(platform)
    if limit is None:
        return None
    size = text_size(platform, text)
    if size <= limit.max:
        return None
    return (
        f"{platform_name(platform)} messages can be up to {limit.max:,} {limit.unit}; "
        f"this one is {size:,}."
    )


def window_closed_detail(platform: str) -> str:
    if platform == "whatsapp":
        return (
            "WhatsApp allows free-form replies for 24 hours after the customer's last message. "
            "Send an approved template instead."
        )
    return (
        f"{platform_name(platform)} allows replies for 24 hours after the customer's last message."
    )


def readable_error(
    code: str, platform: str, *, platform_message: str = "", username: str | None = None
) -> str:
    """The reason a Failed bubble shows (§4.7 copy)."""
    name = platform_name(platform)
    handle = f"@{username}" if username else "This account"
    messages = {
        "reply_window_closed": window_closed_detail(platform),
        "account_needs_reconnect": f"{handle} needs reconnecting before you can send from it.",
        "capability_unavailable": f"{name} doesn't support this.",
        "recipient_unavailable": "This person can't receive messages right now.",
        "platform_rate_limited": (
            f"{name} is limiting messages from this account. Try again in a few minutes."
        ),
        "platform_unavailable": f"{name} didn't respond.",
        "platform_rejected": f"{name} rejected this: {platform_message or 'no reason given'}",
        DELIVERY_UNKNOWN: (
            f"We couldn't confirm this was delivered. Check the chat in {name} before retrying."
        ),
    }
    return messages.get(code, platform_message or "The message couldn't be sent.")


# ---------------------------------------------------------------- queue (API, scheduled, AI)


def capabilities(acct: SocialAccount, deps: PlatformDeps) -> frozenset[Capability]:
    try:
        return adapter_for(acct, deps).capabilities_for(acct)
    except PlatformError as error:
        raise ApiError("capability_unavailable", error.message or None) from error


def check_account(acct: SocialAccount) -> None:
    if acct.status in BLOCKED_STATUSES:
        handle = f"@{acct.username}" if acct.username else "This account"
        raise ApiError(
            "account_needs_reconnect", f"{handle} needs reconnecting before you can send from it."
        )


def send_kind(source: str, *, template: bool) -> SendKind:
    if template:
        return "template"
    return cast(SendKind, source if source in ("human", "ai_auto", "automation") else "human")


async def queue_outbound(
    session: AsyncSession,
    conv: Conversation,
    *,
    source: OutboundSource,
    client_id: uuid.UUID,
    text: str | None = None,
    attachment_asset_ids: Sequence[uuid.UUID] = (),
    template: OutboundTemplate | None = None,
    sent_by_user_id: uuid.UUID | None = None,
    scheduled_message_id: uuid.UUID | None = None,
    suggestion_id: uuid.UUID | None = None,
    deps: PlatformDeps | None = None,
    now: datetime | None = None,
) -> Message:
    """Insert a queued outbound message and enqueue its send (see the module docstring).

    ``deps`` defaults to the worker's (jobs use that); the API passes its own.
    """
    now = now or datetime.now(UTC)
    text = text if text is not None and text.strip() else None
    asset_ids = list(attachment_asset_ids)

    existing = await messages_repo.find_by_client_id(session, conv.id, client_id)
    if existing is not None:
        return _same_request(existing, text=text, asset_ids=asset_ids, template=template)

    acct = await accounts.get(session, conv.social_account_id)
    if acct is None:
        raise ApiError("not_found")
    check_account(acct)
    caps = capabilities(acct, deps or _worker_deps())
    require(caps, Capability.DM_SEND)
    _check_content(conv.platform, text=text, asset_ids=asset_ids, template=template)
    if template is not None:
        require(caps, Capability.TEMPLATES)
    assets = await media_assets.load(session, asset_ids)
    if assets:
        require(caps, Capability.DM_ATTACHMENTS)
        _check_attachment_types(conv.platform, assets)

    human_agent = Capability.HUMAN_AGENT in caps
    window = reply_window(conv.platform, conv.last_inbound_at, human_agent=human_agent, now=now)
    kind = send_kind(source, template=template is not None)
    if not may_send(window, kind):
        raise ApiError("reply_window_closed", window_closed_detail(conv.platform))

    attachments = [media_assets.attachment(a) for a in assets]
    msg = Message(
        conversation_id=conv.id,
        social_account_id=acct.id,
        direction=Direction.OUTBOUND,
        source=source,
        kind=_message_kind(text, attachments, template),
        text=text,
        attachments=attachments,
        template=(
            {"name": template.name, "language": template.language, "params": list(template.params)}
            if template is not None
            else None
        ),
        occurred_at=now,
        client_id=client_id,
        status=MessageStatus.QUEUED,
        attempts=0,
        human_agent_tag=needs_human_agent_tag(window, kind),
        sent_by_user_id=sent_by_user_id,
        scheduled_message_id=scheduled_message_id,
        suggestion_id=suggestion_id,
        reactions=[],
    )
    try:
        async with session.begin_nested():
            session.add(msg)
            await session.flush()
    except IntegrityError:
        # The same client_id was inserted concurrently (a double submit): use that one.
        existing = await messages_repo.find_by_client_id(session, conv.id, client_id)
        if existing is None:
            raise
        return _same_request(existing, text=text, asset_ids=asset_ids, template=template)

    await _touch_conversation(session, conv, msg, now=now, takeover=source == "human")
    events.queue_message(
        session, msg, created=True, sent_by_name=await sender_name(session, sent_by_user_id)
    )
    await events.queue_conversation(session, conv, now=now, human_agent=human_agent)
    await enqueue_send(msg.id, conv.id, msg.workspace_id)
    return msg


def _same_request(
    existing: Message,
    *,
    text: str | None,
    asset_ids: Sequence[uuid.UUID],
    template: OutboundTemplate | None,
) -> Message:
    sent_assets = [a.get("asset_id") for a in existing.attachments or []]
    same = (
        existing.direction == Direction.OUTBOUND
        and existing.text == text
        and sent_assets == [str(i) for i in asset_ids]
        and (existing.template or {}).get("name") == (template.name if template else None)
    )
    if not same:
        raise ApiError(
            "idempotency_conflict", "This client_id was already used for a different message."
        )
    return existing


def _check_content(
    platform: str,
    *,
    text: str | None,
    asset_ids: Sequence[uuid.UUID],
    template: OutboundTemplate | None,
) -> None:
    if template is not None:
        if text or asset_ids:
            raise _invalid("template", "Send a template on its own, without text or attachments.")
        return
    if not text and not asset_ids:
        raise _invalid("text", "Write a message or add an attachment.")
    if text:
        problem = text_limit_error(platform, text)
        if problem:
            raise _invalid("text", problem)


def _check_attachment_types(platform: str, assets: Sequence[Any]) -> None:
    allowed = ATTACHMENT_TYPES.get(platform, frozenset())
    for asset in assets:
        kind = media_assets.attachment_type(asset)
        if kind not in allowed:
            noun = {"image": "images", "video": "videos", "file": "files"}[kind]
            raise ApiError(
                "unsupported_media", f"{platform_name(platform)} messages can't include {noun}."
            )


def _invalid(field: str, message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError(field, message)])


def _message_kind(
    text: str | None, attachments: Sequence[dict[str, Any]], template: OutboundTemplate | None
) -> str:
    if template is not None:
        return MessageKind.TEMPLATE
    if attachments and not text:
        return str(attachments[0]["type"])
    return MessageKind.TEXT


async def _touch_conversation(
    session: AsyncSession, conv: Conversation, msg: Message, *, now: datetime, takeover: bool
) -> None:
    """Last message fields; a reply clears awaiting_reply; a person's reply also takes over."""
    for key, value in conversation_touch(msg).items():
        setattr(conv, key, value)
    conv.last_outbound_at = now
    conv.awaiting_reply = False
    if takeover:
        await human_takeover(session, conv, now=now)
    await session.flush()


async def human_takeover(session: AsyncSession, conv: Conversation, *, now: datetime) -> None:
    """A person replied (Social Hood, a scheduled message, or the native app): clear needs_human
    and pause Auto for the workspace's takeover period, 0 meaning until resumed (FR-SUG-05, F-09).
    Sets the attributes on ``conv``; the caller flushes. The system note arrives with T5.6."""
    conv.needs_human = False
    conv.needs_human_reason = None
    minutes = await session.scalar(select(AiSettings.takeover_minutes))
    minutes = DEFAULT_TAKEOVER_MINUTES if minutes is None else minutes
    until = UNTIL_RESUMED if minutes == 0 else now + timedelta(minutes=minutes)
    current = conv.ai_paused_until
    if current is not None:
        # 'infinity' comes back from asyncpg as a naive datetime.max.
        current = current if current.tzinfo else current.replace(tzinfo=UTC)
        if current > until:  # never shorten a longer pause (or "until resumed")
            until = current
    conv.ai_paused_until = until


async def sender_name(session: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    return await session.scalar(select(User.name).where(User.id == user_id))


async def enqueue_send(
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    delay_s: float = 0,
    not_found: int = 0,
) -> bool:
    """Queue send_message. One waiting job per message (``send:{id}``); one running send per
    conversation (lock ``conv:{id}``), so a conversation's messages go out in order. A failed
    enqueue is logged: the sweeper picks up queued messages without a job."""
    from socialhood.jobs.tasks.send import send_message

    try:
        return await enqueue(
            send_message,
            key=f"send:{message_id}",
            lock=f"conv:{conversation_id}",
            delay_s=delay_s,
            message_id=str(message_id),
            conversation_id=str(conversation_id),
            workspace_id=str(workspace_id),
            not_found=not_found,
        )
    except Exception:
        log.warning("send_enqueue_failed", message_id=str(message_id))
        return False


def _worker_deps() -> PlatformDeps:
    from socialhood.jobs.runtime import runtime
    from socialhood.platforms.deps import deps_from

    rt = runtime()
    return deps_from(rt.http, rt.settings)


# ---------------------------------------------------------------- retry (F-07)


async def retry(
    session: AsyncSession, msg: Message, *, deps: PlatformDeps, now: datetime | None = None
) -> tuple[Message, bool]:
    """Put a failed message back in the queue. Returns (message, requeued). A message that is
    already queued or sending is returned unchanged, so a second click sends nothing more."""
    now = now or datetime.now(UTC)
    if msg.direction != Direction.OUTBOUND:
        raise ApiError("conflict", "Only messages sent from Social Hood can be retried.")
    if msg.status in (MessageStatus.QUEUED, MessageStatus.SENDING):
        return msg, False
    if msg.status != MessageStatus.FAILED:
        raise ApiError("conflict", "This message was already sent.")
    conv = await inbox.get_conversation(session, msg.conversation_id)
    acct = await accounts.get(session, msg.social_account_id)
    if conv is None or acct is None:
        raise ApiError("not_found")
    check_account(acct)
    caps = capabilities(acct, deps)
    require(caps, Capability.DM_SEND)
    window = reply_window(
        conv.platform,
        conv.last_inbound_at,
        human_agent=Capability.HUMAN_AGENT in caps,
        now=now,
    )
    if not may_send(window, send_kind(msg.source, template=msg.template is not None)):
        raise ApiError("reply_window_closed", window_closed_detail(conv.platform))
    requeued = await messages_repo.requeue_failed(session, msg.id)
    await session.refresh(msg)
    if requeued:
        events.queue_message(
            session,
            msg,
            created=False,
            sent_by_name=await sender_name(session, msg.sent_by_user_id),
        )
    return msg, requeued


# ---------------------------------------------------------------- deliver (the send_message job)


class Delivery(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"  # not ours to send: already sent, failed, or owned by another job
    MISSING = "missing"  # not visible (yet)
    DEFERRED = "deferred"  # waiting for a rate-limit token; re-scheduled, not a retry


@dataclass(frozen=True)
class SendJob:
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    workspace_id: uuid.UUID
    attempt: int = 0  # earlier attempts of this job; 0 on the first run
    not_found: int = 0


@dataclass(frozen=True)
class Part:
    attachment_index: int | None
    message: OutboundMessage
    bucket: Bucket


@dataclass
class _Send:
    session: AsyncSession
    redis: Redis
    msg: Message
    conv: Conversation
    acct: SocialAccount
    contact: Contact


Sleep = Callable[[float], Awaitable[Any]]


async def deliver(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    job: SendJob,
    *,
    will_retry: Callable[[PlatformError], bool],
    sleep: Sleep = asyncio.sleep,
    now: datetime | None = None,
) -> Delivery:
    """Send one message. Runs in the message's workspace scope.

    ``will_retry(error)`` says whether the queue will run this job again for a retryable error;
    when it will, the row stays ``sending`` and the error is re-raised, otherwise the row fails.
    """
    async with sessionmaker() as session:
        msg = await messages_repo.get(session, job.message_id)
        if msg is None:
            if job.not_found < NOT_FOUND_RETRIES:
                await enqueue_send(
                    job.message_id,
                    job.conversation_id,
                    job.workspace_id,
                    delay_s=NOT_FOUND_DELAY_S * (job.not_found + 1),
                    not_found=job.not_found + 1,
                )
            else:
                log.warning("send_message_missing", message_id=str(job.message_id))
            return Delivery.MISSING
        resuming = msg.status == MessageStatus.SENDING and job.attempt > 0
        if msg.direction != Direction.OUTBOUND or not (
            msg.status == MessageStatus.QUEUED or resuming
        ):
            return Delivery.SKIPPED
        conv = await inbox.get_conversation(session, msg.conversation_id)
        acct = await accounts.get(session, msg.social_account_id)
        contact = await inbox.get_contact(session, conv.contact_id) if conv else None
        if conv is None or acct is None or contact is None:
            return Delivery.SKIPPED
        send = _Send(session, redis, msg, conv, acct, contact)
        return await _deliver(send, deps, will_retry=will_retry, sleep=sleep, now=now)


async def _deliver(
    send: _Send,
    deps: PlatformDeps,
    *,
    will_retry: Callable[[PlatformError], bool],
    sleep: Sleep,
    now: datetime | None,
) -> Delivery:
    msg, acct = send.msg, send.acct
    now = now or datetime.now(UTC)
    was_queued = msg.status == MessageStatus.QUEUED

    # Everything may have changed since the message was queued: check again before sending.
    try:
        adapter: PlatformAdapter = adapter_for(acct, deps)
        caps = adapter.capabilities_for(acct)
    except PlatformError as error:
        return await _fail(send, error.code, error.message)
    if acct.status in BLOCKED_STATUSES:
        return await _fail(send, "account_needs_reconnect")
    window = reply_window(
        send.conv.platform,
        send.conv.last_inbound_at,
        human_agent=Capability.HUMAN_AGENT in caps,
        now=now,
    )
    kind = send_kind(msg.source, template=msg.template is not None)
    missing = _missing_capability(caps, msg)
    if missing is not None:
        return await _fail(send, "capability_unavailable")
    if not may_send(window, kind):
        return await _fail(send, "reply_window_closed")

    parts = pending_parts(msg, send.conv.platform, human_agent=needs_human_agent_tag(window, kind))
    buckets = TokenBuckets(send.redis)
    if parts:
        wait = await _take_token(buckets, parts[0].bucket, acct.id, sleep)
        if wait and was_queued:
            await enqueue_send(msg.id, msg.conversation_id, msg.workspace_id, delay_s=wait)
            return Delivery.DEFERRED
        if wait:
            return await _on_error(send, _bucket_error(wait), will_retry)

    claimed = await messages_repo.claim(
        send.session,
        msg.id,
        from_status=MessageStatus.QUEUED if was_queued else MessageStatus.SENDING,
        attempts=msg.attempts + 1,
        human_agent_tag=needs_human_agent_tag(window, kind),
    )
    if not claimed:
        await send.session.rollback()
        return Delivery.SKIPPED
    await _commit(send, publish=was_queued)

    sent_before = [a.get("platform_message_id") for a in msg.attachments or [] if a.get("sent")]
    last_id = next((m for m in reversed(sent_before) if m), msg.platform_message_id)
    for index, part in enumerate(parts):
        if index > 0:
            wait = await _take_token(buckets, part.bucket, acct.id, sleep)
            if wait:
                return await _on_error(send, _bucket_error(wait), will_retry)
        try:
            result = await adapter.send_message(acct, send.contact.platform_user_id, part.message)
        except PlatformError as error:
            return await _on_error(send, error, will_retry)
        except Exception:
            # Something unexpected after the call started: the platform may have the message.
            log.exception("send_message_unexpected_error", message_id=str(msg.id))
            return await _fail(send, DELIVERY_UNKNOWN)
        last_id = result.platform_message_id or last_id
        if part.attachment_index is not None:
            await _record_part(send, part.attachment_index, result.platform_message_id)

    await _mark_sent(send, last_id, now=datetime.now(UTC))
    log.info("message_sent", message_id=str(msg.id), parts=len(parts))
    return Delivery.SENT


def _missing_capability(caps: frozenset[Capability], msg: Message) -> Capability | None:
    needed = [Capability.DM_SEND]
    if msg.attachments:
        needed.append(Capability.DM_ATTACHMENTS)
    if msg.template:
        needed.append(Capability.TEMPLATES)
    return next((c for c in needed if c not in caps), None)


def pending_parts(msg: Message, platform: str, *, human_agent: bool) -> list[Part]:
    """The platform messages still to send for this row: each unsent attachment, then the text
    (or the template)."""
    parts: list[Part] = []
    for index, item in enumerate(msg.attachments or []):
        if item.get("sent"):
            continue
        attachment = OutboundAttachment(
            type=cast(Literal["image", "video", "audio", "file"], item["type"]),
            url=str(item.get("send_url") or item["url"]),
            filename=item.get("filename"),
            mime_type=item.get("send_mime_type") or item.get("mime_type"),
        )
        parts.append(
            Part(
                index,
                OutboundMessage(attachment=attachment, human_agent=human_agent),
                _bucket(platform, media=True),
            )
        )
    if msg.template:
        template = OutboundTemplate(
            name=str(msg.template["name"]),
            language=str(msg.template["language"]),
            params=tuple(str(p) for p in msg.template.get("params") or ()),
        )
        parts.append(Part(None, OutboundMessage(template=template), _bucket(platform, media=False)))
    elif msg.text:
        parts.append(
            Part(
                None,
                OutboundMessage(text=msg.text, human_agent=human_agent),
                _bucket(platform, media=False),
            )
        )
    return parts


def _bucket(platform: str, *, media: bool) -> Bucket:
    if platform == "whatsapp":
        return Bucket.WA_SEND
    # Images share the 10/s media bucket until T0.9 confirms their limit (TR-PL-09).
    return Bucket.IG_SEND_MEDIA if media else Bucket.IG_SEND


async def _take_token(
    buckets: TokenBuckets, bucket: Bucket, account_id: uuid.UUID, sleep: Sleep
) -> float:
    """0 once a token is taken; otherwise the seconds to wait when that is too long to wait here.
    A Valkey outage never blocks a send (the platform still enforces its own limits)."""
    waited = 0.0
    while True:
        try:
            wait = await buckets.take(bucket, str(account_id))
        except Exception:
            log.warning("token_bucket_unavailable", bucket=str(bucket))
            return 0.0
        if wait <= 0:
            return 0.0
        if waited + wait > MAX_INLINE_WAIT_S:
            return wait
        await sleep(wait)
        waited += wait


def _bucket_error(wait: float) -> PlatformError:
    return PlatformError(
        "platform_rate_limited", message="Waiting for this account's send rate", retry_after_s=wait
    )


async def _on_error(
    send: _Send, error: PlatformError, will_retry: Callable[[PlatformError], bool]
) -> Delivery:
    """Retry while the queue will (the row stays sending), else fail with the error's code."""
    if error.retryable and will_retry(error):
        log.info(
            "send_message_retry",
            message_id=str(send.msg.id),
            error_code=error.code,
            platform_code=error.platform_code,
        )
        raise error
    log.info(
        "send_message_failed",
        message_id=str(send.msg.id),
        error_code=error.code,
        platform_code=error.platform_code,
    )
    if error.code == "account_needs_reconnect":
        await mark_needs_reconnect(
            send.session,
            send.acct,
            f"{platform_name(send.acct.platform)} stopped accepting this connection.",
        )
    return await _fail(send, error.code, error.message)


async def _fail(send: _Send, code: str, platform_message: str = "") -> Delivery:
    reason = readable_error(
        code, send.conv.platform, platform_message=platform_message, username=send.acct.username
    )
    if await messages_repo.mark_failed(send.session, send.msg.id, code=code, message=reason):
        await _commit(send, publish=True)
    else:
        await send.session.rollback()
    return Delivery.FAILED


async def _record_part(send: _Send, index: int, platform_message_id: str | None) -> None:
    attachments = [dict(a) for a in send.msg.attachments or []]
    attachments[index] = {
        **attachments[index],
        "sent": True,
        "platform_message_id": platform_message_id,
    }
    await messages_repo.update(send.session, send.msg.id, attachments=attachments)
    await _commit(send, publish=False)


async def _mark_sent(send: _Send, platform_message_id: str | None, *, now: datetime) -> None:
    try:
        async with send.session.begin_nested():
            updated = await messages_repo.mark_sent(
                send.session, send.msg.id, platform_message_id=platform_message_id, at=now
            )
    except IntegrityError:
        # The echo of this send was stored first as its own row (TR-JOB-05 reconciliation
        # normally attaches it here); keep ours as sent without the duplicate id.
        log.warning("send_echo_stored_first", message_id=str(send.msg.id))
        updated = await messages_repo.mark_sent(
            send.session, send.msg.id, platform_message_id=None, at=now
        )
    if updated:
        await _commit(send, publish=True)
    else:
        await send.session.rollback()


async def _commit(send: _Send, *, publish: bool) -> None:
    """Reload the row and commit; with ``publish``, emit message.updated once committed."""
    await send.session.flush()
    await send.session.refresh(send.msg)
    if publish:
        events.queue_message(
            send.session,
            send.msg,
            created=False,
            sent_by_name=await sender_name(send.session, send.msg.sent_by_user_id),
        )
        await events.commit_and_publish(send.session, send.redis)
    else:
        await send.session.commit()


# ---------------------------------------------------------------- sweeper (TR-JOB-03)


async def give_up(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, message_id: uuid.UUID
) -> bool:
    """A send left ``sending`` with no job to finish it (the worker died mid-send): the platform
    may have it, so it fails as delivery_unknown and waits for the user (TR-JOB-05)."""
    async with sessionmaker() as session:
        msg = await messages_repo.get(session, message_id)
        if msg is None or msg.status != MessageStatus.SENDING:
            return False
        conv = await inbox.get_conversation(session, msg.conversation_id)
        acct = await accounts.get(session, msg.social_account_id)
        contact = await inbox.get_contact(session, conv.contact_id) if conv else None
        if conv is None or acct is None or contact is None:
            return False
        send = _Send(session, redis, msg, conv, acct, contact)
        reason = readable_error(DELIVERY_UNKNOWN, conv.platform)
        if not await messages_repo.mark_failed(
            session,
            msg.id,
            code=DELIVERY_UNKNOWN,
            message=reason,
            only_from=(MessageStatus.SENDING,),
        ):
            return False
        await _commit(send, publish=True)
        log.warning("send_message_abandoned", message_id=str(message_id))
        return True
