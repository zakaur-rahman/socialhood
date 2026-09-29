"""Suggested replies (T5.4; TR-AI-06, FR-SUG-02, FR-SUG-03, FR-KB-06, F-08).

``generate`` is the suggest_reply job (enqueued by analysis for a message that needs a reply in
Suggest or Auto mode, and by Regenerate). It skips a message that no longer needs a suggestion:
the mode is off, a newer customer message arrived (that one gets its own), or (except for a
regeneration) someone already replied or an automation handled it (FR-AUT-07). Otherwise it
drafts (services/suggestions/drafting, 2 credits) and, holding the conversation's row lock,
supersedes the pending suggestion and inserts the new one as ``pending``; a draft that cannot
answer records its knowledge gap (first generation only, so regenerating does not count the
question twice). suggestion.created (and suggestion.updated for the superseded one) are
published after the commit, and in Auto mode decide_auto_reply is enqueued (first generation
only: a person asking for another draft is handling the conversation). A failed call stores a
``failed`` suggestion so the card stops waiting; used-up credits store nothing (FR-AI-05).

What happens to a pending suggestion (§5.9):
- sent with its id: ``sent`` when the text is the suggestion's (ignoring spacing), else
  ``edited_sent`` with the normalised Levenshtein distance (FR-SUG-02);
- a person's reply without it (Social Hood or the native app): ``dismissed``;
- a new customer message: ``superseded``; Dismiss: ``dismissed``.

The projection (§5.10 Suggestion): ``low_confidence`` below 0.6, ``sources`` the distinct
knowledge sources of the chunks used, ``regenerations_left`` of 5 per message.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai.metering import QuotaExceeded
from socialhood.ai.provider import AIError
from socialhood.errors import ApiError, FieldError
from socialhood.models.ai import ReplySuggestion, SuggestionStatus
from socialhood.models.inbox import Conversation, Direction, Message, MessageSource
from socialhood.observability.logging import get_logger
from socialhood.realtime import events
from socialhood.repositories import inbox, social_accounts
from socialhood.repositories import ingest as ingest_rows
from socialhood.repositories import suggestions as repo
from socialhood.schemas.inbox import Suggestion, SuggestionSource
from socialhood.services.suggestions import drafting, knowledge_port

log = get_logger(__name__)

FEATURE: Literal["reply_suggestion"] = "reply_suggestion"
MAX_REGENERATIONS = 5  # F-08: per message
LOW_CONFIDENCE = 0.6  # §5.10 Suggestion.low_confidence
S = SuggestionStatus
ANSWERED_BY = (
    MessageSource.HUMAN,
    MessageSource.AI_AUTO,
    MessageSource.AUTOMATION,
    MessageSource.NATIVE_APP,
)


class Outcome(StrEnum):
    STORED = "stored"
    FAILED = "failed"  # the call failed; a failed suggestion was stored
    SKIPPED = "skipped"  # not needed (any more)
    MISSING = "missing"  # the conversation or message is not there
    NO_CREDITS = "no_credits"  # FR-AI-05


# ---------------------------------------------------------------- projection and events


async def suggestion_out(session: AsyncSession, row: ReplySuggestion) -> Suggestion:
    sources = await repo.sources_of(session, row.used_chunk_ids or [])
    left = 0 if row.automation_run_id else max(MAX_REGENERATIONS - row.regeneration_index, 0)
    return Suggestion(
        id=row.id,
        conversation_id=row.conversation_id,
        message_id=row.message_id,
        status=row.status,
        can_answer=row.can_answer,
        reply_text=row.reply_text,
        missing_info=row.missing_info,
        low_confidence=row.model_confidence is not None and row.model_confidence < LOW_CONFIDENCE,
        sources=[SuggestionSource(id=source_id, title=title) for source_id, title in sources],
        regenerations_left=left,
        created_at=row.created_at,
    )


async def pending_out(session: AsyncSession, conversation_id: uuid.UUID) -> Suggestion | None:
    """Conversation.pending_suggestion."""
    row = await repo.pending_for(session, conversation_id)
    return await suggestion_out(session, row) if row is not None else None


async def queue_event(session: AsyncSession, row: ReplySuggestion, *, created: bool) -> None:
    """suggestion.created / suggestion.updated, published with the caller's commit."""
    out = await suggestion_out(session, row)
    events.queue(
        session,
        row.workspace_id,
        "suggestion.created" if created else "suggestion.updated",
        {"conversation_id": str(row.conversation_id), "suggestion": out.model_dump(mode="json")},
    )


