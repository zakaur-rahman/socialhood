"""Posts (§2.15): the synced posts list for the automation post picker (T4.3, UX-SCR-03) and the
Comments grid (FR-CMT-03), post detail with its summary and topics, and a post's comments
(FR-CMT-04, UX-SCR-05). The list query is in services/automations/queries.py.

The P6 routes below are the contract; T6.3 implements their bodies and removes each
``openapi_extra`` marker so the tenancy suite covers the route.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.posts import CommentFilter, CommentList, PostDetail, PostList
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
    """Newest first; ``q`` searches captions. Stories are left out (they take no comments).
    Each post carries its comment counts and sentiment split (``stats``, FR-CMT-03)."""
    return await queries.list_posts(session, account_id=account_id, q=q, cursor=cursor, limit=limit)


@router.get("/posts/{post_id}", operation_id="get_post", openapi_extra=pending("T6.3"))
async def get_post(post_id: uuid.UUID, ctx: AnyMember, session: Session) -> PostDetail:
    """FR-CMT-04: the post with its counts, sentiment split, summary and topics (at most 6,
    largest first). post.updated carries the same shape when any of them change."""
    raise NotImplementedError("T6.3")


@router.post(
    "/posts/{post_id}/summary",
    status_code=202,
    operation_id="refresh_post_summary",
    openapi_extra=pending("T6.3"),
)
async def refresh_post_summary(post_id: uuid.UUID, ctx: AnyMember, session: Session) -> Response:
    """The summary card's Refresh (UX-SCR-05): queue summarize_post now (TR-AI-11); post.updated
    carries the new summary and topics. 402 quota_exceeded without AI credits; 409 when the post
    has no analysed comments yet."""
    raise NotImplementedError("T6.3")


@router.get(
    "/posts/{post_id}/comments",
    operation_id="list_post_comments",
    openapi_extra=pending("T6.3"),
)
async def list_post_comments(
    post_id: uuid.UUID,
    ctx: AnyMember,
    session: Session,
    comment_filter: Annotated[CommentFilter, Query(alias="filter")] = "all",
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CommentList:
    """The post's comments, newest first, narrowed by one filter chip (UX-SCR-05; the filters are
    defined with ``CommentFilter`` in schemas/posts.py). Deleted comments are left out."""
    raise NotImplementedError("T6.3")
