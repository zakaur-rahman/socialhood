"""Reply suggestions, auto-reply decisions and AI settings (§5.5; T5.4, T5.5, T5.6). Writes are
scoped to the current workspace (TR-TEN-04); status changes only move a suggestion out of
``pending`` (§5.9's state machine), so a change that lost a race changes nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import (
    AiDecision,
    AiSettings,
    DecisionOutcome,
    KnowledgeChunk,
    KnowledgeSource,
    ReplySuggestion,
    SuggestionStatus,
)
from socialhood.models.inbox import Message, MessageSource
from socialhood.repositories.base import scoped_update

_FRESH = {"populate_existing": True}
PENDING = SuggestionStatus.PENDING


# ---------------------------------------------------------------- suggestions


async def get(session: AsyncSession, suggestion_id: uuid.UUID) -> ReplySuggestion | None:
    return (
        await session.scalars(select(ReplySuggestion).where(ReplySuggestion.id == suggestion_id))
    ).one_or_none()


async def lock(session: AsyncSession, suggestion_id: uuid.UUID) -> ReplySuggestion | None:
    return (
        await session.scalars(
            select(ReplySuggestion).where(ReplySuggestion.id == suggestion_id).with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def pending_for(session: AsyncSession, conversation_id: uuid.UUID) -> ReplySuggestion | None:
    return (
        await session.scalars(
            select(ReplySuggestion).where(
                ReplySuggestion.conversation_id == conversation_id,
                ReplySuggestion.status == PENDING,
            )
        )
    ).one_or_none()


async def generations(session: AsyncSession, message_id: uuid.UUID) -> int | None:
    """The highest regeneration_index of the inbox suggestions for a message, or None."""
    return await session.scalar(
        select(func.max(ReplySuggestion.regeneration_index)).where(
            ReplySuggestion.message_id == message_id,
            ReplySuggestion.automation_run_id.is_(None),
        )
    )


async def exists_generation(session: AsyncSession, message_id: uuid.UUID, index: int) -> bool:
    found = await session.scalar(
        select(ReplySuggestion.id)
        .where(
            ReplySuggestion.message_id == message_id,
            ReplySuggestion.regeneration_index == index,
            ReplySuggestion.automation_run_id.is_(None),
        )
        .limit(1)
    )
    return found is not None


async def leave_pending(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    to: SuggestionStatus,
    *,
    before: datetime | None = None,
) -> list[ReplySuggestion]:
    """Move the conversation's pending suggestion to ``to`` (superseded, dismissed). With
    ``before``, only one answering a message older than that."""
    statement = scoped_update(ReplySuggestion, conversation_id=conversation_id, status=PENDING)
    if before is not None:
        answered = select(Message.occurred_at).where(Message.id == ReplySuggestion.message_id)
        statement = statement.where(answered.scalar_subquery() < before)
    result = await session.scalars(
        statement.values(status=to).returning(ReplySuggestion), execution_options=_FRESH
    )
    return list(result.all())


async def finish(
    session: AsyncSession, suggestion_id: uuid.UUID, to: SuggestionStatus, **values: Any
) -> ReplySuggestion | None:
    """pending → ``to`` with ``values``; None when it was no longer pending."""
    result = await session.scalars(
        scoped_update(ReplySuggestion, id=suggestion_id, status=PENDING)
        .values(status=to, **values)
        .returning(ReplySuggestion),
        execution_options=_FRESH,
    )
    return result.one_or_none()


async def sources_of(
    session: AsyncSession, chunk_ids: Sequence[uuid.UUID]
) -> list[tuple[uuid.UUID, str]]:
    """The distinct knowledge sources of these chunks (id, title), in the chunks' order."""
    if not chunk_ids:
        return []
    rows = (
        await session.execute(
            select(KnowledgeChunk.id, KnowledgeSource.id, KnowledgeSource.title)
            .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
            .where(KnowledgeChunk.id.in_(list(chunk_ids)))
        )
    ).all()
    by_chunk = {chunk_id: (source_id, title) for chunk_id, source_id, title in rows}
    seen: dict[uuid.UUID, str] = {}
    for chunk_id in chunk_ids:
        found = by_chunk.get(chunk_id)
        if found is not None and found[0] not in seen:
            seen[found[0]] = found[1]
    return list(seen.items())


async def chunk_texts(session: AsyncSession, chunk_ids: Sequence[uuid.UUID]) -> list[str]:
    if not chunk_ids:
        return []
    return list(
        (
            await session.scalars(
                select(KnowledgeChunk.content).where(KnowledgeChunk.id.in_(list(chunk_ids)))
            )
        ).all()
    )


async def latest_used_chunk_ids(
    session: AsyncSession, conversation_id: uuid.UUID
) -> list[uuid.UUID]:
    """The knowledge chunks behind the conversation's newest draft that used any (the summary's
    next step is grounded in them, summary.v2); [] when no draft used knowledge."""
    ids = await session.scalar(
        select(ReplySuggestion.used_chunk_ids)
        .where(
            ReplySuggestion.conversation_id == conversation_id,
            func.cardinality(ReplySuggestion.used_chunk_ids) > 0,
        )
        .order_by(ReplySuggestion.created_at.desc(), ReplySuggestion.id.desc())
        .limit(1)
    )
    return list(ids or [])


# ---------------------------------------------------------------- decisions (TR-AI-07)


async def get_decision(session: AsyncSession, decision_id: uuid.UUID) -> AiDecision | None:
    return (
        await session.scalars(select(AiDecision).where(AiDecision.id == decision_id))
    ).one_or_none()


async def decision_for_message(session: AsyncSession, message: Message) -> AiDecision | None:
    """The decision that sent this AI message, or the latest one about this inbound message."""
    if message.source == MessageSource.AI_AUTO:
        where = AiDecision.sent_message_id == message.id
    else:
        where = AiDecision.message_id == message.id
    return (
        await session.scalars(
            select(AiDecision)
            .where(where)
            .order_by(AiDecision.created_at.desc(), AiDecision.id.desc())
            .limit(1)
        )
    ).first()


async def replied_to(session: AsyncSession, message_id: uuid.UUID) -> bool:
    """An AI reply was already sent for this inbound message (TR-AI-07 check 12)."""
    found = await session.scalar(
        select(AiDecision.id)
        .where(
            AiDecision.message_id == message_id,
            AiDecision.outcome == DecisionOutcome.AUTO_SENT,
        )
        .limit(1)
    )
    return found is not None


async def ai_replies_since(
    session: AsyncSession, conversation_id: uuid.UUID, since: datetime
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.source == MessageSource.AI_AUTO,
            Message.occurred_at >= since,
        )
    )
    return int(count or 0)


async def set_feedback(
    session: AsyncSession, decision_id: uuid.UUID, feedback: str | None
) -> AiDecision | None:
    result = await session.scalars(
        scoped_update(AiDecision, id=decision_id)
        .values(user_feedback=feedback)
        .returning(AiDecision),
        execution_options=_FRESH,
    )
    return result.one_or_none()


# ---------------------------------------------------------------- AI settings (FR-KB-04)


async def settings_row(session: AsyncSession) -> AiSettings | None:
    return await session.scalar(select(AiSettings))


async def update_settings(session: AsyncSession, **values: Any) -> AiSettings | None:
    result = await session.scalars(
        scoped_update(AiSettings).values(**values).returning(AiSettings),
        execution_options=_FRESH,
    )
    return result.one_or_none()
