"""Questions the AI couldn't answer (T5.10; FR-KB-06, TR-AI-12, F-17).

When a suggestion comes back with can_answer = false, the suggestion job calls

    await record_gap(session, missing_topic=out.missing_topic, message_id=message.id, now=now)

which normalises the topic (lowercase, punctuation stripped, spaces collapsed) and matches it to
an open gap of the workspace by exact topic or pg_trgm similarity >= 0.6: a match counts one more
ask (the message joins the 5 newest examples), otherwise a new open gap starts. A dismissed gap
that matches reopens. The same message counts once, so regenerating its suggestion does not
inflate the count. ``record_gap`` flushes; the caller commits.

The Knowledge page lists open gaps asked in the last 30 days, most asked first, with up to three
example messages; Dismiss hides a gap until it is asked again; an FAQ created with ``gap_id``
answers it (services/knowledge/sources.py). Home shows the open count.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.ai import GapStatus
from socialhood.models.ai import KnowledgeGap as GapRow
from socialhood.repositories import knowledge as repo
from socialhood.schemas.knowledge import KnowledgeGap, KnowledgeGapExample, KnowledgeGapList

MIN_SIMILARITY = 0.7  # C-034: the fallback after exact labels; 0.6 merged "uae" with "usa"
WINDOW = timedelta(days=30)
MAX_EXAMPLES = 5  # stored, newest first
SHOWN_EXAMPLES = 3  # FR-KB-06
LIST_LIMIT = 100
TOPIC_CHARS = 120
FALLBACK_TOPIC = "other questions"  # a label that normalises to nothing

_INSIDE_WORDS = re.compile(r"['`.\u2018\u2019]")  # apostrophes and dots: "don't", "U.A.E."
_PUNCTUATION = re.compile(r"[^\w\s]|_")


def normalize_topic(topic: str) -> str:
    """Lowercase, punctuation stripped, spaces collapsed: "Shipping to U.A.E.?" -> "shipping to
    uae". Apostrophes and dots vanish ("don't" -> "dont"); other punctuation separates words
    ("cash-on-delivery" -> "cash on delivery")."""
    text = unicodedata.normalize("NFKC", topic).casefold()
    text = _PUNCTUATION.sub(" ", _INSIDE_WORDS.sub("", text))
    return " ".join(text.split())


async def record_gap(
    session: AsyncSession, *, missing_topic: str, message_id: uuid.UUID | None, now: datetime
) -> GapRow:
    """Count a question the AI couldn't answer from knowledge (TR-AI-12); returns its gap.
    ``message_id`` is None for a comment's automation reply: counted, with no example."""
    label = " ".join(missing_topic.split())[:TOPIC_CHARS]
    normalized = normalize_topic(label)
    if not normalized:
        label = normalized = FALLBACK_TOPIC
    for attempt in range(2):
        try:
            async with session.begin_nested():
                gap = await _upsert(session, label, normalized, message_id, now)
            await session.refresh(gap)
            return gap
        except IntegrityError:
            # Another job opened the same topic at the same moment; match it this time.
            if attempt:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


async def _upsert(
    session: AsyncSession, label: str, normalized: str, message_id: uuid.UUID | None, now: datetime
) -> GapRow:
    gap = await repo.gap_matching(
        session, normalized, status=GapStatus.OPEN, min_similarity=MIN_SIMILARITY
    )
    if gap is None:
        gap = await repo.gap_matching(
            session, normalized, status=GapStatus.DISMISSED, min_similarity=MIN_SIMILARITY
        )
    if gap is None:
        gap = GapRow(
            topic=label,
            topic_normalized=normalized,
            status=GapStatus.OPEN,
            occurrences=1,
            first_seen_at=now,
            last_seen_at=now,
            example_message_ids=[message_id] if message_id else [],
        )
        session.add(gap)
        await session.flush()
        return gap
    examples = list(gap.example_message_ids or [])
    if message_id is not None and message_id in examples:
        return gap  # this message was counted already (a regenerated suggestion)
    if gap.status == GapStatus.DISMISSED:
        gap.status = GapStatus.OPEN  # asked again (FR-KB-06)
        gap.dismissed_at = None
    gap.occurrences += 1
    gap.last_seen_at = max(gap.last_seen_at, now)
    if message_id is not None:
        gap.example_message_ids = [message_id, *examples][:MAX_EXAMPLES]
    await session.flush()
    return gap