# ---------------------------------------------------------------- jobs


async def enqueue_suggest(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    regeneration: int = 0,
) -> bool:
    """suggest_reply for a message (job catalogue: key suggest:{message_id}:{n}). Analysis
    calls this (or enqueues the task by name with the same arguments)."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.suggestions import suggest_reply

    return await enqueue(
        suggest_reply,
        key=f"suggest:{message_id}:{regeneration}",
        workspace_id=str(workspace_id),
        conversation_id=str(conversation_id),
        message_id=str(message_id),
        regeneration=regeneration,
    )


async def enqueue_decide(workspace_id: uuid.UUID, suggestion_id: uuid.UUID) -> bool:
    """decide_auto_reply (job catalogue: key auto:{suggestion_id})."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.suggestions import decide_auto_reply

    return await enqueue(
        decide_auto_reply,
        key=f"auto:{suggestion_id}",
        workspace_id=str(workspace_id),
        suggestion_id=str(suggestion_id),
    )


async def _stale(
    session: AsyncSession, conv: Conversation, msg: Message, *, automatic: bool
) -> str | None:
    """Why the message needs no new suggestion, or None."""
    after = select(Message.id).where(
        Message.conversation_id == conv.id,
        Message.occurred_at > msg.occurred_at,
    )
    newer = await session.scalar(
        after.where(
            Message.direction == Direction.INBOUND, Message.source == MessageSource.CUSTOMER
        ).limit(1)
    )
    if newer is not None:
        return "newer_message"
    if not automatic:
        return None
    if msg.automation_handled:
        return "automation_handled"
    replied = await session.scalar(
        after.where(Message.direction == Direction.OUTBOUND, Message.source.in_(ANSWERED_BY)).limit(
            1
        )
    )
    return "answered" if replied is not None else None


async def generate(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    *,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    regeneration: int = 0,
    will_retry: Callable[[AIError], bool] | None = None,
    now: datetime | None = None,
) -> Outcome:
    """The suggest_reply job, in the workspace's scope (see the module docstring).
    ``will_retry(error)``: the queue runs the job again for this error, so re-raise it."""
    now = now or datetime.now(UTC)
    automatic = regeneration == 0
    async with sessionmaker() as session:
        conv = await inbox.get_conversation(session, conversation_id)
        msg = await inbox.get_message(session, message_id)
        if conv is None or msg is None or msg.conversation_id != conv.id:
            return Outcome.MISSING
        acct = await social_accounts.get(session, conv.social_account_id)
        if (
            acct is None
            or msg.direction != Direction.INBOUND
            or msg.source != MessageSource.CUSTOMER
        ):
            return Outcome.SKIPPED
        mode = conv.ai_mode_override or acct.ai_mode
        if mode == "off" or await repo.exists_generation(session, msg.id, regeneration):
            return Outcome.SKIPPED
        stale = await _stale(session, conv, msg, automatic=automatic)
        if stale is not None:
            log.info("suggestion_not_needed", message_id=str(msg.id), reason=stale)
            return Outcome.SKIPPED
        lines = await drafting.conversation_lines(session, msg)
        request = drafting.DraftRequest(
            workspace_id=workspace_id,
            feature=FEATURE,
            platform=conv.platform,
            lines=lines,
            query=await drafting.retrieval_query(session, msg),
            ref_type="message",
            ref_id=msg.id,
            language=await drafting.message_language(session, msg.id),
            quotable=[line.text for line in lines],
        )
        brand = await drafting.load_brand(session)
    try:
        draft = await drafting.draft(sessionmaker, request, brand=brand)
    except QuotaExceeded:
        log.info("suggestion_no_credits", message_id=str(message_id))
        return Outcome.NO_CREDITS
    except AIError as error:
        if will_retry is not None and will_retry(error):
            raise
        log.warning("suggestion_failed", message_id=str(message_id), error_code=error.code)
        await _store_failed(sessionmaker, redis, msg, regeneration, error)
        return Outcome.FAILED
    stored = await _store(sessionmaker, redis, msg, regeneration, draft, now=now)
    if stored is None:
        return Outcome.SKIPPED
    if automatic and mode == "auto":
        await enqueue_decide(workspace_id, stored.id)
    return Outcome.STORED


