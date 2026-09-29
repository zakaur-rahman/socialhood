"""Knowledge retrieval (TR-AI-08): the chunks that may answer a question.

    hits = await retrieve(session, "Do you ship to Dubai?")

The question is embedded as a query (no credits: embeddings are not metered, §1.7), the 8 nearest
chunks of the current workspace's ready sources are found by cosine distance, those with
similarity (1 - distance) below ``AI_RETRIEVAL_MIN_SIM`` are dropped, and at most ``limit`` (6)
are returned, most similar first. Needs a workspace in context (the session's tenant filter).
Raises ``AIError`` when the embedding call fails; callers decide what that means for them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.ai.registry import get_provider
from socialhood.repositories import knowledge as repo
from socialhood.settings import get_settings

CANDIDATES = 8  # nearest chunks considered (TR-AI-08)
MAX_RESULTS = 6  # passed to the model at most
MAX_QUERY_CHARS = 2000


@dataclass(frozen=True)
class Retrieved:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    content: str  # as stored: "[{source title}] " + the chunk text
    similarity: float  # 1 - cosine distance


async def retrieve(
    session: AsyncSession,
    query: str,
    *,
    limit: int = MAX_RESULTS,
    min_similarity: float | None = None,
) -> list[Retrieved]:
    """The most similar chunks for ``query`` (TR-AI-08); [] for an empty query."""
    query = query.strip()[:MAX_QUERY_CHARS]
    if not query or limit <= 0:
        return []
    threshold = get_settings().ai_retrieval_min_sim if min_similarity is None else min_similarity
    [vector] = await get_provider().embed([query], kind="query")
    await repo.allow_iterative_scan(session)
    hits = await repo.nearest_chunks(session, vector, limit=max(CANDIDATES, limit))
    kept = [
        Retrieved(
            chunk_id=hit.chunk_id,
            source_id=hit.source_id,
            source_title=hit.source_title,
            content=hit.content,
            similarity=1.0 - hit.distance,
        )
        for hit in hits
        if 1.0 - hit.distance >= threshold
    ]
    return kept[:limit]
