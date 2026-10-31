"""Publishing writes (01-design.md §4.1, §4.4): create_post, update_post, cancel_post.

Posts go directly, as the member's own action (decision D3), with these safety nets:

- **Confirmation.** A call that would schedule, change or cancel a scheduled post does nothing
  until it is repeated with ``confirmed: true``. Without it the result is a preview (``preview``
  true, nothing stored): the resolved time in the workspace's zone and UTC, the accounts, and
  the composer's checklist, so a wrong time-zone guess or a failing item shows before anything
  is scheduled. Saving a draft needs no confirmation.
- **Five minutes ahead at least** (``MIN_SCHEDULE_LEAD``): AI apps cannot publish now, so a team
  member always has a window to see a post and cancel it.
- **The team is told.** Owners and admins get a notification naming the AI app and the member,
  with a link to the post (where it is cancelled).
- **Free saves drafts only.** The workspace's mode and the plan decide (``require_scheduling``);
  Free gets ``entitlement_required``, a workspace set to "read and drafts" a plain refusal.
- **A daily cap** on posts scheduled (``mcp_posts_daily``).

Everything else is the app's own rules: the same services as the composer
(``services/scheduled_posts``), so the checklist, the account and media checks, the monthly
quota (``scheduled_posts_monthly``) and the format rules are not repeated here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from socialhood.agent.timeparse import TimeParseError, resolve_instant
from socialhood.agent.tools.common import find_account, handle
from socialhood.billing.entitlements import entitlement_error
from socialhood.errors import ApiError, FieldError
from socialhood.mcp import limits
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import Access, ToolInput, WriteInput, WriteOutput, registry, tool
from socialhood.mcp.tools.common import moment
from socialhood.mcp.tools.posts import ACCOUNT, ChecklistOut
from socialhood.models.identity import Role, User
from socialhood.models.mcp import AiConnectionsMode
from socialhood.models.notifications import NotificationType, Severity
from socialhood.models.publishing import (
    COLLABORATORS_MAX,
    FIRST_COMMENT_MAX_CHARS,
    MIN_SCHEDULE_LEAD,
    STORED_CAPTION_MAX_CHARS,
    PostFormat,
)
from socialhood.realtime import events
from socialhood.repositories import social_accounts
from socialhood.schemas.publishing import (
    ScheduledPost,
    ScheduledPostDraft,
    TargetIn,
    UserTagIn,
)
from socialhood.services import notifications
from socialhood.services.scheduled_posts import posts, rules

WHEN = (
    "When to publish: a date and time (2026-11-07T18:00:00+05:30, or 2026-11-07 18:00 in the "
    "workspace's time zone, or words like “tomorrow 7 pm”), “next_free_slot” for the earliest "
    "free posting time of the accounts, or “draft” to save it without a time. At least 5 "
    "minutes from now."
)
CONFIRMED = (
    "false (the default): nothing changes and the result shows what would happen. true: do it. "
    "Send true only after the member has seen the preview."
)
KIND = (
    "post: an image, a video (published as a Reel on Instagram) or a carousel; reel: one video "
    "as a Reel; story: one image or video as a Story, without caption."
)
DRAFT, SLOT, SCHEDULED = "draft", "next_free_slot", "scheduled"
TOO_SOON = (
    "AI apps schedule at least 5 minutes ahead, so the team can see a post before it goes out. "
    "Pick a later time, or use “draft”."
)
Kind = Literal["post", "reel", "story"]


class ReelOptions(BaseModel):
    cover_media_id: uuid.UUID | None = Field(
        default=None, description="An uploaded image to use as the Reel's cover."
    )
    cover_offset_ms: int | None = Field(
        default=None, ge=0, le=900_000, description="Or a frame of the video, in milliseconds."
    )
    share_to_feed: bool = Field(default=True, description="Also show the Reel in the feed.")
    audio_name: str | None = Field(default=None, max_length=60, description="The audio's name.")


class PostFields(ToolInput):
    """What describes a post, on create and on update."""

    media_ids: list[uuid.UUID] | None = Field(
        default=None,
        max_length=10,
        description="media_ids from the media library, in order (carousel order). 2 to 10 make a "
        "carousel.",
    )
    caption: str | None = Field(default=None, max_length=STORED_CAPTION_MAX_CHARS)
    first_comment: str | None = Field(
        default=None,
        max_length=FIRST_COMMENT_MAX_CHARS,
        description="Posted as a comment right after the post publishes.",
    )
    collaborators: list[str] | None = Field(
        default=None,
        max_length=COLLABORATORS_MAX,
        description=f"Instagram usernames to invite, at most {COLLABORATORS_MAX}.",
    )
    location: str | None = Field(
        default=None, max_length=300, description="A Facebook Page id or its link."
    )
    reel_options: ReelOptions | None = None
    per_account_captions: dict[str, str] | None = Field(
        default=None,
        description="A caption for one account instead of the main one, by account id or @handle.",
    )


class CreatePostInput(PostFields, WriteInput):
    accounts: list[str] = Field(min_length=1, max_length=10, description=ACCOUNT)
    kind: Kind = Field(default="post", description=KIND)
    when: str = Field(min_length=1, max_length=100, description=WHEN)
    confirmed: bool = Field(default=False, description=CONFIRMED)


class UpdatePostInput(PostFields, WriteInput):
    post_id: uuid.UUID = Field(description="A draft or scheduled post's id.")
    accounts: list[str] | None = Field(
        default=None, min_length=1, max_length=10, description=ACCOUNT
    )
    kind: Kind | None = Field(default=None, description=KIND)
    when: str | None = Field(
        default=None,
        max_length=100,
        description="A new time (the same forms as create_post) or “next_free_slot”. A draft "
        "given a time is scheduled. Omit to keep the time.",
    )
    confirmed: bool = Field(default=False, description=CONFIRMED)


class CancelPostInput(WriteInput):
    post_id: uuid.UUID = Field(description="A scheduled post's id.")
    confirmed: bool = Field(default=False, description=CONFIRMED)


class PostResult(WriteOutput):
    post_id: uuid.UUID | None = None  # None in a preview of a post not yet created
    status: str  # draft, scheduled, … (what it would be, in a preview)
    kind: str
    format: str | None = None  # image, video, reel, carousel, story
    caption: str
    first_comment: str | None = None
    collaborators: list[str]
    accounts: list[str]
    media_ids: list[uuid.UUID]
    publish_at: str | None = None  # workspace time and UTC
    checklist: list[ChecklistOut]
    ready: bool  # every checklist item passes
    next_step: str
    dashboard_url: str | None = None


# ---------------------------------------------------------------- shared rules


def _when_error(message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError("when", message)])


def resolve_when(call: ToolCall, when: str) -> datetime | Literal["draft", "slot"]:
    """``when`` as a UTC time, or ``draft`` or ``slot``. A time without an offset is read in the
    workspace's zone; a phrase goes through the same resolver as Ask. Under 5 minutes ahead is a
    field error on ``when``."""
    text = when.strip()
    if text.casefold() == DRAFT:
        return "draft"
    if text.casefold() in (SLOT, "next free slot", "queue"):
        return "slot"
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            at = resolve_instant(text, now=call.now, tz=call.timezone).at
        except TimeParseError as error:
            raise _when_error(str(error)) from error
    if at.tzinfo is None:
        at = at.replace(tzinfo=call.timezone)
    at = at.astimezone(UTC)
    if at < call.now + MIN_SCHEDULE_LEAD:
        raise _when_error(TOO_SOON)
    return at


def require_scheduling(call: ToolCall) -> None:
    """Scheduling or changing a scheduled post needs the ``full`` mode: Free is capped at drafts
    by its plan (402), a workspace set to drafts refuses in plain words."""
    if call.mode is AiConnectionsMode.FULL:
        return
    if call.workspace.ai_connections_mode == AiConnectionsMode.FULL:  # the plan holds it back
        raise entitlement_error("ai_connections")
    raise ApiError(
        "forbidden",
        "This workspace lets AI apps only read and prepare drafts. An owner or admin can change "
        "that in Amplychat, under Settings. Saving the post as a draft works.",
    )


async def _accounts(call: ToolCall, names: list[str]) -> list[uuid.UUID]:
    ctx = call.agent_context()
    found: list[uuid.UUID] = []
    for name in names:
        account = await find_account(ctx, name)
        assert account is not None  # the input refuses an empty name
        found.append(account.id)
    return found


async def _captions(call: ToolCall, by_account: dict[str, str] | None) -> dict[uuid.UUID, str]:
    if not by_account:
        return {}
    ids = await _accounts(call, list(by_account))
    return dict(zip(ids, by_account.values(), strict=True))


def _post_kind(kind: Kind, platforms: set[str]) -> Literal["post", "reel", "story"]:
    """Instagram publishes a single video as a Reel already; ``reel`` is a Facebook Reel only
    when a Page is a target (rules.REEL_NEEDS_PAGE)."""
    if kind == "reel" and "facebook" not in platforms:
        return "post"
    return kind


async def _platforms(session: AsyncSession, ids: list[uuid.UUID]) -> set[str]:
    return {a.platform for a in await social_accounts.list_all(session) if a.id in ids}


async def _result(
    call: ToolCall,
    post: ScheduledPost,
    *,
    preview: bool,
    summary: str,
    next_step: str,
    stored: bool = True,
) -> PostResult:
    names = {a.id: handle(a) for a in await social_accounts.list_all(call.session)}
    return PostResult(
        summary=summary,
        preview=preview,
        post_id=post.id if stored else None,
        status=post.status,
        kind=post.kind,
        format=post.format,
        caption=post.caption,
        first_comment=post.first_comment,
        collaborators=post.collaborators,
        accounts=[names.get(t.social_account_id, "a removed account") for t in post.targets],
        media_ids=[a.id for a in post.assets],
        publish_at=moment(call, post.publish_at),
        checklist=[
            ChecklistOut(key=c.key, ok=c.ok, message=c.message, field=c.field)
            for c in post.checklist
        ],
        ready=post.ready,
        next_step=next_step,
        dashboard_url=call.dashboard_url(f"schedule/{post.id}") if stored else None,
    )


def _env(call: ToolCall) -> posts.Env:
    return posts.Env(deps=call.deps, now=call.now, timezone=call.timezone.key)


async def _notify(call: ToolCall, post: ScheduledPost, did: str) -> None:
    """Tell the owners and admins that an AI app scheduled, changed or cancelled a post, who
    asked, and where to cancel it (§4.4)."""
    user = await call.session.get(User, call.principal.user_id)
    who = (user.name or user.email) if user is not None else "A member"
    app = call.client_name or "An AI app"
    what = (
        rules.format_label(PostFormat(post.format), len(post.assets)).lower()
        if post.format
        else "post"
    )
    when = moment(call, post.publish_at)
    title = f"{app} {did} {'an' if what[0] in 'aeiou' else 'a'} {what}" + (
        f" for {when}" if when and did != "cancelled" else ""
    )
    link = f"/schedule/{post.id}"
    at = post.publish_at.isoformat() if post.publish_at else ""
    await notifications.notify_admins(
        call.session,
        type=NotificationType.AI_POST_CHANGE.value,
        severity=Severity.INFO.value,
        title=title[:200],
        body=f"{who} asked {app} to do this. Open the post to review or cancel it before it "
        "publishes.",
        link=link,
        dedupe_key=f"mcp-post:{post.id}:{did}:{at}",
    )


def _confirm_step(preview: bool, then: str) -> str:
    return (
        f"Nothing was changed. Show the member this, then call again with confirmed: true to "
        f"{then}."
        if preview
        else ""
    )


async def _preview_end(call: ToolCall, savepoint: AsyncSessionTransaction) -> None:
    """End a preview: everything the call wrote is rolled back, and the events it queued are
    dropped."""
    await savepoint.rollback()
    events.discard(call.session)


# ---------------------------------------------------------------- create_post


@tool(
    registry,
    name="create_post",
    title="Create or schedule a post",
    description=(
        "Create an Instagram or Facebook post, carousel, Reel or Story from media in the "
        "library, and either save it as a draft, schedule it for a time, or put it in the next "
        "free posting slot. It is checked with the same checklist as the composer, and a failing "
        "item stops scheduling. Scheduling is previewed first: the call shows the resolved time "
        "and the checklist, and a second call with confirmed true schedules it. Posts go out at "
        "least 5 minutes later and the team is notified. Plans: scheduling is part of Pro; "
        "drafts work on every plan."
    ),
    input_model=CreatePostInput,
    output_model=PostResult,
    scope="posts:write",
    access=Access.DRAFT,
    min_role=Role.ADMIN,
    open_world=True,
    dedupe_window_s=600,
)
async def create_post(call: ToolCall, args: CreatePostInput) -> PostResult:
    when = resolve_when(call, args.when)
    scheduling = when != "draft"
    if scheduling:
        require_scheduling(call)
    ids = await _accounts(call, args.accounts)
    platforms = await _platforms(call.session, ids)
    captions = await _captions(call, args.per_account_captions)
    options = args.reel_options or ReelOptions()
    draft = ScheduledPostDraft(
        targets=[TargetIn(social_account_id=i, caption_override=captions.get(i)) for i in ids],
        asset_ids=args.media_ids or [],
        caption=args.caption or "",
        first_comment=args.first_comment,
        kind=_post_kind(args.kind, platforms),
        collaborators=args.collaborators or [],
        location=args.location,
        cover_asset_id=options.cover_media_id,
        cover_offset_ms=options.cover_offset_ms,
        share_to_feed=options.share_to_feed,
        audio_name=options.audio_name,
    )
    preview = scheduling and not args.confirmed
    reservation = None
    if scheduling and not preview:
        reservation = await limits.reserve(
            call.redis,
            call.plan,
            limits.POSTS,
            call.workspace.id,
            call.now,
        )
    savepoint = await call.session.begin_nested() if preview else None
    try:
        post = await posts.create(call.session, draft, _env(call), user_id=call.principal.user_id)
        if args.kind == "reel" and post.format != "reel":
            raise ApiError(
                "validation_error",
                errors=[FieldError("media_ids", "A Reel is one video. Add a video.")],
            )
        if when == "slot":
            post = await posts.queue(call.session, post.id, _env(call))
        elif isinstance(when, datetime):
            post = await posts.schedule(call.session, post.id, when, _env(call))
    except BaseException:
        if reservation is not None:
            await reservation.refund()
        raise
    if savepoint is not None:
        await _preview_end(call, savepoint)
        return await _result(
            call,
            post,
            preview=True,
            summary=f"Preview: this {post.format or 'post'} would be scheduled for "
            f"{moment(call, post.publish_at)}. Nothing is scheduled yet",
            next_step=_confirm_step(True, "schedule it"),
            stored=False,
        )
    if not scheduling:
        call.note("post.created", "scheduled_post", post.id, status=post.status)
        return await _result(
            call,
            post,
            preview=False,
            summary="Saved a draft" + ("" if post.ready else f"; {_failing(post)} to fix"),
            next_step="Schedule it by calling create_post again with a time, or open it in "
            "Amplychat.",
        )
    call.note("post.scheduled", "scheduled_post", post.id, publish_at=post.publish_at)
    await _notify(call, post, "scheduled")
    return await _result(
        call,
        post,
        preview=False,
        summary=f"Scheduled for {moment(call, post.publish_at)}",
        next_step="Cancel it before it publishes with cancel_post.",
    )


def _failing(post: ScheduledPost) -> str:
    n = sum(1 for c in post.checklist if not c.ok)
    return f"{n} checklist item{'s' if n != 1 else ''}"


# ---------------------------------------------------------------- update_post


@dataclass
class _Merged:
    draft: ScheduledPostDraft
    scheduled_before: bool


def _merge(
    current: ScheduledPost,
    args: UpdatePostInput,
    *,
    targets: list[TargetIn] | None,
    kind: Kind | None,
    publish_at: datetime | None,
) -> ScheduledPostDraft:
    """The post as it is, with only the arguments that were sent replaced (the composer's PUT
    replaces the whole post, so the adapter fills in what was left out)."""
    asset_ids = args.media_ids if args.media_ids is not None else [a.id for a in current.assets]
    tags = [
        UserTagIn(asset_id=a.id, username=t.username, x=t.x, y=t.y)
        for a in current.assets
        for t in a.user_tags
        if a.id in asset_ids
    ]
    options = args.reel_options
    return ScheduledPostDraft(
        targets=targets
        or [
            TargetIn(social_account_id=t.social_account_id, caption_override=t.caption_override)
            for t in current.targets
        ],
        asset_ids=asset_ids,
        caption=args.caption if args.caption is not None else current.caption,
        first_comment=(
            args.first_comment if args.first_comment is not None else current.first_comment
        ),
        publish_at=publish_at or current.publish_at,
        kind=kind or current.kind,
        collaborators=(
            args.collaborators if args.collaborators is not None else current.collaborators
        ),
        location=args.location if args.location is not None else current.location_id,
        user_tags=tags,
        cover_asset_id=options.cover_media_id if options else current.cover_asset_id,
        cover_offset_ms=options.cover_offset_ms if options else current.cover_offset_ms,
        share_to_feed=options.share_to_feed if options else current.share_to_feed,
        audio_name=options.audio_name if options else current.audio_name,
    )


@tool(
    registry,
    name="update_post",
    title="Change a post",
    description=(
        "Change a draft or scheduled post: caption, first comment, media, accounts, "
        "collaborators, Reel options or time. Only the fields sent change. Changing a scheduled "
        "post, or giving a draft a time, is previewed first and needs a second call with "
        "confirmed true. A post whose publishing has started can't be changed. Changing "
        "scheduled posts is part of Pro."
    ),
    input_model=UpdatePostInput,
    output_model=PostResult,
    scope="posts:write",
    access=Access.DRAFT,
    min_role=Role.ADMIN,
    destructive=True,  # it overwrites what was there
    open_world=True,
)
async def update_post(call: ToolCall, args: UpdatePostInput) -> PostResult:
    env = _env(call)
    when = resolve_when(call, args.when) if args.when is not None else None
    if when == "draft":
        raise _when_error("To take a scheduled post back to a draft, use cancel_post.")
    current = await posts.get(call.session, args.post_id, env)
    scheduled_before = current.status == SCHEDULED
    scheduling = scheduled_before or when is not None
    if scheduling:
        require_scheduling(call)
    targets: list[TargetIn] | None = None
    if args.accounts is not None:
        ids = await _accounts(call, args.accounts)
        kept = {t.social_account_id: t.caption_override for t in current.targets}
        captions = await _captions(call, args.per_account_captions)
        targets = [
            TargetIn(social_account_id=i, caption_override=captions.get(i, kept.get(i)))
            for i in ids
        ]
    elif args.per_account_captions is not None:
        captions = await _captions(call, args.per_account_captions)
        targets = [
            TargetIn(
                social_account_id=t.social_account_id,
                caption_override=captions.get(t.social_account_id),
            )
            for t in current.targets
        ]
    kind: Kind | None = None
    if args.kind is not None:
        target_ids = [t.social_account_id for t in targets or current.targets]
        kind = _post_kind(args.kind, await _platforms(call.session, target_ids))
    moved = when if isinstance(when, datetime) and scheduled_before else None
    merged = _merge(current, args, targets=targets, kind=kind, publish_at=moved)
    preview = scheduling and not args.confirmed
    reservation = None
    if scheduling and not scheduled_before and not preview:
        reservation = await limits.reserve(
            call.redis, call.plan, limits.POSTS, call.workspace.id, call.now
        )
    savepoint = await call.session.begin_nested() if preview else None
    try:
        post = await posts.replace(call.session, args.post_id, merged, env)
        if when == "slot":
            post = await posts.queue(call.session, post.id, env)
        elif isinstance(when, datetime) and not scheduled_before:
            post = await posts.schedule(call.session, post.id, when, env)
    except BaseException:
        if reservation is not None:
            await reservation.refund()
        raise
    if savepoint is not None:
        await _preview_end(call, savepoint)
        return await _result(
            call,
            post,
            preview=True,
            summary="Preview: the post would be changed as shown. Nothing is changed yet",
            next_step=_confirm_step(True, "make the change"),
        )
    call.note("post.updated", "scheduled_post", post.id, status=post.status)
    if post.status == SCHEDULED:
        await _notify(call, post, "changed")
    return await _result(
        call,
        post,
        preview=False,
        summary="Changed the post"
        + (f"; it publishes {moment(call, post.publish_at)}" if post.publish_at else ""),
        next_step="Cancel it before it publishes with cancel_post."
        if post.status == SCHEDULED
        else "Schedule it by calling update_post with a time.",
    )


# ---------------------------------------------------------------- cancel_post


@tool(
    registry,
    name="cancel_post",
    title="Cancel a scheduled post",
    description=(
        "Take a scheduled post back to a draft so it doesn't publish. The post, its media and "
        "its time are kept. Needs a second call with confirmed true. A post that is publishing "
        "or published can't be cancelled."
    ),
    input_model=CancelPostInput,
    output_model=PostResult,
    scope="posts:write",
    access=Access.WRITE,
    min_role=Role.ADMIN,
    destructive=True,
)
async def cancel_post(call: ToolCall, args: CancelPostInput) -> PostResult:
    env = _env(call)
    current = await posts.get(call.session, args.post_id, env)
    was_scheduled = current.status == SCHEDULED
    preview = was_scheduled and not args.confirmed
    savepoint = await call.session.begin_nested() if preview else None
    post = await posts.unschedule(call.session, args.post_id, env)
    if savepoint is not None:
        await _preview_end(call, savepoint)
        return await _result(
            call,
            post,
            preview=True,
            summary="Preview: the post would go back to a draft and not publish. Nothing is "
            "changed yet",
            next_step=_confirm_step(True, "cancel it"),
        )
    if was_scheduled:
        call.note("post.canceled", "scheduled_post", post.id)
        await _notify(call, post, "cancelled")
    return await _result(
        call,
        post,
        preview=False,
        summary="The post is a draft and won't publish"
        if was_scheduled
        else "The post was already a draft",
        next_step="Schedule it again with update_post and a time.",
    )
