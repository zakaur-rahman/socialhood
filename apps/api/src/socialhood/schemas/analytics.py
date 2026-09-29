"""Post analytics (§2.15 …/analytics/*; FR-ANL-02, TR-AGT-05; agent-architecture §6 and §11).

The P6 contract: what services/analytics returns to the UI. Ask Social Hood's analytics tools call
the same functions, so these shapes are also what the agent explains (FR-AGT-04: numbers come from
the database, never the model).

Conventions:
- Figures come from post_metric_snapshots (FR-ANL-01), comment analyses and media_items. A value
  that is not known (insights not granted, not collected yet at that age, not given by Instagram
  for the format) is None, never 0 or an estimate.
- Percentages are numbers from 0 to 100 (6.1 means 6.1%).
- Dates are days in the workspace time zone, both ends included. Without ``since`` and ``until``
  a range is the last 30 days.
- Every result states the age it is at and its sample size.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from socialhood.schemas.common import ResponseModel
from socialhood.schemas.posts import PostSummary

# A post's age after publishing: a snapshot window (FR-ANL-01), or "lifetime" (its latest known
# values, whatever its age).
AgeName = Literal["1h", "6h", "24h", "72h", "7d", "30d", "lifetime"]
MetricName = Literal["reach", "views", "likes", "comments", "shares", "saves", "engagement_rate"]
# previous: the account's N posts published before this one; range: its posts in since..until.
BaselineKind = Literal["previous", "range"]

# TR-AGT-05: with fewer comparable posts, a comparison reports "not enough history".
MIN_COMPARABLE_POSTS = 3


class PostMetrics(ResponseModel):
    """FR-ANL-02's figures at one age. ``engagement_rate`` = (likes + comments + shares + saves)
    ÷ reach, as a percentage, at the same age; only when reach is known."""

    reach: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    engagement_rate: float | None = None


class PostPerformance(ResponseModel):
    """GET …/analytics/posts/{post_id}/performance: one post's figures at an age.

    ``age`` is the age the figures are at: the requested one or, when the post is younger, the
    latest window it has reached (``requested_age`` then differs and the UI says so). Without
    ``age`` in the request, the latest window the post has reached is used.
    """

    post_id: uuid.UUID
    media_type: str
    posted_at: datetime
    requested_age: AgeName | None = None
    age: AgeName
    captured_at: datetime | None = None  # when the figures were read; None if never
    insights_granted: bool  # False: the account has not granted insights (likes, comments only)
    insights_final: bool  # the 72 h run has re-read the lagging insight values
    metrics: PostMetrics


class MetricComparison(ResponseModel):
    """One metric of the post against the baseline at the same age."""

    metric: MetricName
    value: float | None = None  # this post
    baseline_median: float | None = None
    baseline_mean: float | None = None
    diff_pct: float | None = None  # (value - median) ÷ median, in %; None without a median > 0
    z_score: float | None = None  # (value - mean) ÷ standard deviation; None without spread
    sample_size: int  # baseline posts that have this metric at this age


class Baseline(ResponseModel):
    """What the post was compared with, as requested and as found."""

    kind: BaselineKind
    n: int | None = None  # previous: how many posts were asked for
    since: date | None = None  # range
    until: date | None = None
    same_format: bool  # Reels against Reels, feed posts against feed posts (the default)
    post_ids: list[uuid.UUID]  # the comparable posts used, newest first


class PostComparison(ResponseModel):
    """GET …/analytics/posts/{post_id}/compare (TR-AGT-05; agent-architecture §6 "Fair
    comparison"): the post against its account's earlier posts at the same age.

    ``age`` is the window compared, chosen as in PostPerformance. Posts published before the
    account was connected have no early snapshots, so they join a baseline only at ages they have:
    ``baseline_size`` counts the posts actually compared. ``enough_history`` is False below
    MIN_COMPARABLE_POSTS; the UI and the agent then say there is not enough history and draw no
    conclusion.
    """

    post: PostPerformance
    age: AgeName
    baseline: Baseline
    baseline_size: int
    enough_history: bool
    metrics: list[MetricComparison]  # in MetricName order


class SentimentDistribution(ResponseModel):
    """GET …/analytics/sentiment: comment sentiment for one post, or for comments made in a date
    range (optionally one account's). Unanalysed comments are counted, not guessed.

    ``positive + neutral + negative`` are analysed comments that are not spam; the percentages
    are shares of that sum (None when it is 0).
    """

    post_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    since: date | None = None  # None for a post
    until: date | None = None
    total: int  # comments in scope, deleted ones left out
    analysed: int
    positive: int
    neutral: int
    negative: int
    spam: int
    positive_pct: float | None = None
    neutral_pct: float | None = None
    negative_pct: float | None = None


class TopPost(ResponseModel):
    post: PostSummary
    value: float  # the metric at ``age``
    age: AgeName  # the age this post's value is at


class TopPosts(ResponseModel):
    """GET …/analytics/top-posts: posts published in the range, ranked by a metric at an age
    (each post at the requested age, or at the latest window it has reached when younger)."""

    metric: MetricName
    requested_age: AgeName
    since: date
    until: date
    considered: int  # posts in the range that have the metric: the sample size
    items: list[TopPost]  # best first
