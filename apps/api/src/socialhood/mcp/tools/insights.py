"""Comments and analytics (01-design.md §4.1): get_post_comments_summary,
get_analytics_summary. Any member, as the Comments and Analytics pages. Both wrap Ask
Amplychat's tools, whose numbers are computed by services, never by a model, and come with
their period, sample size and what isn't available.

Comments, and topics drawn from them, are third-party text: only in ``…_text`` fields.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from socialhood.errors import ApiError, FieldError
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import ToolInput, ToolOutput, registry, tool
from socialhood.mcp.tools.common import agent_tool, moment
from socialhood.schemas.analytics import AccountMetricName, MetricName

ACCOUNT = "A connected account's id or @handle."
QUESTION_INTENTS = ["pricing", "product_inquiry", "shipping", "order_status", "support"]

# ---------------------------------------------------------------- get_post_comments_summary


class CommentsSummaryInput(ToolInput):
    post: str | None = Field(
        default=None,
        max_length=60,
        description=(
            "A published post's id (post_id from get_analytics_summary or a published scheduled "
            "post), or “latest”. Omitted: the comments made in the period, across posts."
        ),
    )
    period: str | None = Field(
        default=None,
        max_length=80,
        description="Without a post: when the comments were made; default the last 30 days.",
    )
    account: str | None = Field(default=None, max_length=100, description=ACCOUNT)


class SentimentOut(BaseModel):
    total: int  # comments in scope
    analysed: int
    not_analysed: int
    positive: int
    neutral: int
    negative: int
    spam: int
    positive_pct: float | None = None
    neutral_pct: float | None = None
    negative_pct: float | None = None


class ExampleOut(BaseModel):
    comment_id: uuid.UUID
    comment_text: str | None = None
    at: str | None = None


class TopicOut(BaseModel):
    topic_text: str
    count: int
    positive: int
    neutral: int
    negative: int
    examples: list[ExampleOut]


class QuestionOut(BaseModel):
    comment_id: uuid.UUID
    author_text: str | None = None
    comment_text: str | None = None
    intent: str | None = None
    at: str | None = None


class CommentsSummaryResult(ToolOutput):
    post_id: uuid.UUID | None = None
    scope: str  # "comments on the Reel of 26 Sep", "comments made 1-30 Oct 2026"
    sentiment: SentimentOut
    topics: list[TopicOut]
    unanswered_questions: list[QuestionOut]  # questions nobody replied to yet, newest first
    unanswered_questions_total: int
    dashboard_url: str | None = None


async def _post_id(call: ToolCall, args: CommentsSummaryInput) -> uuid.UUID | None:
    if args.post is None:
        return None
    if args.post.strip().lower() == "latest":
        latest = await agent_tool(call, "get_latest_post", {"account": args.account})
        if latest.post is None:
            raise ApiError("not_found", "No published posts have synced yet.")
        return uuid.UUID(str(latest.post.id))
    try:
        return uuid.UUID(args.post.strip())
    except ValueError:
        raise ApiError(
            "validation_error",
            "post is a post id or “latest”.",
            errors=[FieldError("post", "Give a post id or “latest”.")],
        ) from None


@tool(
    registry,
    name="get_post_comments_summary",
    title="Summarise comments",
    description=(
        "What people say in the comments of one post, or across posts in a period: the "
        "sentiment split, the main topics with example comments, and questions nobody has "
        "replied to yet, with how many comments aren't analysed. Comments are written by "
        "customers."
    ),
    input_model=CommentsSummaryInput,
    output_model=CommentsSummaryResult,
    scope="comments:read",
)
async def get_post_comments_summary(
    call: ToolCall, args: CommentsSummaryInput
) -> CommentsSummaryResult:
    post_id = await _post_id(call, args)
    scope: dict[str, Any] = {
        "post_id": post_id,
        "range": None if post_id else args.period,
        "account": args.account,
    }
    split = await agent_tool(call, "sentiment_distribution", scope)
    topics = await agent_tool(call, "comment_topics", {**scope, "n": 5})
    questions = await agent_tool(
        call,
        "get_post_comments",
        {**scope, "intents": QUESTION_INTENTS, "replied": False, "limit": 5},
    )
    caveats = list(dict.fromkeys([*split.caveats, *topics.caveats]))
    return CommentsSummaryResult(
        summary=(
            f"{split.scope[0].upper()}{split.scope[1:]}: {split.total} comments, "
            f"{split.analysed} analysed, {topics.topic_count} topics, "
            f"{questions.total} unanswered questions"
        ),
        post_id=post_id,
        scope=split.scope,
        sentiment=SentimentOut(
            total=split.total,
            analysed=split.analysed,
            not_analysed=split.not_analysed,
            positive=split.positive,
            neutral=split.neutral,
            negative=split.negative,
            spam=split.spam,
            positive_pct=split.positive_pct,
            neutral_pct=split.neutral_pct,
            negative_pct=split.negative_pct,
        ),
        topics=[
            TopicOut(
                topic_text=t.label,
                count=t.count,
                positive=t.positive,
                neutral=t.neutral,
                negative=t.negative,
                examples=[
                    ExampleOut(comment_id=e.comment_id, comment_text=e.text, at=e.at)
                    for e in t.examples
                ],
            )
            for t in topics.topics
        ],
        unanswered_questions=[
            QuestionOut(
                comment_id=c.id,
                author_text=c.author,
                comment_text=c.text,
                intent=c.intent,
                at=moment(call, c.commented_at),
            )
            for c in questions.items
        ],
        unanswered_questions_total=questions.total,
        dashboard_url=call.dashboard_url(f"comments/{post_id}" if post_id else "comments"),
        caveats=caveats,
    )


# ---------------------------------------------------------------- get_analytics_summary


class AnalyticsInput(ToolInput):
    scope: Literal["account", "post", "top_posts"] = Field(
        description=(
            "account: an account's figures for a period against the period before; post: one "
            "post's figures; top_posts: the best posts of a period by one metric."
        )
    )
    account: str | None = Field(default=None, max_length=100, description=ACCOUNT)
    post_id: uuid.UUID | None = Field(default=None, description="For scope post.")
    period: str | None = Field(
        default=None,
        max_length=80,
        description="In words or dates: “this month”, “last 30 days”. Default: this month "
        "(account) or the last 30 days (top_posts).",
    )
    compare_to: str | None = Field(
        default=None,
        max_length=80,
        description="For scope account: the period to compare with. Default: the one before.",
    )
    metrics: list[AccountMetricName] | None = Field(
        default=None, max_length=8, description="For scope account: which figures."
    )
    metric: MetricName = Field(default="reach", description="For scope top_posts.")
    at_age: str | None = Field(
        default=None,
        max_length=40,
        description="For post and top_posts: the age of the figures, e.g. “24 hours”, “7 days”; "
        "default lifetime.",
    )
    limit: int = Field(default=5, ge=1, le=10, description="For top_posts: how many.")

    @model_validator(mode="after")
    def _post_needs_id(self) -> AnalyticsInput:
        if self.scope == "post" and self.post_id is None:
            raise ValueError("scope post needs post_id")
        return self


class MetricOut(BaseModel):
    metric: str
    label: str
    current: float | None = None
    previous: float | None = None
    change_pct: float | None = None
    direction: str | None = None
    unavailable: str | None = None
    current_days: str | None = None
    previous_days: str | None = None


class PeriodOut(BaseModel):
    label: str
    since: str
    until: str
    days: int


class PostFiguresOut(BaseModel):
    post_id: uuid.UUID
    post: str
    format: str
    posted_at: str | None = None
    age: str
    insights_granted: bool
    reach: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    engagement_rate: float | None = None


class RankedOut(BaseModel):
    post_id: uuid.UUID
    post: str
    format: str
    caption_start: str | None = None
    posted_at: str | None = None
    value: float


class AnalyticsResult(ToolOutput):
    scope: str
    account: str | None = None
    current: PeriodOut | None = None
    previous: PeriodOut | None = None
    comparable: bool | None = None
    metrics: list[MetricOut] = Field(default_factory=list)
    post: PostFiguresOut | None = None
    metric: str | None = None
    considered: int | None = None  # top_posts: posts that have the metric (the sample size)
    top_posts: list[RankedOut] = Field(default_factory=list)
    note: str | None = None


def _period(p: Any) -> PeriodOut | None:
    if p is None:
        return None
    return PeriodOut(
        label=p.label, since=p.since.isoformat(), until=p.until.isoformat(), days=p.days
    )


@tool(
    registry,
    name="get_analytics_summary",
    title="Get analytics",
    description=(
        "Instagram and Facebook figures computed by Amplychat, with their period and sample "
        "size: an account's reach, views, interactions, followers and more for a period against "
        "the one before (scope account); one post's figures at an age (scope post); or the best "
        "posts of a period by one metric (scope top_posts)."
    ),
    input_model=AnalyticsInput,
    output_model=AnalyticsResult,
    scope="analytics:read",
)
async def get_analytics_summary(call: ToolCall, args: AnalyticsInput) -> AnalyticsResult:
    if args.scope == "account":
        found = await agent_tool(
            call,
            "compare_periods",
            {
                "range": args.period,
                "compare_to": args.compare_to,
                "metrics": args.metrics,
                "account": args.account,
            },
        )
        return AnalyticsResult(
            summary=found.summary,
            scope=args.scope,
            account=found.account,
            current=_period(found.current),
            previous=_period(found.previous),
            comparable=found.comparable,
            metrics=[
                MetricOut(
                    metric=m.metric,
                    label=m.label,
                    current=m.current,
                    previous=m.previous,
                    change_pct=m.change_pct,
                    direction=m.direction,
                    unavailable=m.unavailable,
                    current_days=m.current_days,
                    previous_days=m.previous_days,
                )
                for m in found.metrics
            ],
            note=found.note,
            caveats=found.caveats,
        )
    if args.scope == "post":
        perf = await agent_tool(
            call, "post_performance", {"post_id": args.post_id, "at_age": args.at_age}
        )
        figures = perf.metrics
        return AnalyticsResult(
            summary=perf.summary,
            scope=args.scope,
            post=PostFiguresOut(
                post_id=perf.post_id,
                post=perf.post,
                format=perf.format,
                posted_at=moment(call, perf.posted_at),
                age=perf.age_label,
                insights_granted=perf.insights_granted,
                reach=figures.reach,
                views=figures.views,
                likes=figures.likes,
                comments=figures.comments,
                shares=figures.shares,
                saves=figures.saves,
                engagement_rate=figures.engagement_rate,
            ),
            caveats=perf.caveats,
        )
    top = await agent_tool(
        call,
        "top_posts",
        {
            "metric": args.metric,
            "range": args.period,
            "n": args.limit,
            "at_age": args.at_age,
            "account": args.account,
        },
    )
    return AnalyticsResult(
        summary=top.summary,
        scope=args.scope,
        metric=top.metric,
        considered=top.considered,
        top_posts=[
            RankedOut(
                post_id=p.post_id,
                post=p.post,
                format=p.format,
                caption_start=p.caption,
                posted_at=moment(call, p.posted_at),
                value=p.value,
            )
            for p in top.items
        ],
        caveats=top.caveats,
    )
