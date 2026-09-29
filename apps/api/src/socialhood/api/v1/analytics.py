"""Analytics (§2.15 …/analytics/*; FR-ANL-02, TR-AGT-05; agent-architecture §6 and §11): the
analytics service for the UI, the same functions Ask Social Hood's tools call. Any member.

Figures come from the FR-ANL-01 snapshots; comparisons are at the same age (see
schemas/analytics.py for the conventions). An unknown or another workspace's post or account is
404 not_found; a ``since`` after ``until`` is 422.

The routes below are the P6 contract; T6.5 implements their bodies and removes each
``openapi_extra`` marker so the tenancy suite covers the route.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.analytics import (
    AgeName,
    BaselineKind,
    MetricName,
    PostComparison,
    PostPerformance,
    SentimentDistribution,
    TopPosts,
)

router = APIRouter(prefix="/v1/w/{wid}", tags=["analytics"])


@router.get(
    "/analytics/posts/{post_id}/performance",
    operation_id="get_post_performance",
    openapi_extra=pending("T6.5"),
)
async def get_post_performance(
    post_id: uuid.UUID,
    ctx: AnyMember,
    session: Session,
    age: Annotated[AgeName | None, Query()] = None,
) -> PostPerformance:
    """Reach, views, likes, comments, shares, saves and engagement rate at ``age`` (FR-ANL-02).
    Without ``age``: the latest window the post has reached."""
    raise NotImplementedError("T6.5")


@router.get(
    "/analytics/posts/{post_id}/compare",
    operation_id="compare_post",
    openapi_extra=pending("T6.5"),
)
async def compare_post(
    post_id: uuid.UUID,
    ctx: AnyMember,
    session: Session,
    baseline: Annotated[BaselineKind, Query()] = "previous",
    n: Annotated[int, Query(ge=3, le=50)] = 10,
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
    age: Annotated[AgeName | None, Query()] = None,
    same_format: Annotated[bool, Query()] = True,
) -> PostComparison:
    """The post against its account's earlier posts at the same age (TR-AGT-05): the previous
    ``n`` posts, or (``baseline=range``, which needs ``since`` and ``until``) the posts published
    in that range, this post left out. ``same_format`` compares Reels with Reels and feed posts
    with feed posts."""
    raise NotImplementedError("T6.5")


@router.get(
    "/analytics/sentiment",
    operation_id="get_sentiment_distribution",
    openapi_extra=pending("T6.5"),
)
async def get_sentiment_distribution(
    ctx: AnyMember,
    session: Session,
    post_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
) -> SentimentDistribution:
    """Comment sentiment for one post (``post_id``; the range is then ignored), or for comments
    made in the range, optionally on one account's posts."""
    raise NotImplementedError("T6.5")


@router.get(
    "/analytics/top-posts",
    operation_id="list_top_posts",
    openapi_extra=pending("T6.5"),
)
async def list_top_posts(
    ctx: AnyMember,
    session: Session,
    metric: Annotated[MetricName, Query()] = "reach",
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
    n: Annotated[int, Query(ge=1, le=20)] = 5,
    age: Annotated[AgeName, Query()] = "lifetime",
    account_id: Annotated[uuid.UUID | None, Query()] = None,
) -> TopPosts:
    """Posts published in the range ranked by ``metric`` at ``age``, best first; posts without
    the metric at that age are left out (``considered`` is the sample size)."""
    raise NotImplementedError("T6.5")
