"""Post tools (FR-AGT-02, FR-AGT-06, TA.4; agent-architecture.html §5).

R1 (all read; any member, as on the Comments page):
- get_posts(range, format, account): media items with comment stats, newest first, capped;
  stories only when asked for (they take no comments).
- get_latest_post(account, format): the account's most recent post with its age and format.
- search_posts(q, range): posts by caption.

Backed by services/comments/queries.find_posts (the synced media items). Facebook isn't connected
in R1: asking for it returns nothing and says so (FR-AGT-06). Metrics and comparisons are the
analytics tools (tools/analytics.py). No writes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.tools.common import (
    FACEBOOK_NOT_CONNECTED,
    Period,
    clip,
    facebook_asked,
    find_account,
    handle,
    limit_field,
    period,
    post_label,
    post_ref,
    tool,
    when,
)
from socialhood.models.media import MediaItem
from socialhood.schemas.posts import CommentStats
from socialhood.services.analytics.ages import FORMATS, FormatName, format_of
from socialhood.services.comments.queries import find_posts


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stats(BaseModel):
    """The post's comment counts (FR-CMT-03): positive + neutral + negative are analysed
    comments that are not spam."""

    total: int
    analysed: int
    positive: int
    neutral: int
    negative: int
    spam: int


class PostItem(BaseModel):
    id: uuid.UUID
    label: str  # "Reel of 26 Sep"
    format: FormatName  # feed (images, carousels, feed videos), reel or story
    media_type: str
    caption: str | None = None
    posted_at: datetime
    posted_at_label: str | None = None
    age: str  # how long ago it was published, e.g. "26 hours"
    permalink: str | None = None
    likes: int | None = None  # Instagram's count at the last sync or snapshot
    comments: int | None = None
    comment_stats: Stats


def age_words(age: timedelta) -> str:
    """ "45 minutes", "26 hours", "3 days": how old a post is, rounded down."""
    seconds = max(int(age.total_seconds()), 0)
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    if seconds < 48 * 3600:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{seconds // 86400} days"


def post_item(ctx: ToolContext, item: MediaItem) -> PostItem:
    stats = CommentStats.from_stored(item.comment_stats)
    return PostItem(
        id=item.id,
        label=post_label(item, ctx),
        format=format_of(item.media_type),
        media_type=item.media_type,
        caption=clip(item.caption, 160),
        posted_at=item.posted_at,
        posted_at_label=when(ctx, item.posted_at),
        age=age_words(ctx.now - item.posted_at),
        permalink=item.permalink,
        likes=item.like_count,
        comments=item.comments_count,
        comment_stats=Stats(**stats.model_dump()),
    )


class PostsResult(ToolResult):
    period: Period | None = None
    items: list[PostItem]
    total: int
    more: int


PlatformChoice = Literal["instagram", "facebook"]


def _facebook(what: str) -> PostsResult:
    return PostsResult(
        summary=f"Facebook isn't connected, so there are no Facebook {what}",
        items=[],
        total=0,
        more=0,
        caveats=[FACEBOOK_NOT_CONNECTED],
    )


# ---------------------------------------------------------------- get_posts


class GetPostsInput(_Input):
    range: str | None = Field(
        default=None,
        max_length=80,
        description="When they were published, e.g. “last week”; omitted: the newest posts.",
    )
    format: FormatName | None = Field(
        default=None, description="feed (images, carousels, videos), reel or story."
    )
    account: str | None = Field(default=None, max_length=100, description="@handle or id.")
    platform: PlatformChoice | None = None
    limit: int = limit_field()


@tool(
    name="get_posts",
    label="Looking up your posts",
    description=(
        "Published posts, newest first, with their comment counts and sentiment split; "
        "narrowed by when they were published, format (feed, reel, story) and account."
    ),
    input_model=GetPostsInput,
    result_model=PostsResult,
)
async def get_posts(ctx: ToolContext, args: GetPostsInput) -> PostsResult:
    if facebook_asked(args.platform, args.account):
        return _facebook("posts")
    acct = await find_account(ctx, args.account)
    span = period(ctx, args.range, default=None)
    found = await find_posts(
        ctx.session,
        start=span.start if span else None,
        end=span.end if span else None,
        media_types=FORMATS[args.format] if args.format else None,
        account_id=acct.id if acct else None,
        limit=args.limit,
    )
    items = [post_item(ctx, p) for p in found.items]
    noun = {"feed": "feed post", "reel": "reel", "story": "story", None: "post"}[args.format]
    plural = noun if found.total == 1 else ("stories" if noun == "story" else f"{noun}s")
    summary = f"Found {found.total} {plural}"
    if acct:
        summary += f" on {handle(acct)}"
    if span:
        summary += f", {span.label}"
    return PostsResult(
        summary=clip(summary, 300) or "Looked up posts",
        period=Period.of(span) if span else None,
        items=items,
        total=found.total,
        more=max(found.total - len(items), 0),
        refs=[post_ref(p, ctx) for p in found.items],
    )


# ---------------------------------------------------------------- get_latest_post


class GetLatestPostInput(_Input):
    account: str | None = Field(default=None, max_length=100, description="@handle or id.")
    format: FormatName | None = None
    platform: PlatformChoice | None = None


class LatestPostResult(ToolResult):
    post: PostItem | None = None
    account: str | None = None


@tool(
    name="get_latest_post",
    label="Looking up your latest post",
    description=(
        "The most recent post (of an account or format when given), with its age, format, "
        "caption and comment counts. Start here for “my latest post” questions."
    ),
    input_model=GetLatestPostInput,
    result_model=LatestPostResult,
)
async def get_latest_post(ctx: ToolContext, args: GetLatestPostInput) -> LatestPostResult:
    if facebook_asked(args.platform, args.account):
        return LatestPostResult(
            summary="Facebook isn't connected, so there is no Facebook post",
            caveats=[FACEBOOK_NOT_CONNECTED],
        )
    acct = await find_account(ctx, args.account)
    found = await find_posts(
        ctx.session,
        media_types=FORMATS[args.format] if args.format else None,
        account_id=acct.id if acct else None,
        limit=1,
    )
    if not found.items:
        return LatestPostResult(
            summary="No posts found",
            account=handle(acct) if acct else None,
            caveats=["No posts have synced from Instagram yet."],
        )
    item = found.items[0]
    post = post_item(ctx, item)
    return LatestPostResult(
        summary=clip(f"Your latest post is the {post.label}, published {post.age} ago", 300)
        or "Found your latest post",
        post=post,
        account=handle(acct) if acct else None,
        refs=[post_ref(item, ctx)],
    )


# ---------------------------------------------------------------- search_posts


class SearchPostsInput(_Input):
    q: str = Field(min_length=1, max_length=100, description="Words in the caption.")
    range: str | None = Field(default=None, max_length=80)
    account: str | None = Field(default=None, max_length=100)
    limit: int = limit_field()


@tool(
    name="search_posts",
    label="Searching your posts",
    description="Posts whose caption contains the words, newest first.",
    input_model=SearchPostsInput,
    result_model=PostsResult,
)
async def search_posts(ctx: ToolContext, args: SearchPostsInput) -> PostsResult:
    if facebook_asked(args.account):
        return _facebook("posts")
    acct = await find_account(ctx, args.account)
    span = period(ctx, args.range, default=None)
    found = await find_posts(
        ctx.session,
        start=span.start if span else None,
        end=span.end if span else None,
        account_id=acct.id if acct else None,
        q=args.q,
        limit=args.limit,
    )
    items = [post_item(ctx, p) for p in found.items]
    noun = "post" if found.total == 1 else "posts"
    summary = f"Found {found.total} {noun} mentioning “{clip(args.q, 40)}”"
    if span:
        summary += f", {span.label}"
    return PostsResult(
        summary=clip(summary, 300) or "Searched posts",
        period=Period.of(span) if span else None,
        items=items,
        total=found.total,
        more=max(found.total - len(items), 0),
        refs=[post_ref(p, ctx) for p in found.items],
    )
