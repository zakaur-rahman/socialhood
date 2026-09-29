"""Post analytics (T6.5; FR-ANL-02, TR-AGT-05; agent-architecture §6): typed, parameterised reads
of the FR-ANL-01 snapshots, used by the analytics routes and, unchanged, by Ask Social Hood's
analytics tools. The agent never sees tables; numbers come from here (FR-AGT-04).

- ``post_performance``: one post's figures at an age (``ages.shown_age`` picks the snapshot).
- ``compare_post``: the post against its account's previous N posts, or its posts in a date
  range, at the same age and (by default) in the same format; per metric the baseline's median
  and mean, the difference in % and in standard deviations, and the sample size. Fewer than
  MIN_COMPARABLE_POSTS comparable posts: not enough history.
- ``top_posts``: posts published in a range ranked by a metric at an age.

Rules (agent-architecture §6 "Fair comparison"):
- Figures at an age come from that age's snapshot, never from a later reading. A post younger
  than the requested age is shown and compared at its current age, and the result says so
  (``age`` differs from ``requested_age``); no interpolation between snapshots.
- Baseline posts join only at ages they have a snapshot for; ``baseline_size`` counts them.
- Engagement rate = (likes + comments + shares + saves) ÷ reach, in %, at the same age; only
  with reach.
- ``lifetime`` is a post's latest snapshot (or, without any, its live like and comment counts).
- Stories are left out: they take no comments and expire before most windows.
- Date ranges are the workspace's calendar days, both ends included; the default is the last 30
  days. An unknown or another workspace's post or account is 404; ``since`` after ``until`` 422.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, get_args

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.analytics import PostMetricSnapshot
from socialhood.models.media import MediaItem, MediaType
from socialhood.platforms.capabilities import Capability
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.analytics import (
    MIN_COMPARABLE_POSTS,
    AgeName,
    Baseline,
    BaselineKind,
    MetricName,
    PostComparison,
    PostMetrics,
    PostPerformance,
    TopPost,
    TopPosts,
)
from socialhood.schemas.posts import CommentStats, PostSummary
from socialhood.services.analytics import stats
from socialhood.services.analytics.ages import WINDOWS, exact_age, same_format, shown_age
from socialhood.services.analytics.common import View, date_range, load_account, load_post

METRICS: tuple[MetricName, ...] = get_args(MetricName)
MAX_RANGE_POSTS = 500  # a range baseline or ranking reads at most this many posts, newest first


# ---------------------------------------------------------------- figures at an age


@dataclass(frozen=True)
class Figures:
    """A post's known values at one age."""

    age: AgeName
    values: Mapping[str, int] = field(default_factory=dict)
    captured_at: datetime | None = None
    insights_final: bool = False

    def value(self, metric: MetricName) -> float | None:
        if metric == "engagement_rate":
            return stats.engagement_rate(self.values)
        known = self.values.get(metric)
        return float(known) if known is not None else None

    def metrics(self) -> PostMetrics:
        return PostMetrics(
            **{m: self.values.get(m) for m in METRICS if m != "engagement_rate"},
            engagement_rate=stats.engagement_rate(self.values),
        )

    @property
    def known(self) -> bool:
        """Whether any of the analytics metrics is known."""
        return any(self.value(m) is not None for m in METRICS)


Snapshots = Mapping[str, PostMetricSnapshot]


def _ints(raw: Mapping[str, Any] | None) -> dict[str, int]:
    return {k: v for k, v in (raw or {}).items() if isinstance(v, int) and not isinstance(v, bool)}


