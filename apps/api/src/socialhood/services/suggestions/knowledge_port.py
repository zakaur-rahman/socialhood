"""The two knowledge functions suggestions need (TR-AI-08 retrieval, TR-AI-12 gaps).

ADAPTER: T5.3 (knowledge) owns retrieval and gap recording. These are thin stand-ins with the
same contract so T5.4 can be built and tested in parallel; at merge, replace the bodies of
``retrieve_knowledge`` and ``record_knowledge_gap`` with calls to the knowledge service (or
re-export its functions here) and keep ``RetrievedChunk``'s fields. Callers import only this
module.

- ``retrieve_knowledge(session, query)``: embed the query as RETRIEVAL_QUERY, take the 8 nearest
  chunks of ready sources in the workspace by cosine distance, keep those with similarity
  (1 - distance) >= AI_RETRIEVAL_MIN_SIM, return at most 6, most similar first.
- ``record_knowledge_gap(session, missing_topic, message_id, now)``: normalise the topic
  (lowercase, no punctuation, single spaces); an open gap with the same topic or a trigram
  similarity >= 0.6 counts one more occurrence (keeping up to 5 example messages, newest first);
  a dismissed one reopens; otherwise a new open gap. Runs in the caller's transaction.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.ai.registry import get_provider
from socialhood.db.tenancy import require_workspace
from socialhood.models.ai import (
    GapStatus,
    KnowledgeChunk,
    KnowledgeGap,
    KnowledgeSource,
    KnowledgeStatus,
)
from socialhood.settings import get_settings

NEAREST = 8
MAX_CHUNKS = 6
GAP_SIMILARITY = 0.6
MAX_EXAMPLES = 5
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    content: str
    similarity: float


async def retrieve_knowledge(session: AsyncSession, query: str) -> list[RetrievedChunk]:
    """TR-AI-08 retrieval for the current workspace (see the module docstring)."""
    if not query.strip():
        return []
    [vector] = await get_provider().embed([query], kind="query")
    # pgvector >= 0.8: keep scanning past other workspaces' neighbours (TR-AI-08).
    await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    rows = await session.execute(
        select(
            KnowledgeChunk.id,
            KnowledgeChunk.source_id,
            KnowledgeSource.title,
            KnowledgeChunk.content,
            distance.label("distance"),
        )
        .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
        .where(KnowledgeSource.status == KnowledgeStatus.READY)
        .order_by(distance)
        .limit(NEAREST)
    )
    minimum = get_settings().ai_retrieval_min_sim
    chunks = [
        RetrievedChunk(chunk_id, source_id, title, content, 1.0 - float(dist))
        for chunk_id, source_id, title, content, dist in rows.all()
    ]
    return [c for c in chunks if c.similarity >= minimum][:MAX_CHUNKS]


def normalize_topic(topic: str) -> str:
    return " ".join(_PUNCTUATION.sub(" ", topic.casefold()).split())


async def record_knowledge_gap(
    session: AsyncSession, missing_topic: str, message_id: uuid.UUID | None, now: datetime
) -> uuid.UUID | None:
    """TR-AI-12 (see the module docstring); returns the gap's id, or None for an empty topic."""
    normalized = normalize_topic(missing_topic)
    if not normalized:
        return None
    similarity = func.similarity(KnowledgeGap.topic_normalized, normalized)
    gap = (
        await session.scalars(
            select(KnowledgeGap)
            .where(
                KnowledgeGap.status == GapStatus.OPEN,
                (KnowledgeGap.topic_normalized == normalized) | (similarity >= GAP_SIMILARITY),
            )
            .order_by(similarity.desc())
            .limit(1)
            .with_for_update()
        )
    ).first()
    if gap is None:
        gap = (
            await session.scalars(
                select(KnowledgeGap)
                .where(
                    KnowledgeGap.status == GapStatus.DISMISSED,
                    KnowledgeGap.topic_normalized == normalized,
                )
                .order_by(KnowledgeGap.last_seen_at.desc())
                .limit(1)
                .with_for_update()
            )
        ).first()
        if gap is not None:
            gap.status = GapStatus.OPEN
            gap.dismissed_at = None
    if gap is not None:
        _seen(gap, message_id, now)
        await session.flush()
        return gap.id
    examples = [message_id] if message_id else []
    statement = (
        insert(KnowledgeGap)
        .values(
            workspace_id=require_workspace(),
            topic=missing_topic.strip()[:120],
            topic_normalized=normalized,
            first_seen_at=now,
            last_seen_at=now,
            example_message_ids=examples,
        )
        .on_conflict_do_update(
            index_elements=[KnowledgeGap.workspace_id, KnowledgeGap.topic_normalized],
            index_where=text("status = 'open'"),
            set_={
                "occurrences": KnowledgeGap.occurrences + 1,
                "last_seen_at": now,
            },
        )
        .returning(KnowledgeGap.id)
    )
    return (await session.execute(statement)).scalar_one()


def _seen(gap: KnowledgeGap, message_id: uuid.UUID | None, now: datetime) -> None:
    gap.occurrences = (gap.occurrences or 0) + 1
    gap.last_seen_at = max(gap.last_seen_at, now) if gap.last_seen_at else now
    if message_id is not None:
        examples = [m for m in gap.example_message_ids or [] if m != message_id]
        gap.example_message_ids = [message_id, *examples][:MAX_EXAMPLES]