async def list_gaps(session: AsyncSession, *, status: str, now: datetime) -> KnowledgeGapList:
    """Gaps in ``status`` asked in the last 30 days, most asked first (FR-KB-06)."""
    rows = await repo.list_gaps(session, status=status, since=now - WINDOW, limit=LIST_LIMIT)
    return KnowledgeGapList(items=await _out(session, rows))


async def count_open(session: AsyncSession, *, now: datetime) -> int:
    """Home's "{n} questions the AI couldn't answer" (Overview.knowledge_gaps_open)."""
    return await repo.count_open_gaps(session, since=now - WINDOW)


async def open_topics(session: AsyncSession, *, now: datetime, limit: int = 20) -> list[str]:
    """The most asked open topics, for a prompt that asks the model to reuse an existing label
    for the same missing fact (see docs/CONFLICTS.md on merging "Dubai" into "UAE")."""
    return await repo.open_gap_topics(session, since=now - WINDOW, limit=limit)


async def dismiss(session: AsyncSession, gap_id: uuid.UUID, *, now: datetime) -> KnowledgeGap:
    """Hide a gap until it is asked again; dismissing twice is fine. 409 once answered."""
    gap = await repo.get_gap(session, gap_id, for_update=True)
    if gap is None:
        raise ApiError("not_found")
    if gap.status == GapStatus.ANSWERED:
        raise ApiError("conflict", "This question already has an answer.")
    if gap.status == GapStatus.OPEN:
        gap.status = GapStatus.DISMISSED
        gap.dismissed_at = now
        await session.flush()
        await session.refresh(gap)
    [out] = await _out(session, [gap])
    return out


async def gap_to_answer(session: AsyncSession, gap_id: uuid.UUID) -> GapRow:
    """The gap an FAQ is about to answer, locked; 404 when it isn't this workspace's."""
    gap = await repo.get_gap(session, gap_id, for_update=True)
    if gap is None:
        raise ApiError("not_found")
    return gap


def mark_answered(gap: GapRow, source_id: uuid.UUID) -> None:
    """F-17: the gap leaves the list, linked to the FAQ that answers it."""
    gap.status = GapStatus.ANSWERED
    gap.resolved_source_id = source_id


async def _out(session: AsyncSession, rows: Sequence[GapRow]) -> list[KnowledgeGap]:
    wanted = [mid for gap in rows for mid in (gap.example_message_ids or [])]
    messages = await repo.messages_by_id(session, wanted)
    items: list[KnowledgeGap] = []
    for gap in rows:
        examples: list[KnowledgeGapExample] = []
        for message_id in gap.example_message_ids or []:
            message = messages.get(message_id)
            if message is None or not (message.text or "").strip():
                continue  # deleted, or a message without text
            examples.append(
                KnowledgeGapExample(
                    message_id=message.id,
                    conversation_id=message.conversation_id,
                    text=message.text or "",
                    occurred_at=message.occurred_at,
                )
            )
            if len(examples) == SHOWN_EXAMPLES:
                break
        items.append(
            KnowledgeGap.model_validate(
                {
                    "id": gap.id,
                    "topic": gap.topic,
                    "status": gap.status,
                    "occurrences": gap.occurrences,
                    "first_seen_at": gap.first_seen_at,
                    "last_seen_at": gap.last_seen_at,
                    "examples": examples,
                }
            )
        )
    return items
