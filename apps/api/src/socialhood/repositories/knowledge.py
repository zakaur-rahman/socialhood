"""Knowledge queries (TR-AI-08, TR-AI-12): sources, chunks, nearest-chunk search and gaps.

Selects are filtered to the current workspace by the session event (TR-TEN-02); deletes go
through ``scoped_delete``.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import (
    GapStatus,
    KnowledgeChunk,
    KnowledgeGap,
    KnowledgeSource,
    KnowledgeStatus,
)
from socialhood.models.inbox import Message
from socialhood.models.media import MediaAsset
from socialhood.repositories.base import scoped_delete

# ---------------------------------------------------------------- sources


async def list_sources(session: AsyncSession) -> list[tuple[KnowledgeSource, MediaAsset | None]]:
    """Every source, newest first, with its file's asset when it has one."""
    rows = await session.execute(
        select(KnowledgeSource, MediaAsset)
        .outerjoin(MediaAsset, MediaAsset.id == KnowledgeSource.file_asset_id)
        .order_by(KnowledgeSource.created_at.desc(), KnowledgeSource.id.desc())
    )
    return [(source, asset) for source, asset in rows]


async def get_source(
    session: AsyncSession, source_id: uuid.UUID, *, for_update: bool = False
) -> KnowledgeSource | None:
    statement = select(KnowledgeSource).where(KnowledgeSource.id == source_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return (await session.scalars(statement)).one_or_none()


async def get_asset(session: AsyncSession, asset_id: uuid.UUID | None) -> MediaAsset | None:
    if asset_id is None:
        return None
    return (
        await session.scalars(select(MediaAsset).where(MediaAsset.id == asset_id))
    ).one_or_none()


async def characters_used(session: AsyncSession, *, exclude: uuid.UUID | None = None) -> int:
    """Characters of every source counted against knowledge_characters (§1.7)."""
    statement = select(func.coalesce(func.sum(KnowledgeSource.char_count), 0))
    if exclude is not None:
        statement = statement.where(KnowledgeSource.id != exclude)
    return int(await session.scalar(statement) or 0)


async def any_source(session: AsyncSession) -> bool:
    return (await session.scalar(select(KnowledgeSource.id).limit(1))) is not None


async def delete_source(session: AsyncSession, source_id: uuid.UUID) -> bool:
    result = await session.execute(scoped_delete(KnowledgeSource, id=source_id))
    return int(result.rowcount) > 0  # type: ignore[attr-defined]


async def replace_chunks(
    session: AsyncSession, source_id: uuid.UUID, chunks: Sequence[KnowledgeChunk]
) -> None:
    """The source's chunks become ``chunks``, in the caller's transaction (TR-AI-08)."""
    await session.execute(scoped_delete(KnowledgeChunk, source_id=source_id))
    session.add_all(chunks)
    await session.flush()


# ---------------------------------------------------------------- retrieval


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    content: str
    distance: float


async def allow_iterative_scan(session: AsyncSession) -> None:
    """pgvector >= 0.8: keep scanning the HNSW index until enough rows pass the workspace
    filter (TR-AI-08). SET LOCAL lasts until the transaction ends; older pgvector refuses the
    setting, which is ignored."""
    try:
        async with session.begin_nested():
            await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    except DBAPIError:
        pass


async def nearest_chunks(
    session: AsyncSession, vector: Sequence[float], *, limit: int
) -> list[ChunkHit]:
    """The ``limit`` chunks of ready sources nearest to ``vector`` by cosine distance, nearest
    first (relaxed order is re-sorted here)."""
    distance = KnowledgeChunk.embedding.cosine_distance(list(vector)).label("distance")
    rows = await session.execute(
        select(
            KnowledgeChunk.id,
            KnowledgeChunk.source_id,
            KnowledgeSource.title,
            KnowledgeChunk.content,
            distance,
        )
        .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
        .where(
            KnowledgeSource.status == KnowledgeStatus.READY,
            KnowledgeChunk.source_version == KnowledgeSource.version,
        )
        .order_by(distance)
        .limit(limit)
    )
    hits = [
        ChunkHit(
            chunk_id=row.id,
            source_id=row.source_id,
            source_title=row.title,
            content=row.content,
            distance=float(row.distance),
        )
        for row in rows
    ]
    return sorted(hits, key=lambda hit: hit.distance)


# ---------------------------------------------------------------- gaps


async def gap_matching(
    session: AsyncSession, normalized: str, *, status: GapStatus, min_similarity: float
) -> KnowledgeGap | None:
    """A gap in ``status`` whose topic equals ``normalized``, else the most similar one with
    trigram similarity >= ``min_similarity`` (pg_trgm). Locked for the caller's update."""
    exact = (
        await session.scalars(
            select(KnowledgeGap)
            .where(KnowledgeGap.status == status, KnowledgeGap.topic_normalized == normalized)
            .order_by(KnowledgeGap.last_seen_at.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if exact is not None:
        return exact
    similarity = func.similarity(KnowledgeGap.topic_normalized, normalized)
    return (
        await session.scalars(
            select(KnowledgeGap)
            .where(KnowledgeGap.status == status, similarity >= min_similarity)
            .order_by(similarity.desc(), KnowledgeGap.last_seen_at.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one_or_none()


async def get_gap(
    session: AsyncSession, gap_id: uuid.UUID, *, for_update: bool = False
) -> KnowledgeGap | None:
    statement = select(KnowledgeGap).where(KnowledgeGap.id == gap_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return (await session.scalars(statement)).one_or_none()


async def list_gaps(
    session: AsyncSession, *, status: str, since: datetime, limit: int
) -> list[KnowledgeGap]:
    """Gaps in ``status`` last asked since ``since``, most asked first."""
    return list(
        (
            await session.scalars(
                select(KnowledgeGap)
                .where(KnowledgeGap.status == status, KnowledgeGap.last_seen_at >= since)
                .order_by(
                    KnowledgeGap.occurrences.desc(),
                    KnowledgeGap.last_seen_at.desc(),
                    KnowledgeGap.id,
                )
                .limit(limit)
            )
        ).all()
    )


async def count_open_gaps(session: AsyncSession, *, since: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(KnowledgeGap)
            .where(KnowledgeGap.status == GapStatus.OPEN, KnowledgeGap.last_seen_at >= since)
        )
        or 0
    )


async def open_gap_topics(session: AsyncSession, *, since: datetime, limit: int) -> list[str]:
    """Labels of gaps still unanswered (open or dismissed), most asked first: a dismissed label
    reused by the model reopens its gap (FR-KB-06, C-034)."""
    return list(
        (
            await session.scalars(
                select(KnowledgeGap.topic_normalized)
                .where(
                    KnowledgeGap.status.in_([GapStatus.OPEN, GapStatus.DISMISSED]),
                    KnowledgeGap.last_seen_at >= since,
                )
                .order_by(KnowledgeGap.occurrences.desc(), KnowledgeGap.last_seen_at.desc())
                .limit(limit)
            )
        ).all()
    )


async def messages_by_id(
    session: AsyncSession, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Message]:
    if not ids:
        return {}
    rows = await session.scalars(select(Message).where(Message.id.in_(set(ids))))
    return {message.id: message for message in rows.all()}
