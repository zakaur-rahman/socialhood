"""Publishing reads (01-design.md §4.1): list_scheduled_posts, get_scheduled_post,
get_best_times, list_media. Owners and admins, as the Schedule page (``min_role`` admin).

Captions and media are the workspace's own content, not third-party text.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from socialhood.agent.tools.common import find_account, handle
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import ToolInput, ToolOutput, registry, tool
from socialhood.mcp.tools.common import agent_tool, moment
from socialhood.models.identity import Role
from socialhood.repositories import social_accounts
from socialhood.services.scheduled_posts import best_times, library, posts, slots

ACCOUNT = "A connected account's id or @handle (from list_accounts)."

# ---------------------------------------------------------------- list_scheduled_posts


class ListScheduledPostsInput(ToolInput):
    status: Literal["scheduled", "draft", "published", "failed"] | None = Field(
        default=None,
        description=(
            "scheduled (the default without a period), draft, published or failed (on at least "
            "one account)."
        ),
    )
    period: str | None = Field(
        default=None,
        max_length=80,
        description=(
            "When they publish, in words or dates, read in the workspace's time zone: "
            "“next week”, “2026-11-01 to 2026-11-07”. Omitted: every post still to be published; "
            "for published or failed, the last 30 days."
        ),
    )
    account: str | None = Field(default=None, max_length=100, description=ACCOUNT)
    limit: int = Field(default=20, ge=1, le=25, description="How many to list (at most 25).")


class PostTargetOut(BaseModel):
    account: str
    status: str
    error: str | None = None


class ScheduledPostOut(BaseModel):
    post_id: uuid.UUID
    status: str  # draft, scheduled, publishing, published, partially_published, failed, canceled
    format: str | None = None  # image, video, reel, carousel, story
    caption_start: str | None = None
    publish_at: str | None = None  # local and UTC
    published_at: str | None = None
    accounts: list[PostTargetOut]
    dashboard_url: str | None = None


class ScheduledPostsResult(ToolOutput):
    period: str | None = None
    items: list[ScheduledPostOut]
    total: int
    more: int


@tool(
    registry,
    name="list_scheduled_posts",
    title="List scheduled posts",
    description=(
        "Scheduled, draft, published or failed posts with their time (workspace time and UTC), "
        "format, accounts and each account's status. Without a period: every post still to be "
        "published, soonest first."
    ),
    input_model=ListScheduledPostsInput,
    output_model=ScheduledPostsResult,
    scope="posts:read",
    min_role=Role.ADMIN,
)
async def list_scheduled_posts(
    call: ToolCall, args: ListScheduledPostsInput
) -> ScheduledPostsResult:
    found = await agent_tool(
        call,
        "list_scheduled_posts",
        {"range": args.period, "status": args.status, "account": args.account, "limit": args.limit},
    )
    return ScheduledPostsResult(
        summary=found.summary,
        period=found.period.label if found.period else None,
        items=[
            ScheduledPostOut(
                post_id=i.id,
                status=i.status,
                format=i.format,
                caption_start=i.caption,
                publish_at=moment(call, i.publish_at),
                published_at=moment(call, i.published_at),
                accounts=[
                    PostTargetOut(account=t.account, status=t.status, error=t.error)
                    for t in i.targets
                ],
                dashboard_url=call.dashboard_url(f"schedule/{i.id}"),
            )
            for i in found.items
        ],
        total=found.total,
        more=found.more,
        caveats=found.caveats,
    )


# ---------------------------------------------------------------- get_scheduled_post


class GetScheduledPostInput(ToolInput):
    post_id: uuid.UUID = Field(description="A scheduled post's id (from list_scheduled_posts).")


class AssetOut(BaseModel):
    media_id: uuid.UUID
    type: str  # image, video
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None


class TargetOut(BaseModel):
    account_id: uuid.UUID
    account: str
    status: str
    caption_override: str | None = None
    permalink: str | None = None
    error: str | None = None
    first_comment: str | None = None  # pending, posted, failed


class ChecklistOut(BaseModel):
    key: str
    ok: bool
    message: str
    field: str | None = None


class ScheduledPostDetail(ToolOutput):
    post_id: uuid.UUID
    status: str
    kind: str  # post, story, reel
    format: str | None = None
    caption: str
    first_comment: str | None = None
    collaborators: list[str]
    publish_at: str | None = None
    published_at: str | None = None
    assets: list[AssetOut]
    accounts: list[TargetOut]
    checklist: list[ChecklistOut]
    ready: bool  # every checklist item passes
    dashboard_url: str | None = None


@tool(
    registry,
    name="get_scheduled_post",
    title="Get a scheduled post",
    description=(
        "One scheduled post in full: caption, first comment, collaborators, time, media, each "
        "account's status and link once published, and the composer's checklist (what passes "
        "and what stops it from being scheduled)."
    ),
    input_model=GetScheduledPostInput,
    output_model=ScheduledPostDetail,
    scope="posts:read",
    min_role=Role.ADMIN,
)
async def get_scheduled_post(call: ToolCall, args: GetScheduledPostInput) -> ScheduledPostDetail:
    post = await posts.get(
        call.session,
        args.post_id,
        posts.Env(deps=call.deps, now=call.now, timezone=call.timezone.key),
    )
    accounts = {a.id: a for a in await social_accounts.list_all(call.session)}
    failing = [c for c in post.checklist if not c.ok]
    return ScheduledPostDetail(
        summary=(
            f"A {post.format or post.kind} post, {post.status}"
            + (f", for {moment(call, post.publish_at)}" if post.publish_at else "")
            + (f"; {len(failing)} checklist items to fix" if failing else "")
        ),
        post_id=post.id,
        status=post.status,
        kind=post.kind,
        format=post.format,
        caption=post.caption,
        first_comment=post.first_comment,
        collaborators=post.collaborators,
        publish_at=moment(call, post.publish_at),
        published_at=moment(call, post.published_at),
        assets=[
            AssetOut(
                media_id=a.id,
                type=a.resource_type,
                thumbnail_url=a.thumbnail_url,
                width=a.width,
                height=a.height,
                duration_s=a.duration_s,
            )
            for a in post.assets
        ],
        accounts=[
            TargetOut(
                account_id=t.social_account_id,
                account=(
                    handle(accounts[t.social_account_id])
                    if t.social_account_id in accounts
                    else "a removed account"
                ),
                status=t.status,
                caption_override=t.caption_override,
                permalink=t.permalink,
                error=t.error.message if t.error else None,
                first_comment=t.first_comment.status if t.first_comment else None,
            )
            for t in post.targets
        ],
        checklist=[
            ChecklistOut(key=c.key, ok=c.ok, message=c.message, field=c.field)
            for c in post.checklist
        ],
        ready=post.ready,
        dashboard_url=call.dashboard_url(f"schedule/{post.id}"),
    )


# ---------------------------------------------------------------- get_best_times


class GetBestTimesInput(ToolInput):
    account: str = Field(max_length=100, description=ACCOUNT)


class BestTimeOut(BaseModel):
    weekday: str  # Monday … Sunday
    hour_local: str | None = None  # "18:00", workspace time; None: too little history that day
    posts: int  # posts the suggestion is based on
    lift_percent: int | None = None  # how much better than the account's typical post


class BestTimesResult(ToolOutput):
    account: str
    timezone: str
    enough_history: bool
    sample_size: int
    min_posts: int
    method: str
    days: list[BestTimeOut]
    next_free_slots: list[str]  # the account's next free posting times, local and UTC


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@tool(
    registry,
    name="get_best_times",
    title="Get best posting times",
    description=(
        "Suggested posting hours per weekday for one account, worked out from its own posts' "
        "engagement (not by an AI model), with the sample size, plus its next free posting "
        "times."
    ),
    input_model=GetBestTimesInput,
    output_model=BestTimesResult,
    scope="posts:read",
    min_role=Role.ADMIN,
)
async def get_best_times(call: ToolCall, args: GetBestTimesInput) -> BestTimesResult:
    account = await find_account(call.agent_context(), args.account)
    assert account is not None  # ``account`` is required, so never empty
    found = await best_times.best_times(
        call.session, call.redis, account.id, timezone=call.timezone.key, now=call.now
    )
    free = await slots.next_free(
        call.session, [account.id], timezone=call.timezone.key, now=call.now
    )
    caveats = []
    if not found.enough_history:
        caveats.append(
            f"{handle(account)} has {found.sample_size} posts with known engagement; "
            f"suggestions need {found.min_posts}."
        )
    upcoming = [m for at in free.get(account.id, []) if (m := moment(call, at))]
    if not upcoming:
        caveats.append("This account has no posting times set, so there are no free slots.")
    return BestTimesResult(
        summary=f"Best posting times for {handle(account)} from {found.sample_size} posts",
        account=handle(account),
        timezone=found.timezone,
        enough_history=found.enough_history,
        sample_size=found.sample_size,
        min_posts=found.min_posts,
        method=found.method,
        days=[
            BestTimeOut(
                weekday=WEEKDAYS[d.weekday],
                hour_local=d.local_time.strftime("%H:%M") if d.local_time else None,
                posts=d.posts,
                lift_percent=d.lift_percent,
            )
            for d in found.days
        ],
        next_free_slots=upcoming,
        caveats=caveats,
    )


# ---------------------------------------------------------------- list_media


class ListMediaInput(ToolInput):
    type: Literal["image", "video"] | None = None
    since: date | None = Field(
        default=None, description="Uploaded on or after this day (workspace time zone)."
    )
    until: date | None = Field(default=None, description="Uploaded on or before this day.")
    cursor: str | None = Field(
        default=None, max_length=200, description="next_cursor from the previous page."
    )
    limit: int = Field(default=20, ge=1, le=20, description="How many to list (at most 20).")


class MediaOut(BaseModel):
    media_id: uuid.UUID
    type: str  # image, video
    format: str | None = None  # jpg, png, mp4, …
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    bytes: int
    url: str | None = None
    uploaded_at: str | None = None


class MediaResult(ToolOutput):
    items: list[MediaOut]
    next_cursor: str | None = None


@tool(
    registry,
    name="list_media",
    title="List the media library",
    description=(
        "Images and videos uploaded for posts, newest first, with their media_id (what a post "
        "takes), type, format, size and video length. Pages with next_cursor."
    ),
    input_model=ListMediaInput,
    output_model=MediaResult,
    scope="posts:read",
    min_role=Role.ADMIN,
)
async def list_media(call: ToolCall, args: ListMediaInput) -> MediaResult:
    page = await library.list_library(
        call.session,
        asset_type=args.type,
        since=args.since,
        until=args.until,
        cursor=args.cursor,
        limit=args.limit,
        timezone=call.timezone.key,
    )
    items = [
        MediaOut(
            media_id=a.id,
            type=a.resource_type,
            format=a.format,
            width=a.width,
            height=a.height,
            duration_s=a.duration_s,
            bytes=a.bytes,
            url=a.secure_url,
            uploaded_at=moment(call, a.created_at),
        )
        for a in page.items
    ]
    noun = "file" if len(items) == 1 else "files"
    return MediaResult(
        summary=f"{len(items)} {noun} in the media library"
        + (" (more with next_cursor)" if page.next_cursor else ""),
        items=items,
        next_cursor=page.next_cursor,
    )
