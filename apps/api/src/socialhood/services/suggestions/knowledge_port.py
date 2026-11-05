"""The two knowledge functions suggestions need (TR-AI-08 retrieval, TR-AI-12 gaps), from the
knowledge service (services/knowledge). Callers import only this module."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import any_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import GapStatus, KnowledgeGap
from socialhood.models.inbox import Message
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
# A label names a topic in a few words. It comes from model output, and other customers' drafts read
# it back, so anything longer, or holding contact details, is counted under the fallback topic.
GAP_LABEL_WORDS = 5
GAP_LABEL_CHARS = 40
_NOT_A_LABEL = re.compile(r"\d{5}|\bdot\b")
MIN_GAP_CONVERSATIONS = 2  # a label one conversation made up isn't shown to anyone else


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
    label = normalize_topic(missing_topic)
    if not label:
        return None
    if (
        len(label) > GAP_LABEL_CHARS
        or len(label.split()) > GAP_LABEL_WORDS
        or _NOT_A_LABEL.search(label)
    ):
        missing_topic = gaps.FALLBACK_TOPIC
    gap = await gaps.record_gap(
        session, missing_topic=missing_topic, message_id=message_id, now=now
    )
    return gap.id


async def open_gap_labels(session: AsyncSession, now: datetime) -> list[str]:
    """The workspace's most asked open gap labels (up to 20), so a draft can reuse one exactly
    for the same missing fact (C-034): only those asked in at least two conversations, as drafts
    for other customers read them."""
    conversations = (
        select(func.count(distinct(Message.conversation_id)))
        .where(Message.id == any_(KnowledgeGap.example_message_ids))
        .scalar_subquery()
    )
    return list(
        (
            await session.scalars(
                select(KnowledgeGap.topic_normalized)
                .where(
                    KnowledgeGap.status == GapStatus.OPEN,
                    KnowledgeGap.last_seen_at >= now - gaps.WINDOW,
                    conversations >= MIN_GAP_CONVERSATIONS,
                )
                .order_by(KnowledgeGap.occurrences.desc(), KnowledgeGap.last_seen_at.desc())
                .limit(20)
            )
        ).all()
    )


async def find_products(session: AsyncSession, query: str) -> list[ProductFact]:
    """The catalogue's products the question names (GR-31), as structured facts."""
    return await catalogue.find(session, query)


async def product_texts(session: AsyncSession, product_ids: list[uuid.UUID]) -> list[str]:
    """What a reply may quote from the given products (the ids a suggestion used), for the output
    filter when Auto mode re-checks a stored reply. Ids that aren't products give nothing."""
    return catalogue.texts(await catalogue.facts_for(session, product_ids))
