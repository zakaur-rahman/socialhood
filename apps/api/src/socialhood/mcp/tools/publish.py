"""Publishing writes (01-design.md §4.1, §4.4): create_post, update_post, cancel_post.

Posts go directly, as the member's own action (decision D3), with these safety nets:

- **Confirmation.** A call that would schedule or publish a post, or change or cancel a scheduled
  one, does nothing until it is repeated with ``confirmed: true`` and the preview's
  ``confirmation_token`` (mcp/confirmations.py), which the server checks. Without it the result is
  a preview (``preview`` true, nothing stored): the resolved time in the workspace's zone and UTC,
  the accounts, and the composer's checklist, so a wrong time-zone guess or a failing item shows
  before anything is scheduled. Saving or editing a draft needs no confirmation: it is changed at
  once.
- **The app's own times.** A time is at least 1 minute ahead (``MIN_SCHEDULE_LEAD``), the rule a
  person gets in the composer. ``when: "now"`` publishes at once through the app's own Publish now
  (``posts.publish_now``), for when the member asked for exactly that; it is previewed like any
  scheduling, and the preview says it can't be undone.
- **The team is told.** Owners and admins get a notification naming the AI app and the member,
  with a link to the post (where it is cancelled).
- **Free saves drafts only.** The workspace's mode and the plan decide (``require_scheduling``);
  Free gets ``entitlement_required``, a workspace set to "read and drafts" a plain refusal.
- **Caps** on posts scheduled or published now: per day (``mcp_posts_daily``) and per minute
  (``mcp_posts``).

Everything else is the app's own rules: the same services as the composer
(``services/scheduled_posts``), so the checklist, the account and media checks, the monthly
quota (``scheduled_posts_monthly``) and the format rules are not repeated here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.agent.timeparse import TimeParseError, resolve_instant
from socialhood.agent.tools.common import find_account, handle
from socialhood.billing.entitlements import entitlement_error
from socialhood.errors import ApiError, FieldError
from socialhood.mcp import confirmations, limits
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import Access, ConfirmedInput, ToolInput, WriteOutput, registry, tool
from socialhood.mcp.tools.common import end_preview, moment
from socialhood.mcp.tools.posts import ACCOUNT, ChecklistOut
from socialhood.models.identity import Role, User
from socialhood.models.mcp import AiConnectionsMode
from socialhood.models.notifications import NotificationType, Severity
from socialhood.models.publishing import (
    COLLABORATORS_MAX,
    FIRST_COMMENT_MAX_CHARS,
    INSTAGRAM_USERNAME_MAX_CHARS,
    MIN_SCHEDULE_LEAD,
    STORED_CAPTION_MAX_CHARS,
    PostFormat,
)
from socialhood.repositories import scheduled_posts as scheduled_posts_repo
from socialhood.repositories import social_accounts
from socialhood.schemas.publishing import (
    ScheduledPost,
    ScheduledPostDraft,
    TargetIn,
    UserTagIn,
)
from socialhood.services import notifications
from socialhood.services.scheduled_posts import posts, rules

NOW_ONLY = "only when the member asked to publish immediately"
WHEN = (
    "When to publish: a date and time at least 1 minute from now (2026-11-07T18:00:00+05:30, or "
    "2026-11-07 18:00 in the workspace's time zone, or words like “tomorrow 7 pm”); "
    "“next_free_slot” for the earliest free posting time of the accounts; “draft” to save it "
    f"without a time; or “now” to publish at once, {NOW_ONLY}."
)
KIND = (
    "post: an image, a video (published as a Reel on Instagram) or a carousel; reel: one video "
    "as a Reel; story: one image or video as a Story, without caption."
)
DRAFT, SLOT, NOW, SCHEDULED = "draft", "next_free_slot", "now", "scheduled"
TOO_SOON = f"{rules.TIME_TOO_SOON} Or use “draft”."
FARTHEST = timedelta(days=3660)  # nobody plans a post further out, and year 9999 can't be shown
OUT_OF_RANGE = "That date is out of range. Pick a time in the next few years."
PUBLISHING = "It is publishing and can't be cancelled. get_scheduled_post shows how it went."
Kind = Literal["post", "reel", "story"]
# The app's own limits (schemas/publishing.py), so a value over one is a field error here.
AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Collaborator = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=INSTAGRAM_USERNAME_MAX_CHARS + 1
    ),
]
AccountCaption = Annotated[str, Field(max_length=STORED_CAPTION_MAX_CHARS)]


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
    collaborators: list[Collaborator] | None = Field(
        default=None,
        max_length=COLLABORATORS_MAX,
        description=f"Instagram usernames to invite, at most {COLLABORATORS_MAX}.",
    )
    location: str | None = Field(
        default=None, max_length=300, description="A Facebook Page id or its link."
    )
    reel_options: ReelOptions | None = None
    per_account_captions: dict[AccountName, AccountCaption] | None = Field(
        default=None,
        max_length=10,  # as many as a post has accounts
        description="A caption for one account instead of the main one, by account id or @handle.",
    )


class CreatePostInput(PostFields, ConfirmedInput):
    accounts: list[AccountName] = Field(min_length=1, max_length=10, description=ACCOUNT)
    kind: Kind = Field(default="post", description=KIND)
    when: str = Field(min_length=1, max_length=100, description=WHEN)


class UpdatePostInput(PostFields, ConfirmedInput):
    post_id: uuid.UUID = Field(description="A draft or scheduled post's id.")
    accounts: list[AccountName] | None = Field(
        default=None, min_length=1, max_length=10, description=ACCOUNT
    )
    kind: Kind | None = Field(default=None, description=KIND)
    when: str | None = Field(
        default=None,
        max_length=100,
        description="A new time (the same forms as create_post), “next_free_slot”, or “now” to "
        f"publish at once, {NOW_ONLY}. A draft given a time is scheduled. Omit to keep the time.",
    )


class CancelPostInput(ConfirmedInput):
    post_id: uuid.UUID = Field(description="A scheduled post's id.")


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


def resolve_when(call: ToolCall, when: str) -> datetime | Literal["draft", "slot", "now"]:
    """``when`` as a UTC time, or ``draft``, ``slot`` or ``now``. A time without an offset is read
    in the workspace's zone; a phrase goes through the same resolver as Ask. Under a minute ahead
    (the app's rule) or out of range is a field error on ``when``."""
    text = when.strip()
    if text.casefold() == DRAFT:
        return "draft"
    if text.casefold() in (SLOT, "next free slot", "queue"):
        return "slot"
    if text.casefold() == NOW:
        return "now"
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            at = resolve_instant(text, now=call.now, tz=call.timezone).at
        except TimeParseError as error:
            raise _when_error(str(error)) from error
    if at.tzinfo is None:
        at = at.replace(tzinfo=call.timezone)
    try:
        at = at.astimezone(UTC)
    except OverflowError as error:  # year 1 or 9999, in a zone away from UTC
        raise _when_error(OUT_OF_RANGE) from error
    if at > call.now + FARTHEST:
        raise _when_error(OUT_OF_RANGE)
    if at < call.now + MIN_SCHEDULE_LEAD:
        raise _when_error(TOO_SOON)
    return at


def require_scheduling(call: ToolCall) -> None:
    """Scheduling, publishing or changing a scheduled post needs the ``full`` mode: Free is capped
    at drafts by its plan (402), a workspace set to drafts refuses in plain words."""
    if call.mode is AiConnectionsMode.FULL:
        return
    if call.workspace.ai_connections_mode == AiConnectionsMode.FULL:  # the plan holds it back
        raise entitlement_error("ai_connections")
    raise ApiError(
        "forbidden",
        "This workspace lets AI apps only read and prepare drafts. An owner or admin can change "
        "that in Amplychat, under Settings. Saving the post as a draft works.",
    )


async def _reserve_post(call: ToolCall) -> limits.Reservation:
    return await limits.reserve_post(
        call.redis,
        call.plan,
        call.workspace.id,
        call.now,
        rate_limited=call.settings.rate_limits_enabled,
    )


async def _accounts(call: ToolCall, names: list[str], field: str = "accounts") -> list[uuid.UUID]:
    # shortcut: one accounts query per name (at most 20 names a call); one query for all needs
    # find_account (agent/tools/common.py) to take a loaded list.
    ctx = call.agent_context()
    found: list[uuid.UUID] = []
    for name in names:
        account = await find_account(ctx, name)
        if account is None:  # a blank name, which the input refuses too
            raise ApiError(
                "validation_error", errors=[FieldError(field, "An account can't be blank.")]
            )
        found.append(account.id)
    return found


async def _captions(call: ToolCall, by_account: dict[str, str] | None) -> dict[uuid.UUID, str]:
    if not by_account:
        return {}
    ids = await _accounts(call, list(by_account), "per_account_captions")
    return dict(zip(ids, by_account.values(), strict=True))


def _post_kind(kind: Kind, platforms: set[str]) -> Literal["post", "reel", "story"]:
    """Instagram publishes a single video as a Reel already; ``reel`` is a Facebook Reel only
    when a Page is a target (rules.REEL_NEEDS_PAGE)."""
    if kind == "reel" and "facebook" not in platforms:
        return "post"
    return kind


async def _platforms(session: AsyncSession, ids: list[uuid.UUID]) -> set[str]:
    return {a.platform for a in await social_accounts.list_all(session) if a.id in ids}


async def _locked(call: ToolCall, post_id: uuid.UUID, env: posts.Env) -> ScheduledPost:
    """The post, read under its row lock (the one ``posts.replace`` and the dispatcher take): its
    status decides whether a preview is needed, so it can't change before the write."""
    await scheduled_posts_repo.get(call.session, post_id, for_update=True)
    return await posts.get(call.session, post_id, env)


async def _target_names(call: ToolCall, post: ScheduledPost) -> list[str]:
    names = {a.id: handle(a) for a in await social_accounts.list_all(call.session)}
    return [names.get(t.social_account_id, "a removed account") for t in post.targets]


async def _result(
    call: ToolCall,
    post: ScheduledPost,
    *,
    preview: bool,
    summary: str,
    next_step: str,
    stored: bool = True,
    token: str | None = None,
    now: bool = False,
) -> PostResult:
    # Publish now sets the time to this moment, so the post's own "at least 1 minute from now"
    # line fails by design: it isn't shown as something to fix.
    checklist = [c for c in post.checklist if not (now and c.key == "publish_at")]
    return PostResult(
        summary=summary[:400],
        preview=preview,
        confirmation_token=token,
        post_id=post.id if stored else None,
        status=post.status,
        kind=post.kind,
        format=post.format,
        caption=post.caption,
        first_comment=post.first_comment,
        collaborators=post.collaborators,
        accounts=await _target_names(call, post),
        media_ids=[a.id for a in post.assets],
        publish_at=moment(call, post.publish_at),
        checklist=[
            ChecklistOut(key=c.key, ok=c.ok, message=c.message, field=c.field) for c in checklist
        ],
        ready=all(c.ok for c in checklist) if now else post.ready,
        next_step=next_step,
        dashboard_url=call.dashboard_url(f"schedule/{post.id}") if stored else None,
    )


def _env(call: ToolCall) -> posts.Env:
    return posts.Env(deps=call.deps, now=call.now, timezone=call.timezone.key)


async def _notify(call: ToolCall, post: ScheduledPost, did: str) -> None:
    """Tell the owners and admins that an AI app scheduled, published, changed or cancelled a
    post, who asked, and where to cancel it (§4.4). Each call tells them once: the key carries the
    call's id, so a second change to the same post is told too."""
    user = await call.session.get(User, call.principal.user_id)
    who = (user.name or user.email) if user is not None else "A member"
    app = call.client_name or "An AI app"
    what = (
        rules.format_label(PostFormat(post.format), len(post.assets)).lower()
        if post.format
        else "post"
    )
    a = "an" if what[0] in "aeiou" else "a"
    when = moment(call, post.publish_at)
    if did == "published":
        title = f"{app} published {a} {what} now"
        then = "Open the post to see it."
    else:
        title = f"{app} {did} {a} {what}" + (f" for {when}" if when and did != "cancelled" else "")
        then = "Open the post to review or cancel it before it publishes."
    await notifications.notify_admins(
        call.session,
        type=NotificationType.AI_POST_CHANGE.value,
        severity=Severity.INFO.value,
        title=title[:200],
        body=f"{who} asked {app} to do this. {then}",
        link=f"/schedule/{post.id}",
        dedupe_key=f"mcp-post:{post.id}:{did}:{call.call_id}",
    )


async def _now_preview(call: ToolCall, post: ScheduledPost) -> str:
    names = await _target_names(call, post)
    to = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
    return (
        f"Preview: this publishes immediately to {to} and cannot be undone. Nothing is published "
        "yet"
    )


async def _published_now(
    call: ToolCall, post: ScheduledPost, handover: posts.HandOver
) -> PostResult:
    """A confirmed Publish now: the publishing jobs get the targets once the call has committed,
    as the app's own route does after its commit (the 30-second dispatcher takes any that fail to
    queue), and the team is told."""

    async def hand_over() -> None:
        await posts.hand_over(handover)

    call.after_commit.append(hand_over)
    call.note("post.published", "scheduled_post", post.id, publish_at=post.publish_at)
    await _notify(call, post, "published")
    return await _result(
        call, post, preview=False, summary="Publishing now", next_step=PUBLISHING, now=True
    )


# ---------------------------------------------------------------- create_post


@tool(
    registry,
    name="create_post",
    title="Create, schedule or publish a post",
    description=(
        "Create an Instagram or Facebook post, carousel, Reel or Story from media in the "
        "library, and save it as a draft, schedule it for a time, put it in the next free "
        "posting slot, or publish it now. It is checked with the same checklist as the composer, "
        "and a failing item stops scheduling. Scheduling and publishing are previewed first: the "
        "call shows the resolved time and the checklist. Show the member the preview and call "
        "again only after they agree, with confirmed true and the preview's confirmation_token. "
        "A scheduled time is at least 1 minute ahead. when “now” publishes at once and cannot be "
        f"undone: use it {NOW_ONLY}. The team is notified. Plans: scheduling and publishing are "
        "part of Creator and Business; drafts work on every plan, with no preview."
    ),
    input_model=CreatePostInput,
    output_model=PostResult,
    scope="posts:write",
    access=Access.DRAFT,
    min_role=Role.ADMIN,
    open_world=True,
    dedupe_window_s=confirmations.TTL_S,  # as long as a confirmation token lasts
)
async def create_post(call: ToolCall, args: CreatePostInput) -> PostResult:
    when = resolve_when(call, args.when)
    scheduling = when != "draft"
    now = when == "now"
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
    if scheduling and not preview:
        confirmations.require(call, args, args.confirmation_token)
    reservation = None
    if scheduling and not preview:
        reservation = await _reserve_post(call)
    savepoint = await call.session.begin_nested() if preview else None
    handover: posts.HandOver | None = None
    try:
        post = await posts.create(call.session, draft, _env(call), user_id=call.principal.user_id)
        if args.kind == "reel" and post.format != "reel":
            raise ApiError(
                "validation_error",
                errors=[FieldError("media_ids", "A Reel is one video. Add a video.")],
            )
        if when == "slot":
            post = await posts.queue(call.session, post.id, _env(call))
        elif now:
            post, handover = await posts.publish_now(call.session, post.id, _env(call))
        elif isinstance(when, datetime):
            post = await posts.schedule(call.session, post.id, when, _env(call))
    except BaseException:
        if reservation is not None:
            await reservation.refund()
        raise
    if savepoint is not None:
        await end_preview(call, savepoint)
        return await _result(
            call,
            post,
            preview=True,
            summary=await _now_preview(call, post)
            if now
            else f"Preview: this {post.format or 'post'} would be scheduled for "
            f"{moment(call, post.publish_at)}. Nothing is scheduled yet",
            next_step=confirmations.next_step("publish it now" if now else "schedule it"),
            stored=False,
            token=confirmations.issue(call, args),
            now=now,
        )
    if not scheduling:
        call.note("post.created", "scheduled_post", post.id, status=post.status)
        return await _result(
            call,
            post,
            preview=False,
            summary="Saved a draft" + ("" if post.ready else f"; {_failing(post)} to fix"),
            next_step="Schedule it by calling update_post with a time, or open it in Amplychat.",
        )
    if handover is not None:
        return await _published_now(call, post, handover)
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

    def reel(name: str, kept: Any) -> Any:
        """A Reel option from the request when it was sent, else the post's own."""
        return getattr(options, name) if options and name in options.model_fields_set else kept

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
        cover_asset_id=reel("cover_media_id", current.cover_asset_id),
        cover_offset_ms=reel("cover_offset_ms", current.cover_offset_ms),
        share_to_feed=reel("share_to_feed", current.share_to_feed),
        audio_name=reel("audio_name", current.audio_name),
    )


