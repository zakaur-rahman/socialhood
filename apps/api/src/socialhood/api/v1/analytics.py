"""Analytics (§2.15 …/analytics/*; FR-ANL-02, TR-AGT-05; agent-architecture §6 and §11): the
analytics service for the UI, the same functions Ask Amplychat's tools call. Any member.

Figures come from the FR-ANL-01 snapshots; comparisons are at the same age (see
schemas/analytics.py for the conventions and services/analytics for the rules). An unknown or
another workspace's post or account is 404 not_found; a ``since`` after ``until`` is 422.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request

from socialhood.auth.deps import AnyMember, Session, WorkspaceContext
from socialhood.platforms.deps import deps_from
from socialhood.schemas.analytics import (
    AccountMetricName,
    AccountMetrics,
    AgeName,
    BaselineKind,
    MetricName,
    PostComparison,
    PostPerformance,
    SentimentDistribution,
    TopPosts,
)
from socialhood.services.analytics import account_metrics, queries, sentiment
from socialhood.services.analytics.common import View, capabilities_from, date_range

router = APIRouter(prefix="/v1/w/{wid}", tags=["analytics"])


def _view(request: Request, ctx: WorkspaceContext) -> View:
    deps = deps_from(request.app.state.http, request.app.state.settings)
    return View(
        timezone=ctx.workspace.timezone,
        now=datetime.now(UTC),
        capabilities=capabilities_from(deps),
    )


@router.get("/analytics/posts/{post_id}/performance", operation_id="get_post_performance")
async def get_post_performance(
    request: Request,
    post_id: uuid.UUID,
    ctx: AnyMember,
    session: Session,
    age: Annotated[AgeName | None, Query()] = None,
) -> PostPerformance:
    """Reach, views, likes, comments, shares, saves and engagement rate at ``age`` (FR-ANL-02).
    Without ``age``: the latest window the post has reached."""
    return await queries.post_performance(session, _view(request, ctx), post_id, age)


@router.get("/analytics/posts/{post_id}/compare", operation_id="compare_post")
async def compare_post(
    request: Request,
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
    return await queries.compare_post(
        session,
        _view(request, ctx),
        post_id,
        queries.BaselineQuery(
            kind=baseline, n=n, since=since, until=until, same_format=same_format
        ),
        age,
    )


@router.get("/analytics/sentiment", operation_id="get_sentiment_distribution")
async def get_sentiment_distribution(
    request: Request,
    ctx: AnyMember,
    session: Session,
    post_id: Annotated[uuid.UUID | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
) -> SentimentDistribution:
    """Comment sentiment for one post (``post_id``; the range is then ignored), or for comments
    made in the range, optionally on one account's posts."""
    return await sentiment.sentiment_distribution(
        session,
        _view(request, ctx),
        post_id=post_id,
        account_id=account_id,
        since=since,
        until=until,
    )


@router.get("/analytics/top-posts", operation_id="list_top_posts")
async def list_top_posts(
    request: Request,
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
    return await queries.top_posts(
        session,
        _view(request, ctx),
        metric=metric,
        since=since,
        until=until,
        n=n,
        age=age,
        account_id=account_id,
    )


@router.get("/analytics/account-metrics", operation_id="get_account_metrics")
async def get_account_metrics(
    request: Request,
    ctx: AnyMember,
    session: Session,
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    compare: Annotated[Literal["none", "previous"], Query()] = "none",
    metric: Annotated[list[AccountMetricName] | None, Query()] = None,
) -> AccountMetrics:
    """What the account (or every account) did over the range, from its daily readings and the
    comment and message tables; ``compare=previous`` adds the period of the same length just
    before, with the change in % (worked out here). A day without a reading is a gap, not a zero:
    each figure says how many days it has, and is null with the reason when none. Today has no
    reading yet. ``metric`` (repeatable) picks metrics; default all. 404 for another workspace's
    account."""
    view = _view(request, ctx)
    wanted = date_range(view.timezone, view.now, since, until)
    current = account_metrics.span_of(wanted.since, wanted.until)
    previous = (
        account_metrics.span_of(
            current.since - timedelta(days=current.days), current.since - timedelta(days=1)
        )
        if compare == "previous"
        else None
    )
    return await account_metrics.account_metrics(
        session, view, current=current, previous=previous, account_id=account_id, metrics=metric
    )
