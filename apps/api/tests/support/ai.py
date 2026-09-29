"""AI test support: every test runs with a FakeProvider (never Gemini); request ``fake_ai`` to
queue responses or read the calls. Factories write P5 rows through the ORM in the workspace's
scope and return their ids."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.ai.fake import FakeProvider, bag_of_words
from socialhood.ai.registry import use_provider
from socialhood.db.tenancy import workspace_scope
from socialhood.models.ai import (
    AiDecision,
    KnowledgeChunk,
    KnowledgeGap,
    KnowledgeSource,
    MessageAnalysis,
    ReplySuggestion,
)


@pytest.fixture(autouse=True)
def fake_ai() -> Iterator[FakeProvider]:
    with use_provider(FakeProvider()) as provider:
        assert isinstance(provider, FakeProvider)
        yield provider


def _wid(workspace_id: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(workspace_id))


async def _add(engine: AsyncEngine, workspace_id: uuid.UUID | str, *rows: Any) -> None:
    with workspace_scope(_wid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all(rows)
            await session.commit()


async def make_analysis(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    **values: Any,
) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "intent": "pricing",
        "sentiment": "neutral",
        "sentiment_score": 0.1,
        "priority": "medium",
        "lead_score": 55,
        "language": "en",
        "topics": ["price"],
        "needs_reply": True,
        "needs_human": False,
        "model": "fake-model",
        "prompt_version": "analysis.v1",
        "input_tokens": 100,
        "output_tokens": 20,
        "latency_ms": 5,
    }
    row = MessageAnalysis(
        conversation_id=conversation_id, message_id=message_id, **{**defaults, **values}
    )
    await _add(engine, workspace_id, row)
    return row.id


async def make_suggestion(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    **values: Any,
) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "status": "pending",
        "can_answer": True,
        "reply_text": "Our prices start at ₹499.",
        "model_confidence": 0.9,
        "model": "fake-model",
        "prompt_version": "suggest.v2",
    }
    row = ReplySuggestion(
        conversation_id=conversation_id, message_id=message_id, **{**defaults, **values}
    )
    await _add(engine, workspace_id, row)
    return row.id


async def make_source(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    question: str = "How much is shipping?",
    body: str = "Shipping is free on orders over ₹999.",
    chunks: bool = True,
    **values: Any,
) -> uuid.UUID:
    """A ready FAQ with its one chunk embedded by the fake's bag of words (like ingestion)."""
    defaults: dict[str, Any] = {
        "type": "faq",
        "title": question,
        "question": question,
        "body": body,
        "status": "ready",
        "char_count": len(question) + len(body),
        "chunk_count": 1 if chunks else 0,
        "last_ingested_at": datetime.now(UTC),
    }
    source = KnowledgeSource(**{**defaults, **values})
    await _add(engine, workspace_id, source)
    if chunks:
        content = f"[{source.title}] Q: {question}\nA: {body}"
        chunk = KnowledgeChunk(
            source_id=source.id,
            source_version=1,
            ordinal=0,
            char_count=len(content),
            content=content,
            embedding=bag_of_words(content),
        )
        await _add(engine, workspace_id, chunk)
    return source.id


async def make_gap(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    topic: str = "shipping to uae",
    **values: Any,
) -> uuid.UUID:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "topic": topic,
        "topic_normalized": topic.casefold(),
        "first_seen_at": now,
        "last_seen_at": now,
    }
    row = KnowledgeGap(**{**defaults, **values})
    await _add(engine, workspace_id, row)
    return row.id


async def make_decision(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    **values: Any,
) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "outcome": "escalated",
        "reason": "out_of_knowledge",
        "checks": [{"n": 9, "name": "can_answer", "passed": False, "value": False}],
    }
    row = AiDecision(
        conversation_id=conversation_id, message_id=message_id, **{**defaults, **values}
    )
    await _add(engine, workspace_id, row)
    return row.id