def figures_at(post: MediaItem, snaps: Snapshots, age: AgeName) -> Figures | None:
    """The post's figures at ``age`` exactly, or None when it has none there."""
    if age == "lifetime":
        latest = next((snaps[w] for w in reversed(WINDOWS) if w in snaps), None)
        if latest is not None:
            return Figures(
                "lifetime", _ints(latest.metrics), latest.captured_at, latest.insights_final
            )
        counts = _ints({"likes": post.like_count, "comments": post.comments_count})
        return Figures("lifetime", counts, post.synced_at) if counts else None
    snap = snaps.get(age)
    if snap is None:
        return None
    return Figures(age, _ints(snap.metrics), snap.captured_at, snap.insights_final)


async def snapshots_for(
    session: AsyncSession, post_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict[str, PostMetricSnapshot]]:
    """Each post's snapshots by window."""
    found: dict[uuid.UUID, dict[str, PostMetricSnapshot]] = defaultdict(dict)
    if post_ids:
        rows = await session.scalars(
            select(PostMetricSnapshot).where(PostMetricSnapshot.media_item_id.in_(post_ids))
        )
        for snap in rows.all():
            found[snap.media_item_id][snap.window] = snap
    return found


def post_summary(item: MediaItem) -> PostSummary:
    return PostSummary(
        id=item.id,
        social_account_id=item.social_account_id,
        platform_media_id=item.platform_media_id,
        media_type=item.media_type,
        caption=item.caption,
        media_url=item.media_url,
        thumbnail_url=item.thumbnail_url,
        permalink=item.permalink,
        posted_at=item.posted_at,
        like_count=item.like_count,
        comments_count=item.comments_count,
        stats=CommentStats.from_stored(item.comment_stats),
    )


# ---------------------------------------------------------------- performance


async def _performance(
    session: AsyncSession,
    view: View,
    post: MediaItem,
    snaps: Snapshots,
    requested: AgeName | None,
) -> tuple[PostPerformance, Figures | None]:
    used = shown_age(post.posted_at, snaps.keys(), requested, view.now)
    found = figures_at(post, snaps, used)
    acct = await accounts.get(session, post.social_account_id)
    granted = acct is not None and Capability.POST_INSIGHTS in view.capabilities(acct)
    performance = PostPerformance(
        post_id=post.id,
        media_type=post.media_type,
        posted_at=post.posted_at,
        requested_age=requested,
        age=used,
        captured_at=found.captured_at if found else None,
        insights_granted=granted,
        insights_final=found.insights_final if found else False,
        metrics=found.metrics() if found else PostMetrics(),
    )
    return performance, found


async def post_performance(
    session: AsyncSession, view: View, post_id: uuid.UUID, age: AgeName | None = None
) -> PostPerformance:
    """Reach, views, likes, comments, shares, saves and engagement rate of one post at ``age``
    (FR-ANL-02): that window's snapshot, the one closest to it when the post has none there, or
    the latest window the post has reached when it is younger (or without ``age``)."""
    post = await load_post(session, post_id)
    snaps = (await snapshots_for(session, [post.id])).get(post.id, {})
    performance, _ = await _performance(session, view, post, snaps, age)
    return performance


# ---------------------------------------------------------------- comparison


@dataclass(frozen=True)
class BaselineQuery:
    """What to compare with: the previous ``n`` posts of the account, or (``range``) its posts
    published ``since``..``until`` (both required), the post itself left out."""

    kind: BaselineKind = "previous"
    n: int = 10
    since: date | None = None
    until: date | None = None
    same_format: bool = True


