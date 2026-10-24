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
# "23h" is the last reading of an Instagram Story, which is gone after 24 h.
AgeName = Literal["1h", "6h", "23h", "24h", "72h", "7d", "30d", "lifetime"]
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


class ExtraMetrics(ResponseModel):
    """Figures only some posts have, kept apart from ``PostMetrics`` (which every post shares and
    compares): an Instagram Story's replies and its taps and swipes through the Story, and the
    clicks on a Facebook Page post. None: not given for this post or not read yet."""

    replies: int | None = None
    taps_forward: int | None = None
    taps_back: int | None = None
    swipes_forward: int | None = None
    exits: int | None = None  # taps out of the Story
    clicks: int | None = None


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
    # Story replies and taps, Page post clicks (GR-39, GR-30 follow-ups); None for a post that has
    # none of these figures.
    extra_metrics: ExtraMetrics | None = None


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


# ---- account metrics (GR-38): what an account did over a period, from account_daily_metrics
# (insights and followers, one row per account per day) and the comment and message tables.

# Sums over the period's days, except ``followers``, which is the latest reading in the period.
# ``comments`` and ``messages_received`` count rows, so every day is known.
AccountMetricName = Literal[
    "reach",
    "views",
    "accounts_engaged",
    "interactions",
    "followers",
    "follows",
    "unfollows",
    "profile_link_taps",
    "comments",
    "messages_received",
]
# Why a figure is None: the account hasn't granted insights, no day of the period has a reading
# yet, or no Instagram account is connected.
MetricGap = Literal["insights_not_granted", "no_readings", "no_account"]
ChangeDirection = Literal["up", "down", "flat"]


class DaySpan(ResponseModel):
    """Calendar days in the workspace's zone, both included."""

    since: date
    until: date
    days: int


class PeriodFigure(ResponseModel):
    """One metric over one period. ``value`` is None when it isn't known (``unavailable`` says
    why), never 0. With gaps it sums the days that have a reading: ``days_known`` of
    ``days_total``."""

    value: float | None = None
    days_known: int
    days_total: int
    unavailable: MetricGap | None = None


class AccountMetricFigure(ResponseModel):
    """A metric for the period and, when asked, the period before. ``change_pct`` is
    (current - previous) / previous x 100 to one decimal, computed here: None when either side is
    unknown, the previous value is 0, or the periods aren't comparable."""

    metric: AccountMetricName
    current: PeriodFigure
    previous: PeriodFigure | None = None
    change_pct: float | None = None
    direction: ChangeDirection | None = None  # flat under 0.5%; None when either side is unknown


class AccountMetrics(ResponseModel):
    """GET …/analytics/account-metrics: an account's (or every account's) figures for a period,
    optionally against another. ``comparable`` is False when the two periods differ in length: the
    figures are still given, but no change is computed."""

    account_id: uuid.UUID | None = None
    period: DaySpan
    previous_period: DaySpan | None = None
    comparable: bool
    figures: list[AccountMetricFigure]
