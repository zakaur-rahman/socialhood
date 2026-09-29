"""Knowledge routes (§2.15; T5.3, T5.10): sources, the test box and knowledge gaps. Admins only.

The signatures below are the P5 contract; each task implements its bodies and removes its
``openapi_extra`` marker so the tenancy suite covers the route.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import Admin, Session
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

router = APIRouter(prefix="/v1/w/{wid}", tags=["knowledge"])


@router.get(
    "/knowledge-sources", operation_id="list_knowledge_sources", openapi_extra=pending("T5.3")
)
async def list_knowledge_sources(ctx: Admin, session: Session) -> KnowledgeSourceList:
    raise NotImplementedError("T5.3")


@router.post(
    "/knowledge-sources",
    status_code=201,
    operation_id="create_knowledge_source",
    openapi_extra=pending("T5.3"),
)
async def create_knowledge_source(
    body: KnowledgeSourceCreate, ctx: Admin, session: Session
) -> KnowledgeSource:
    """402 quota_exceeded over knowledge_characters; ingestion runs in the background."""
    raise NotImplementedError("T5.3")


@router.get(
    "/knowledge-sources/{source_id}",
    operation_id="get_knowledge_source",
    openapi_extra=pending("T5.3"),
)
async def get_knowledge_source(
    source_id: uuid.UUID, ctx: Admin, session: Session
) -> KnowledgeSource:
    raise NotImplementedError("T5.3")


@router.patch(
    "/knowledge-sources/{source_id}",
    operation_id="update_knowledge_source",
    openapi_extra=pending("T5.3"),
)
async def update_knowledge_source(
    source_id: uuid.UUID, body: KnowledgeSourcePatch, ctx: Admin, session: Session
) -> KnowledgeSource:
    raise NotImplementedError("T5.3")


@router.delete(
    "/knowledge-sources/{source_id}",
    status_code=204,
    operation_id="delete_knowledge_source",
    openapi_extra=pending("T5.3"),
)
async def delete_knowledge_source(source_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    raise NotImplementedError("T5.3")


@router.post("/knowledge/test", operation_id="test_knowledge", openapi_extra=pending("T5.3"))
async def test_knowledge(body: KnowledgeTest, ctx: Admin, session: Session) -> KnowledgeTestResult:
    """FR-KB-03: 1 credit; nothing is stored or sent."""
    raise NotImplementedError("T5.3")


@router.get("/knowledge-gaps", operation_id="list_knowledge_gaps", openapi_extra=pending("T5.10"))
async def list_knowledge_gaps(
    ctx: Admin,
    session: Session,
    status: Annotated[str, Query(pattern="^(open|answered|dismissed)$")] = "open",
) -> KnowledgeGapList:
    """Open gaps from the last 30 days, most asked first (TR-AI-12)."""
    raise NotImplementedError("T5.10")


@router.post(
    "/knowledge-gaps/{gap_id}/dismiss",
    operation_id="dismiss_knowledge_gap",
    openapi_extra=pending("T5.10"),
)
async def dismiss_knowledge_gap(gap_id: uuid.UUID, ctx: Admin, session: Session) -> KnowledgeGap:
    raise NotImplementedError("T5.10")
