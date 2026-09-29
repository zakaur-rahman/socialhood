"""The two knowledge functions suggestions need (TR-AI-08 retrieval, TR-AI-12 gaps), from the
knowledge service (services/knowledge). Callers import only this module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.services.knowledge import gaps, retrieval
from socialhood.services.knowledge.gaps import normalize_topic
from socialhood.services.knowledge.retrieval import Retrieved as RetrievedChunk

__all__ = ["RetrievedChunk", "normalize_topic", "record_knowledge_gap", "retrieve_knowledge"]


async def retrieve_knowledge(session: AsyncSession, query: str) -> list[RetrievedChunk]:
    """At most 6 chunks of ready sources with similarity >= AI_RETRIEVAL_MIN_SIM, best first."""
    if not query.strip():
        return []
    return await retrieval.retrieve(session, query)


async def record_knowledge_gap(
    session: AsyncSession, missing_topic: str, message_id: uuid.UUID | None, now: datetime
) -> uuid.UUID | None:
    """Count the missing topic as a knowledge gap; returns the gap's id. A label with no words
    (only punctuation) records nothing."""
    if not normalize_topic(missing_topic):
        return None
    gap = await gaps.record_gap(
        session, missing_topic=missing_topic, message_id=message_id, now=now
    )
    return gap.id
