"""The two knowledge functions suggestions need (TR-AI-08 retrieval, TR-AI-12 gaps), from the
knowledge service (services/knowledge). Callers import only this module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.services.catalogue import facts as catalogue
from socialhood.services.catalogue.facts import ProductFact
from socialhood.services.knowledge import gaps, retrieval
from socialhood.services.knowledge.gaps import normalize_topic
from socialhood.services.knowledge.retrieval import Retrieved as RetrievedChunk

__all__ = [
    "ProductFact",
    "RetrievedChunk",
    "find_products",
    "normalize_topic",
    "open_gap_labels",
    "product_texts",
    "record_knowledge_gap",
    "retrieve_knowledge",
]

PRODUCT_SIMILARITY = 1.0  # a product the model cited is an exact fact: as grounded as it gets


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


async def open_gap_labels(session: AsyncSession, now: datetime) -> list[str]:
    """The workspace's most asked open gap labels (up to 20), so a draft can reuse one exactly
    for the same missing fact (C-034)."""
    return await gaps.open_topics(session, now=now, limit=20)


async def find_products(session: AsyncSession, query: str) -> list[ProductFact]:
    """The catalogue's products the question names (GR-31), as structured facts."""
    return await catalogue.find(session, query)


async def product_texts(session: AsyncSession, product_ids: list[uuid.UUID]) -> list[str]:
    """What a reply may quote from the given products (the ids a suggestion used), for the output
    filter when Auto mode re-checks a stored reply. Ids that aren't products give nothing."""
    return catalogue.texts(await catalogue.facts_for(session, product_ids))
