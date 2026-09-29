"""Posts (synced media items) for the automation post picker (T4.3, UX-SCR-03); the Comments page
builds on this in P6 (comment stats, comments). The query is in services/automations/queries.py.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.automations import PostList
from socialhood.services.automations import queries

router = APIRouter(prefix="/v1/w/{wid}", tags=["posts"])


@router.get("/posts", operation_id="list_posts")
async def list_posts(
    ctx: AnyMember,
    session: Session,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
) -> PostList:
    """Newest first; ``q`` searches captions. Stories are left out (they take no comments)."""
    return await queries.list_posts(session, account_id=account_id, q=q, cursor=cursor, limit=limit)
