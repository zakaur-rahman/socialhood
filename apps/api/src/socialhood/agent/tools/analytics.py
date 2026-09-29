"""Analytics tools (FR-AGT-02, FR-AGT-04, FR-AGT-06, TR-AGT-05, TA.4; agent-architecture.html §6).

Every number comes from services/analytics, the same typed queries the UI uses; the model only
explains them. Results carry the age actually used, the time range and the sample size.

R1 (all read; any member, as the analytics routes):
- post_performance(post_id, at_age): reach, views, likes, comments, shares, saves and engagement
  rate at the snapshot closest to the age (FR-ANL-01), or lifetime; the age used.
- compare_posts(post_id, baseline, n, range, same_format, at_age): the post against the
  baseline's median and mean per metric at the same age; previous N posts or a range, same format
  by default; fewer than 3 comparable posts is "not enough history".
- top_posts(metric, range, n, at_age, account): ranked posts with the metric and the age used.
- sentiment_distribution(post_id | range, account): analysed against total, unanalysed reported.
- comment_topics(post_id | range, sentiment, n): top topics with counts and example comments
  (TR-AI-11 labels; services/analytics/sentiment.comment_topics).

Ages: the member's phrase ("after 24 hours", "at 7 days", "lifetime") goes through
timeparse.resolve_age and is matched to the snapshot windows (1 h, 6 h, 24 h, 72 h, 7 d, 30 d):
another age is compared at the nearest window, and the result says so. Ranges are calendar days
in the workspace's zone (timeparse.calendar_days; default the last 30 days).

Not built: above_average_posts, engagement_trend, account_metrics, sentiment_trend,
compare_sentiment and lead_metrics have no query in services/analytics yet (account insights are
only collected); they come with the analytics that read them.

Without the insights permission a tool returns what it has and a caveat ("insights aren't
granted"); a post younger than the requested age is compared at its current age, and says so.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.timeparse import TimeParseError, resolve_age, span_label
from socialhood.agent.tools.common import (
    FACEBOOK_NOT_CONNECTED,
    Days,
    analytics_view,
    clip,
    days,
    facebook_asked,
    find_account,
    handle,
    limit_field,
    period,
    post_label,
    post_label_of,
    post_ref,
    quoted,
    ref,
    tool,
    when,
)
from socialhood.errors import ApiError, FieldError
from socialhood.models.ai import Sentiment
from socialhood.models.analytics import LIVE_COUNT_WINDOWS, WINDOW_AGES, SnapshotWindow
from socialhood.models.connections import Platform, SocialAccount
from socialhood.platforms.capabilities import Capability
from socialhood.repositories import social_accounts
from socialhood.schemas.analytics import (
    MIN_COMPARABLE_POSTS,
    AgeName,
    BaselineKind,
    MetricName,
    PostPerformance,
)
from socialhood.schemas.posts import SentimentName
from socialhood.services.analytics import queries, sentiment
from socialhood.services.analytics.ages import PROVISIONAL_WINDOWS, format_of
from socialhood.services.analytics.common import capabilities_from, load_post
from socialhood.services.analytics.queries import BaselineQuery

LIFETIME_WORDS = frozenset(
    {"lifetime", "so far", "now", "overall", "total", "all time", "latest", "current", "today"}
)
AGE_WORDS: dict[str, str] = {
    "1h": "1 hour",
    "6h": "6 hours",
    "24h": "24 hours",
    "72h": "72 hours",
    "7d": "7 days",
    "30d": "30 days",
    "lifetime": "lifetime (the latest figures)",
}
INSIGHT_METRICS = frozenset({"reach", "views", "shares", "saves", "engagement_rate"})


def _at_age() -> str | None:
    """The ``at_age`` argument."""
    return Field(
        default=None,
        max_length=40,
        description=(
            "The post's age to read figures at, as the member said it: “24 hours”, “after 7 "
            "days”, “lifetime”. Omitted: the latest age the post has reached."
        ),
    )


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- shared


def snapshot_age(phrase: str | None) -> tuple[AgeName | None, str | None]:
    """The snapshot window for the member's age phrase, and the rule when it isn't one of them
    (nearest window by ratio of ages; the younger one on a tie)."""
    text = " ".join((phrase or "").lower().split())
    if not text:
        return None, None
    if text in LIFETIME_WORDS:
        return "lifetime", None
    try:
        resolved = resolve_age(phrase or "")
    except TimeParseError as error:
        raise ApiError(
            "validation_error", str(error), errors=[FieldError("at_age", str(error))]
        ) from error
    goal = resolved.age.total_seconds()
    window = min(
        WINDOW_AGES,
        key=lambda w: (abs(math.log(WINDOW_AGES[w].total_seconds() / goal)), WINDOW_AGES[w]),
    )
    if WINDOW_AGES[window] == resolved.age:
        return window.value, resolved.rule
    rule = (
        f"figures are recorded at 1 h, 6 h, 24 h, 72 h, 7 d and 30 d, so {resolved.label} is "
        f"read at {AGE_WORDS[window.value]}"
    )
    return window.value, rule


def insights_caveat(acct: SocialAccount | None) -> str:
    who = handle(acct) if acct else "this account"
    return (
        f"Insights aren't granted for {who}, so reach, views, shares, saves and engagement rate "
        "aren't available; likes and comments are."
    )


def _granted(ctx: ToolContext, acct: SocialAccount | None) -> bool:
    return acct is not None and Capability.POST_INSIGHTS in capabilities_from(ctx.platform)(acct)


class Metrics(BaseModel):
    reach: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    engagement_rate: float | None = None  # % of reach, at the same age


def _age_caveats(ctx: ToolContext, perf: PostPerformance, rule: str | None) -> list[str]:
    """Why the figures are at another age than asked, or missing (FR-AGT-06)."""
    caveats = [rule[0].upper() + rule[1:] + "."] if rule else []
    requested = perf.requested_age
    if requested not in (None, "lifetime") and perf.age != requested:
        assert requested is not None
        window = SnapshotWindow(requested)
        if perf.posted_at + WINDOW_AGES[window] > ctx.now:
            caveats.append(
                f"The post is younger than {AGE_WORDS[requested]}, so its figures are at "
                f"{AGE_WORDS[perf.age]}, the latest age it has reached."
            )
        else:
            caveats.append(
                f"No figures were recorded for this post at {AGE_WORDS[requested]} (it may have "
                f"been published before the account was connected), so {AGE_WORDS[perf.age]} "
                "is used."
            )
    if perf.captured_at is None:
        caveats.append(f"No figures have been recorded for this post at {AGE_WORDS[perf.age]} yet.")
    elif perf.age in {w.value for w in LIVE_COUNT_WINDOWS}:
        caveats.append(
            "At 1 and 6 hours only likes and comments are recorded; reach and the other insights "
            "start at 24 hours."
        )
    elif (
        perf.insights_granted
        and not perf.insights_final
        and perf.age in {w.value for w in PROVISIONAL_WINDOWS}
    ):
        caveats.append(
            "Instagram can still update these figures (insights lag up to 48 hours); they are "
            "final from the 72-hour reading."
        )
    return caveats


# ---------------------------------------------------------------- post_performance


class PerformanceInput(_Input):
    post_id: uuid.UUID
    at_age: str | None = _at_age()


class PerformanceResult(ToolResult):
    post_id: uuid.UUID
    post: str  # "Reel of 26 Sep"
    format: str
    posted_at: datetime
    posted_at_label: str | None = None
    requested_age: AgeName | None = None
    age: AgeName  # the age the figures are at
    age_label: str
    captured_at: datetime | None = None
    insights_granted: bool
    insights_final: bool
    metrics: Metrics


@tool(
    name="post_performance",
    label="Reading the post's figures",
    description=(
        "One post's reach, views, likes, comments, shares, saves and engagement rate at an age "
        "after publishing (1 h, 6 h, 24 h, 72 h, 7 d, 30 d, or lifetime)."
    ),
    input_model=PerformanceInput,
    result_model=PerformanceResult,
)
async def post_performance(ctx: ToolContext, args: PerformanceInput) -> PerformanceResult:
    age, rule = snapshot_age(args.at_age)
    item = await load_post(ctx.session, args.post_id)
    view = analytics_view(ctx)
    perf = await queries.post_performance(ctx.session, view, item.id, age)
    acct = await social_accounts.get(ctx.session, item.social_account_id)
    caveats = [] if perf.insights_granted else [insights_caveat(acct)]
    caveats += _age_caveats(ctx, perf, rule)
    label = post_label(item, ctx)
    m = perf.metrics
    shown = ", ".join(
        f"{name} {value:,}" for name, value in (("reach", m.reach), ("likes", m.likes)) if value
    )
    return PerformanceResult(
        summary=clip(f"{label} at {AGE_WORDS[perf.age]}" + (f": {shown}" if shown else ""), 300)
        or label,
        post_id=item.id,
        post=label,
        format=format_of(item.media_type),
        posted_at=item.posted_at,
        posted_at_label=when(ctx, item.posted_at),
        requested_age=perf.requested_age,
        age=perf.age,
        age_label=AGE_WORDS[perf.age],
        captured_at=perf.captured_at,
        insights_granted=perf.insights_granted,
        insights_final=perf.insights_final,
        metrics=Metrics(**m.model_dump()),
        refs=[post_ref(item, ctx)],
        caveats=caveats,
    )


# ---------------------------------------------------------------- compare_posts


class CompareInput(_Input):
    post_id: uuid.UUID
    baseline: BaselineKind = Field(
        default="previous",
        description="previous: the account's N posts before this one; range: its posts "
        "published in a period (“compared with my posts from the last 30 days”), given in "
        "`range`.",
    )
    n: int = Field(default=10, ge=1, le=50, description="How many previous posts.")
    range: str | None = Field(
        default=None,
        max_length=80,
        description="For a range baseline: when those posts were published, e.g. “the last "
        "30 days”.",
    )
    same_format: bool = Field(default=True, description="Reels with reels, feed with feed.")
    at_age: str | None = _at_age()


class Comparison(BaseModel):
    metric: MetricName
    value: float | None = None  # this post
    baseline_median: float | None = None
    baseline_mean: float | None = None
    diff_pct: float | None = None  # against the median, in %
    z_score: float | None = None
    sample_size: int  # baseline posts that have this metric at this age


class BaselineOut(BaseModel):
    kind: BaselineKind
    n: int | None = None
    since: date | None = None
    until: date | None = None
    label: str
    same_format: bool
    size: int  # posts actually compared


class CompareResult(ToolResult):
    post_id: uuid.UUID
    post: str
    age: AgeName
    age_label: str
    baseline: BaselineOut
    enough_history: bool
    metrics: list[Comparison]


@tool(
    name="compare_posts",
    label="Comparing with your earlier posts",
    description=(
        "Compare a post with the account's earlier posts at the same age after publishing: per "
        "metric, the baseline's median and mean, the difference in % and the baseline size. "
        "Baseline: the previous N posts (default 10) or the posts of a period; same format by "
        "default. Fewer than 3 comparable posts means not enough history."
    ),
    input_model=CompareInput,
    result_model=CompareResult,
)
async def compare_posts(ctx: ToolContext, args: CompareInput) -> CompareResult:
    age, rule = snapshot_age(args.at_age)
    item = await load_post(ctx.session, args.post_id)
    since = until = None
    span_rule = None
    if args.baseline == "range":
        span = period(ctx, args.range, default="the last 30 days")
        assert span is not None
        covered = days(ctx, span)
        since, until, span_rule = covered.since, covered.until, covered.rule
    result = await queries.compare_post(
        ctx.session,
        analytics_view(ctx),
        item.id,
        BaselineQuery(
            kind=args.baseline, n=args.n, since=since, until=until, same_format=args.same_format
        ),
        age,
    )
    acct = await social_accounts.get(ctx.session, item.social_account_id)
    label = post_label(item, ctx)
    fmt = format_of(item.media_type)
    kind_words = {"reel": "reels", "feed": "feed posts", "story": "stories"}[fmt]
    posts_word = kind_words if args.same_format else "posts"
    base = result.baseline
    if base.kind == "previous":
        # The baseline is the posts actually compared, not the number asked for.
        size = result.baseline_size
        base_label = (
            f"the previous {args.n} {posts_word}"
            if size == args.n
            else f"the previous {size} {posts_word} (of {args.n} asked for)"
        )
    else:
        assert base.since is not None
        assert base.until is not None
        base_label = f"{posts_word} published {span_label(base.since, base.until)}"
    caveats = [] if result.post.insights_granted else [insights_caveat(acct)]
    if span_rule:
        caveats.append(span_rule[0].upper() + span_rule[1:] + ".")
    caveats += _age_caveats(ctx, result.post, rule)
    if not result.enough_history:
        caveats.append(
            f"Only {result.baseline_size} comparable post{'s' if result.baseline_size != 1 else ''}"
            f" at {AGE_WORDS[result.age]}; at least {MIN_COMPARABLE_POSTS} are needed, so there "
            "isn't enough history to compare."
        )
    reach = next((c for c in result.metrics if c.metric == "reach"), None)
    summary = f"Compared the {label} with {base_label} at {AGE_WORDS[result.age]}"
    if result.enough_history and reach and reach.diff_pct is not None:
        summary += f": reach {reach.diff_pct:+.1f}% against the median"
    elif not result.enough_history:
        summary += ": not enough history"
    return CompareResult(
        summary=clip(summary, 300) or "Compared the post",
        post_id=item.id,
        post=label,
        age=result.age,
        age_label=AGE_WORDS[result.age],
        baseline=BaselineOut(
            kind=base.kind,
            n=base.n,
            since=base.since,
            until=base.until,
            label=base_label,
            same_format=base.same_format,
            size=result.baseline_size,
        ),
        enough_history=result.enough_history,
        metrics=[Comparison(**c.model_dump()) for c in result.metrics],
        refs=[post_ref(item, ctx)],
        caveats=caveats,
    )


# ---------------------------------------------------------------- top_posts


class TopPostsInput(_Input):
    metric: MetricName = "reach"
    range: str | None = Field(
        default=None,
        max_length=80,
        description="When the posts were published; default the last 30 days.",
    )
    n: int = limit_field(default=5, maximum=10)
    at_age: str | None = Field(
        default=None, max_length=40, description="“24 hours”, “7 days”; default lifetime."
    )
    account: str | None = Field(default=None, max_length=100)
    platform: str | None = Field(default=None, max_length=20)


class RankedPost(BaseModel):
    post_id: uuid.UUID
    post: str
    format: str
    caption: str | None = None
    posted_at: datetime
    value: float
    age: AgeName


class TopPostsResult(ToolResult):
    metric: MetricName
    days: Days | None = None
    requested_age: AgeName | None = None
    considered: int  # posts in the range that have the metric: the sample size
    items: list[RankedPost]


@tool(
    name="top_posts",
    label="Ranking your posts",
    description=(
        "The best posts published in a period by one metric (reach, views, likes, comments, "
        "shares, saves or engagement_rate) at an age (default lifetime), with the sample size."
    ),
    input_model=TopPostsInput,
    result_model=TopPostsResult,
)
async def top_posts(ctx: ToolContext, args: TopPostsInput) -> TopPostsResult:
    if facebook_asked(args.platform, args.account):
        return TopPostsResult(
            summary="Facebook isn't connected, so there are no Facebook posts to rank",
            metric=args.metric,
            considered=0,
            items=[],
            caveats=[FACEBOOK_NOT_CONNECTED],
        )
    age, rule = snapshot_age(args.at_age)
    acct = await find_account(ctx, args.account)
    span = period(ctx, args.range, default="the last 30 days")
    assert span is not None
    covered = days(ctx, span)
    ranked = await queries.top_posts(
        ctx.session,
        analytics_view(ctx),
        metric=args.metric,
        since=covered.since,
        until=covered.until,
        n=args.n,
        age=age or "lifetime",
        account_id=acct.id if acct else None,
    )
    items = []
    refs = []
    for top in ranked.items:
        post = top.post
        fmt = format_of(post.media_type)
        label = post_label_of(post.media_type, post.posted_at, ctx)
        items.append(
            RankedPost(
                post_id=post.id,
                post=label,
                format=fmt,
                caption=clip(post.caption, 120),
                posted_at=post.posted_at,
                value=top.value,
                age=top.age,
            )
        )
        refs.append(ref("post", post.id, label))
    caveats = [rule[0].upper() + rule[1:] + "."] if rule else []
    if covered.rule:
        caveats.append(covered.rule[0].upper() + covered.rule[1:] + ".")
    if args.metric in INSIGHT_METRICS:
        # Accounts that publish posts: a WhatsApp number has no posts, so no insights to grant.
        accounts = [acct] if acct else await social_accounts.list_all(ctx.session)
        missing = [a for a in accounts if a.platform == Platform.INSTAGRAM and not _granted(ctx, a)]
        caveats += [insights_caveat(a) for a in missing]
    if not ranked.considered:
        caveats.append(f"No post published {covered.label} has {args.metric} at that age.")
    metric = args.metric.replace("_", " ")
    return TopPostsResult(
        summary=clip(f"Ranked {ranked.considered} posts published {covered.label} by {metric}", 300)
        or "Ranked posts",
        metric=args.metric,
        days=covered,
        requested_age=ranked.requested_age,
        considered=ranked.considered,
        items=items,
        refs=refs,
        caveats=caveats,
    )


# ---------------------------------------------------------------- sentiment_distribution


class ScopeInput(_Input):
    post_id: uuid.UUID | None = Field(
        default=None, description="One post; omitted: comments made in the range."
    )
    range: str | None = Field(
        default=None,
        max_length=80,
        description="When the comments were made (without a post); default the last 30 days.",
    )
    account: str | None = Field(default=None, max_length=100)
    platform: str | None = Field(default=None, max_length=20)


class SentimentResult(ToolResult):
    post_id: uuid.UUID | None = None
    scope: str  # "comments on the Reel of 26 Sep" or "comments made 1-30 Sep 2026"
    days: Days | None = None
    total: int  # comments in scope
    analysed: int
    not_analysed: int
    positive: int
    neutral: int
    negative: int
    spam: int
    positive_pct: float | None = None  # shares of positive + neutral + negative (spam apart)
    neutral_pct: float | None = None
    negative_pct: float | None = None
    positive_share: float | None = None  # positive_pct as 0..1, for plan conditions


async def _comment_scope(
    ctx: ToolContext, args: ScopeInput
) -> tuple[str, Days | None, SocialAccount | None, list[str]]:
    acct = await find_account(ctx, args.account)
    if args.post_id is not None:
        item = await load_post(ctx.session, args.post_id)
        return f"comments on the {post_label(item, ctx)}", None, acct, []
    span = period(ctx, args.range, default="the last 30 days")
    assert span is not None
    covered = days(ctx, span)
    rules = [covered.rule[0].upper() + covered.rule[1:] + "."] if covered.rule else []
    where = f" on {handle(acct)}" if acct else ""
    return f"comments made {covered.label}{where}", covered, acct, rules


@tool(
    name="sentiment_distribution",
    label="Measuring comment sentiment",
    description=(
        "How many comments are positive, neutral and negative (spam apart), for one post or the "
        "comments made in a period, with how many are analysed of the total."
    ),
    input_model=ScopeInput,
    result_model=SentimentResult,
)
async def sentiment_distribution(ctx: ToolContext, args: ScopeInput) -> SentimentResult:
    if facebook_asked(args.platform, args.account):
        return SentimentResult(
            summary="Facebook isn't connected, so there are no Facebook comments",
            scope="Facebook",
            total=0,
            analysed=0,
            not_analysed=0,
            positive=0,
            neutral=0,
            negative=0,
            spam=0,
            caveats=[FACEBOOK_NOT_CONNECTED],
        )
    scope, covered, acct, caveats = await _comment_scope(ctx, args)
    dist = await sentiment.sentiment_distribution(
        ctx.session,
        analytics_view(ctx),
        post_id=args.post_id,
        account_id=acct.id if acct else None,
        since=covered.since if covered else None,
        until=covered.until if covered else None,
    )
    missing = dist.total - dist.analysed
    if not dist.total:
        caveats.append(f"There are no {scope}.")
    elif missing:
        caveats.append(
            f"{missing} of {dist.total} comments aren't analysed yet (still being analysed, or "
            "analysis is off), so they aren't in the percentages."
        )
    refs = []
    if args.post_id is not None:
        refs.append(post_ref(await load_post(ctx.session, args.post_id), ctx))
    summary = f"{scope[0].upper()}{scope[1:]}: {dist.analysed} of {dist.total} analysed"
    if dist.positive_pct is not None:
        summary += (
            f": {dist.positive_pct:g}% positive, {dist.neutral_pct:g}% neutral, "
            f"{dist.negative_pct:g}% negative"
        )
    return SentimentResult(
        summary=clip(summary, 300) or "Measured sentiment",
        post_id=args.post_id,
        scope=scope,
        days=covered,
        total=dist.total,
        analysed=dist.analysed,
        not_analysed=missing,
        positive=dist.positive,
        neutral=dist.neutral,
        negative=dist.negative,
        spam=dist.spam,
        positive_pct=dist.positive_pct,
        neutral_pct=dist.neutral_pct,
        negative_pct=dist.negative_pct,
        positive_share=(
            round(dist.positive_pct / 100, 3) if dist.positive_pct is not None else None
        ),
        refs=refs,
        caveats=caveats,
    )


# ---------------------------------------------------------------- comment_topics


class TopicsInput(ScopeInput):
    sentiment: SentimentName | None = Field(
        default=None, description="Only comments with this sentiment, e.g. negative."
    )
    n: int = limit_field(default=5, maximum=10)


class TopicExampleOut(BaseModel):
    comment_id: uuid.UUID
    text: str | None = None
    at: str | None = None


class TopicOut(BaseModel):
    label: str
    count: int
    positive: int
    neutral: int
    negative: int
    examples: list[TopicExampleOut]


class TopicsResult(ToolResult):
    post_id: uuid.UUID | None = None
    scope: str
    days: Days | None = None
    sentiment: SentimentName | None = None
    topics: list[TopicOut]
    topic_count: int  # distinct topics
    analysed: int  # analysed comments (not spam) in scope with this sentiment
    total: int  # every comment in scope
    pending: int
    skipped: int


@tool(
    name="comment_topics",
    label="Finding what people talk about",
    description=(
        "The most frequent comment topics (analysed, not spam) for one post or the comments of a "
        "period, optionally of one sentiment, with counts per sentiment and three example "
        "comments each."
    ),
    input_model=TopicsInput,
    result_model=TopicsResult,
)
async def comment_topics(ctx: ToolContext, args: TopicsInput) -> TopicsResult:
    if facebook_asked(args.platform, args.account):
        return TopicsResult(
            summary="Facebook isn't connected, so there are no Facebook comments",
            scope="Facebook",
            topics=[],
            topic_count=0,
            analysed=0,
            total=0,
            pending=0,
            skipped=0,
            caveats=[FACEBOOK_NOT_CONNECTED],
        )
    scope, covered, acct, caveats = await _comment_scope(ctx, args)
    found = await sentiment.comment_topics(
        ctx.session,
        analytics_view(ctx),
        post_id=args.post_id,
        account_id=acct.id if acct else None,
        since=covered.since if covered else None,
        until=covered.until if covered else None,
        sentiment=Sentiment(args.sentiment) if args.sentiment else None,
        n=args.n,
    )
    if found.pending:
        caveats.append(
            f"{found.pending} of {found.total} comments are still being analysed, so they aren't "
            "counted."
        )
    if found.skipped:
        caveats.append(f"{found.skipped} comments weren't analysed, so they aren't counted.")
    if not found.analysed:
        caveats.append(f"There are no analysed {scope}.")
    refs = []
    if args.post_id is not None:
        refs.append(post_ref(await load_post(ctx.session, args.post_id), ctx))
    topics = []
    for t in found.topics:
        topics.append(
            TopicOut(
                label=t.label,
                count=t.count,
                positive=t.positive,
                neutral=t.neutral,
                negative=t.negative,
                examples=[
                    TopicExampleOut(
                        comment_id=e.comment_id,
                        text=clip(e.text, 200),
                        at=when(ctx, e.commented_at),
                    )
                    for e in t.examples
                ],
            )
        )
        refs += [ref("comment", e.comment_id, quoted(e.text), e.post_id) for e in t.examples]
    mood = f"{args.sentiment} " if args.sentiment else ""
    top = ", ".join(f"“{t.label}” {t.count}" for t in topics[:3])
    summary = f"{found.topic_count} topics in {found.analysed} analysed {mood}{scope}"
    if top:
        summary += f": {top}"
    return TopicsResult(
        summary=clip(summary, 300) or "Counted topics",
        post_id=args.post_id,
        scope=scope,
        days=covered,
        sentiment=args.sentiment,
        topics=topics,
        topic_count=found.topic_count,
        analysed=found.analysed,
        total=found.total,
        pending=found.pending,
        skipped=found.skipped,
        refs=refs,
        caveats=caveats,
    )
