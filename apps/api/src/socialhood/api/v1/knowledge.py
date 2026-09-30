"""Knowledge routes (§2.15; T5.3, T5.10): sources, the test box and knowledge gaps. Admins only.

The rules are in services/knowledge/: sources.py (create, edit, delete, the knowledge_characters
limit), answer.py (the test box), gaps.py (questions the AI couldn't answer). A new or edited
source is queued for ingestion right after its transaction commits (FR-KB-02).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.api import ratelimit
from socialhood.auth.deps import Admin, Session
from socialhood.billing.entitlements import credits_gate
from socialhood.schemas.knowledge import (
    KnowledgeGap,
    KnowledgeGapList,
    KnowledgeSource,
    KnowledgeSourceCreate,
    KnowledgeSourceList,
    KnowledgeSourcePatch,
    KnowledgeTest,
    KnowledgeTestResult,
)
from socialhood.services.knowledge import answer, gaps, sources

router = APIRouter(prefix="/v1/w/{wid}", tags=["knowledge"])


@router.get("/knowledge-sources", operation_id="list_knowledge_sources")
async def list_knowledge_sources(ctx: Admin, session: Session) -> KnowledgeSourceList:
    """Every source, newest first, with characters used of the plan's knowledge_characters."""
    return await sources.list_sources(session)


@router.post("/knowledge-sources", status_code=201, operation_id="create_knowledge_source")
async def create_knowledge_source(
    body: KnowledgeSourceCreate, ctx: Admin, session: Session
) -> KnowledgeSource:
    """FR-KB-01: an FAQ (question, body), note (title, body), web page (url) or file
    (file_asset_id). 422 lists missing or foreign fields; 402 quota_exceeded over
    knowledge_characters; 415 for a file that isn't PDF, DOCX, TXT or MD up to 10 MB; 404 for a
    gap_id that isn't this workspace's. Ingestion runs in the background (status pending)."""
    source = await sources.create(session, body, user_id=ctx.user.id)
    out = await sources.view(session, source)
    await session.commit()
    await sources.enqueue_ingest(source)
    return out


@router.get("/knowledge-sources/{source_id}", operation_id="get_knowledge_source")
async def get_knowledge_source(
    source_id: uuid.UUID, ctx: Admin, session: Session
) -> KnowledgeSource:
    return await sources.get(session, source_id)


@router.patch("/knowledge-sources/{source_id}", operation_id="update_knowledge_source")
async def update_knowledge_source(
    source_id: uuid.UUID, body: KnowledgeSourcePatch, ctx: Admin, session: Session
) -> KnowledgeSource:
    """Any change (or ``reingest``) adds 1 to the version and ingests the source again."""
    source, reingest = await sources.update(session, source_id, body)
    out = await sources.view(session, source)
    await session.commit()
    if reingest:
        await sources.enqueue_ingest(source)
    return out


@router.delete(
    "/knowledge-sources/{source_id}", status_code=204, operation_id="delete_knowledge_source"
)
async def delete_knowledge_source(source_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    await sources.delete(session, source_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/knowledge/test", operation_id="test_knowledge", dependencies=[ratelimit.AI])
async def test_knowledge(
    request: Request, body: KnowledgeTest, ctx: Admin, session: Session
) -> KnowledgeTestResult:
    """FR-KB-03: the answer a suggestion would draft, with its sources, or can_answer false
    ("Not in your knowledge"). 1 credit; nothing is stored or sent. 402 quota_exceeded without
    credits; 503 when the AI is unavailable."""
    async with credits_gate(session):  # §2.15 "admin · credits"
        return await answer.try_question(
            session,
            request.app.state.sessionmaker,
            workspace=ctx.workspace,
            question=body.question,
        )


@router.get("/knowledge-gaps", operation_id="list_knowledge_gaps")
async def list_knowledge_gaps(
    ctx: Admin,
    session: Session,
    status: Annotated[str, Query(max_length=16, pattern="^(open|answered|dismissed)$")] = "open",
) -> KnowledgeGapList:
    """Gaps asked in the last 30 days, most asked first, with up to three example messages
    (FR-KB-06, TR-AI-12)."""
    return await gaps.list_gaps(session, status=status, now=datetime.now(UTC))


@router.post("/knowledge-gaps/{gap_id}/dismiss", operation_id="dismiss_knowledge_gap")
async def dismiss_knowledge_gap(gap_id: uuid.UUID, ctx: Admin, session: Session) -> KnowledgeGap:
    """Hidden until a customer asks again (FR-KB-06); 409 conflict once answered."""
    out = await gaps.dismiss(session, gap_id, now=datetime.now(UTC))
    await session.commit()
    return out