async def _store(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    msg: Message,
    regeneration: int,
    draft: drafting.Draft,
    *,
    now: datetime,
) -> ReplySuggestion | None:
    async with sessionmaker() as session:
        conv = await ingest_rows.lock_conversation(session, msg.conversation_id)
        if conv is None:
            return None
        stale = await _stale(session, conv, msg, automatic=regeneration == 0)
        if stale is not None:
            log.info("suggestion_not_needed", message_id=str(msg.id), reason=stale)
            return None
        superseded = await repo.leave_pending(session, conv.id, S.SUPERSEDED)
        row = ReplySuggestion(
            conversation_id=conv.id,
            message_id=msg.id,
            status=S.PENDING,
            can_answer=draft.can_answer,
            reply_text=draft.reply,
            missing_info=draft.missing_info,
            missing_topic=draft.missing_topic,
            model_confidence=draft.confidence,
            top_similarity=draft.top_similarity,
            used_chunk_ids=draft.used_chunk_ids,
            regeneration_index=regeneration,
            model=draft.model,
            prompt_version=draft.prompt_version,
            input_tokens=draft.input_tokens,
            output_tokens=draft.output_tokens,
            latency_ms=draft.latency_ms,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        if not draft.can_answer and draft.missing_topic and regeneration == 0:
            await knowledge_port.record_knowledge_gap(session, draft.missing_topic, msg.id, now)
        for old in superseded:
            await queue_event(session, old, created=False)
        await queue_event(session, row, created=True)
        await events.commit_and_publish(session, redis)
        log.info(
            "suggestion_stored",
            suggestion_id=str(row.id),
            can_answer=row.can_answer,
            regeneration=regeneration,
        )
        return row


async def _store_failed(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    msg: Message,
    regeneration: int,
    error: AIError,
) -> None:
    """§5.9 ``failed``: the pending suggestion (if any) stays; the card stops waiting."""
    async with sessionmaker() as session:
        row = ReplySuggestion(
            conversation_id=msg.conversation_id,
            message_id=msg.id,
            status=S.FAILED,
            can_answer=False,
            regeneration_index=regeneration,
            error_code=error.code,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        await queue_event(session, row, created=True)
        await events.commit_and_publish(session, redis)


# ---------------------------------------------------------------- regenerate and dismiss (F-08)


async def regenerate(session: AsyncSession, conv: Conversation) -> uuid.UUID:
    """POST …/conversations/{id}/suggestions: another draft for the customer's latest message
    (up to 5 per message). The mode must not be off and credits must remain; returns the
    message answered. The job does the work; the caller commits (quota() may create the
    period's usage counter)."""
    from socialhood.ai.metering import quota
    from socialhood.billing.plans import CREDIT_COSTS

    acct = await social_accounts.get(session, conv.social_account_id)
    mode = conv.ai_mode_override or (acct.ai_mode if acct else "off")
    if mode == "off":
        raise ApiError("conflict", "AI replies are off for this conversation.")
    target = await session.scalar(
        select(Message)
        .where(
            Message.conversation_id == conv.id,
            Message.direction == Direction.INBOUND,
            Message.source == MessageSource.CUSTOMER,
        )
        .order_by(Message.occurred_at.desc(), Message.id.desc())
        .limit(1)
    )
    if target is None:
        raise ApiError("conflict", "There's no customer message to reply to yet.")
    latest = await repo.generations(session, target.id)
    n = 0 if latest is None else latest + 1
    if n > MAX_REGENERATIONS:
        raise ApiError(
            "conflict", f"You can regenerate a reply up to {MAX_REGENERATIONS} times per message."
        )
    if not (await quota(session)).allows(CREDIT_COSTS[FEATURE]):
        raise ApiError("quota_exceeded", "Your AI credits are used up until they reset.")
    await enqueue_suggest(conv.workspace_id, conv.id, target.id, regeneration=n)
    return target.id


async def dismiss(session: AsyncSession, row: ReplySuggestion) -> ReplySuggestion:
    """POST …/suggestions/{id}/dismiss: a pending suggestion becomes dismissed; any other is
    returned unchanged. The caller commits and publishes."""
    updated = await repo.finish(session, row.id, S.DISMISSED)
    if updated is None:
        return row
    await queue_event(session, updated, created=False)
    return updated


# ---------------------------------------------------------------- sends and new messages


async def for_send(
    session: AsyncSession, conv: Conversation, suggestion_id: uuid.UUID | None
) -> ReplySuggestion | None:
    """The suggestion a send names, locked; it must belong to the conversation. The
    conversation is locked first, the order every writer of suggestions takes."""
    if suggestion_id is None:
        return None
    await ingest_rows.lock_conversation(session, conv.id)
    row = await repo.lock(session, suggestion_id)
    if row is None or row.conversation_id != conv.id:
        raise ApiError(
            "validation_error",
            errors=[FieldError("suggestion_id", "This suggestion isn't in this conversation.")],
        )
    return row


def _compact(text: str | None) -> str:
    return " ".join((text or "").split())


def edit_distance(a: str, b: str) -> float:
    """Levenshtein distance divided by the longer text's length (0 = same, 1 = all changed)."""
    if a == b:
        return 0.0
    if not a or not b:
        return 1.0
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return round(previous[-1] / len(a), 4)


async def after_send(
    session: AsyncSession,
    conv: Conversation,
    msg: Message,
    suggestion: ReplySuggestion | None,
) -> None:
    """A message was queued (services/sending). With its suggestion: sent or edited_sent. A
    person's reply without one dismisses the pending suggestion (F-08)."""
    if suggestion is not None:
        if suggestion.status != S.PENDING:
            return
        sent, suggested = _compact(msg.text), _compact(suggestion.reply_text)
        distance = 0.0 if sent == suggested else edit_distance(suggested, sent)
        updated = await repo.finish(
            session,
            suggestion.id,
            S.SENT if distance == 0.0 else S.EDITED_SENT,
            sent_message_id=msg.id,
            edit_distance=distance,
        )
        if updated is not None:
            await queue_event(session, updated, created=False)
        return
    if msg.source == MessageSource.HUMAN:
        await dismiss_pending(session, conv.id)


async def dismiss_pending(session: AsyncSession, conversation_id: uuid.UUID) -> None:
    """A person replied without the suggestion (including from the native app)."""
    for row in await repo.leave_pending(session, conversation_id, S.DISMISSED):
        await queue_event(session, row, created=False)


async def supersede_for_inbound(session: AsyncSession, conv: Conversation, msg: Message) -> None:
    """A new customer message replaces an unused suggestion (FR-SUG-02)."""
    for row in await repo.leave_pending(session, conv.id, S.SUPERSEDED, before=msg.occurred_at):
        await queue_event(session, row, created=False)