async def compare_post(
    session: AsyncSession,
    view: View,
    post_id: uuid.UUID,
    baseline: BaselineQuery | None = None,
    age: AgeName | None = None,
) -> PostComparison:
    """The post against its account's earlier posts at the same age (TR-AGT-05)."""
    baseline = baseline or BaselineQuery()
    if baseline.kind == "range" and (baseline.since is None or baseline.until is None):
        raise ApiError(
            "validation_error",
            "A range baseline needs a start and an end date.",
            errors=[FieldError("since", "Pick the dates to compare with.")],
        )
    post = await load_post(session, post_id)
    snaps = (await snapshots_for(session, [post.id])).get(post.id, {})
    performance, found = await _performance(session, view, post, snaps, age)

    statement = select(MediaItem).where(
        MediaItem.social_account_id == post.social_account_id,
        MediaItem.id != post.id,
        MediaItem.media_type != MediaType.STORY,
    )
    if baseline.same_format:
        statement = statement.where(MediaItem.media_type.in_(same_format(post.media_type)))
    order = (MediaItem.posted_at.desc(), MediaItem.id.desc())
    since = until = None
    if baseline.kind == "previous":
        statement = statement.where(MediaItem.posted_at < post.posted_at).limit(baseline.n)
    else:
        span = date_range(view.timezone, view.now, baseline.since, baseline.until)
        since, until = span.since, span.until
        statement = statement.where(
            MediaItem.posted_at >= span.start, MediaItem.posted_at < span.end
        ).limit(MAX_RANGE_POSTS)
    candidates = list((await session.scalars(statement.order_by(*order))).all())
    candidate_snaps = await snapshots_for(session, [c.id for c in candidates])

    compared: list[tuple[MediaItem, Figures]] = []
    for candidate in candidates:
        figures = figures_at(candidate, candidate_snaps.get(candidate.id, {}), performance.age)
        if figures is not None and figures.known:
            compared.append((candidate, figures))
    subject = found or Figures(performance.age)
    comparisons = []
    for metric in METRICS:
        values = [v for _, f in compared if (v := f.value(metric)) is not None]
        comparisons.append(stats.compare(metric, subject.value(metric), values))
    return PostComparison(
        post=performance,
        age=performance.age,
        baseline=Baseline(
            kind=baseline.kind,
            n=baseline.n if baseline.kind == "previous" else None,
            since=since,
            until=until,
            same_format=baseline.same_format,
            post_ids=[c.id for c, _ in compared],
        ),
        baseline_size=len(compared),
        enough_history=len(compared) >= MIN_COMPARABLE_POSTS,
        metrics=comparisons,
    )


# ---------------------------------------------------------------- rankings


async def top_posts(
    session: AsyncSession,
    view: View,
    *,
    metric: MetricName = "reach",
    since: date | None = None,
    until: date | None = None,
    n: int = 5,
    age: AgeName = "lifetime",
    account_id: uuid.UUID | None = None,
) -> TopPosts:
    """Posts published in the range, best first by ``metric`` at ``age`` (each post at that age,
    or at its latest snapshot when younger); posts without the metric there are left out and
    ``considered`` is the sample size. Ties go to the newer post."""
    span = date_range(view.timezone, view.now, since, until)
    statement = select(MediaItem).where(
        MediaItem.posted_at >= span.start,
        MediaItem.posted_at < span.end,
        MediaItem.media_type != MediaType.STORY,
    )
    if account_id is not None:
        await load_account(session, account_id)
        statement = statement.where(MediaItem.social_account_id == account_id)
    posts = list(
        (
            await session.scalars(
                statement.order_by(MediaItem.posted_at.desc()).limit(MAX_RANGE_POSTS)
            )
        ).all()
    )
    snaps = await snapshots_for(session, [p.id for p in posts])
    ranked: list[tuple[float, MediaItem, AgeName]] = []
    for post in posts:
        taken = snaps.get(post.id, {})
        used = exact_age(post.posted_at, taken.keys(), age, view.now)
        figures = figures_at(post, taken, used) if used is not None else None
        value = figures.value(metric) if figures is not None else None
        if value is not None and used is not None:
            ranked.append((value, post, used))
    ranked.sort(key=lambda r: (r[0], r[1].posted_at), reverse=True)
    return TopPosts(
        metric=metric,
        requested_age=age,
        since=span.since,
        until=span.until,
        considered=len(ranked),
        items=[
            TopPost(post=post_summary(post), value=value, age=used)
            for value, post, used in ranked[:n]
        ],
    )
