"""Posts (synced media items) for the automation post picker (T4.3, UX-SCR-03); the Comments page
builds on this in P6 (comment stats, comments).

The signature below is the P4 contract; T4.3 implements the body.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.automations import PostList

router = APIRouter(prefix="/v1/w/{wid}", tags=["posts"])

PENDING = {"x-pending": "T4.3"}


@router.get("/posts", operation_id="list_posts", openapi_extra=PENDING)
async def list_posts(
    ctx: AnyMember,
    session: Session,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
) -> PostList:
    """Newest first; ``q`` searches captions."""
    raise NotImplementedError("T4.3")