@tool(
    registry,
    name="update_post",
    title="Change a post",
    description=(
        "Change a draft or scheduled post: caption, first comment, media, accounts, "
        "collaborators, Reel options or time. Only the fields sent change. A draft is changed at "
        "once, with no preview. Changing a scheduled post, giving a draft a time, or publishing "
        "now is previewed first: show the member the preview and call again only after they "
        "agree, with confirmed true and its confirmation_token. when “now” publishes at once and "
        f"cannot be undone: use it {NOW_ONLY}. A post whose publishing has started can't be "
        "changed. Changing scheduled posts and publishing are part of Creator and Business."
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
    now = when == "now"
    current = await _locked(call, args.post_id, env)
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
    if scheduling and not preview:
        confirmations.require(call, args, args.confirmation_token)
    # New scheduling and every Publish now count against the caps; a change to a post that is
    # already scheduled doesn't.
    reservation = None
    if scheduling and not preview and (now or not scheduled_before):
        reservation = await _reserve_post(call)
    savepoint = await call.session.begin_nested() if preview else None
    handover: posts.HandOver | None = None
    try:
        post = await posts.replace(call.session, args.post_id, merged, env)
        if when == "slot":
            post = await posts.queue(call.session, post.id, env)
        elif now:
            post, handover = await posts.publish_now(call.session, post.id, env)
        elif isinstance(when, datetime) and not scheduled_before:
            post = await posts.schedule(call.session, post.id, when, env)
    except BaseException:
        if reservation is not None:
            await reservation.refund()
        raise
    if savepoint is not None:
        await end_preview(call, savepoint)
        return await _result(
            call,
            post,
            preview=True,
            summary=await _now_preview(call, post)
            if now
            else "Preview: the post would be changed as shown. Nothing is changed yet",
            next_step=confirmations.next_step("publish it now" if now else "make the change"),
            token=confirmations.issue(call, args),
            now=now,
        )
    if handover is not None:
        return await _published_now(call, post, handover)
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
        "its time are kept. Previewed first: show the member the preview and call again only "
        "after they agree, with confirmed true and its confirmation_token. A post that is "
        "publishing or published can't be cancelled."
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
    current = await _locked(call, args.post_id, env)
    was_scheduled = current.status == SCHEDULED
    preview = was_scheduled and not args.confirmed
    if was_scheduled and not preview:
        confirmations.require(call, args, args.confirmation_token)
    savepoint = await call.session.begin_nested() if preview else None
    post = await posts.unschedule(call.session, args.post_id, env)
    if savepoint is not None:
        await end_preview(call, savepoint)
        return await _result(
            call,
            post,
            preview=True,
            summary="Preview: the post would go back to a draft and not publish. Nothing is "
            "changed yet",
            next_step=confirmations.next_step("cancel it"),
            token=confirmations.issue(call, args),
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
