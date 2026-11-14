"""YouTube uploads for AI apps (C-196; "edit with Claude, schedule with Amplychat"):
prepare_youtube_upload and get_youtube_upload_status.

- ``prepare_youtube_upload`` makes a post for one YouTube channel with its title, description,
  privacy, time and the two answers YouTube needs (``made_for_kids``, ``synthetic_media``: no
  defaults, the AI must ask), previewed first like create_post. Confirmed, it opens the channel's
  upload (services/post_publishing/youtube_direct.start: one of YouTube's daily uploads) and
  returns two ways to send the file straight to YouTube: a one-time link to the upload page
  (a ``youtube`` ticket, for apps without a shell) and the upload address with a curl command (for
  Claude Code, which sends the file from the member's disk). Nothing passes through Amplychat.
- ``get_youtube_upload_status`` says where the video is: waiting for the file, uploading,
  processing, scheduled, published or failed. When YouTube holds the whole file and nobody has
  told Amplychat yet (the curl route), it finishes the upload as the upload page would: the post
  is scheduled, or published for "now". So it is a write-tier tool.

Both are Creator and above (the ``full`` mode), owners and admins, audited, and capped like
create_post (``mcp_posts_daily``, ``mcp_posts``); a post's YouTube rules are the composer's.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, ValidationError

from socialhood.agent.tools.common import find_account, handle
from socialhood.errors import ApiError, FieldError
from socialhood.mcp import confirmations
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import (
    Access,
    ConfirmedInput,
    WriteInput,
    WriteOutput,
    registry,
    tool,
)
from socialhood.mcp.tools.common import end_preview, moment
from socialhood.mcp.tools.posts import ChecklistOut
from socialhood.mcp.tools.publish import _reserve_post, require_scheduling, resolve_when
from socialhood.models.identity import Role
from socialhood.models.publishing import STORED_CAPTION_MAX_CHARS, YOUTUBE_TITLE_MAX_CHARS
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.publishing import videos_for
from socialhood.repositories import scheduled_posts as scheduled_posts_repo
from socialhood.schemas.publishing import (
    ScheduledPost,
    ScheduledPostDraft,
    TargetIn,
    YouTubeOptions,
    YouTubeUploadComplete,
)
from socialhood.services import mcp_uploads
from socialhood.services.post_publishing import youtube_direct
from socialhood.services.scheduled_posts import posts, views

CHANNEL = "The YouTube channel: its account id or @handle (from list_accounts)."
PUBLISH_AT = (
    "When it goes out: a date and time at least 1 minute from now (2026-11-20T18:00:00+05:30, "
    "or 2026-11-20 18:00 in the workspace's time zone, or words like “tomorrow 7 pm”), or "
    "“now” to publish as soon as the upload finishes, only when the member asked for that."
)
KIDS = (
    "Is the video made for kids (YouTube's audience setting, required by US law)? Ask the member; "
    "never guess."
)
SYNTHETIC = (
    "Does it contain realistic altered or AI-made content a viewer could take for real? Ask the "
    "member. Ordinary edits (cuts, captions, colour, music) don't count."
)
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
WAITING = "The upload is open: send the file with upload_page_url or the curl command."


class PrepareYouTubeUploadInput(ConfirmedInput):
    account_id: str = Field(min_length=1, max_length=100, description=CHANNEL)
    title: str = Field(min_length=1, max_length=YOUTUBE_TITLE_MAX_CHARS, description="No < or >.")
    description: str = Field(
        default="",
        max_length=STORED_CAPTION_MAX_CHARS,
        description="Up to 5,000 bytes, no < or >.",
    )
    privacy: Literal["public", "unlisted", "private"] = "public"
    made_for_kids: bool = Field(description=KIDS)
    synthetic_media: bool = Field(description=SYNTHETIC)
    publish_at: str = Field(min_length=1, max_length=100, description=PUBLISH_AT)
    format: Literal["video", "short"] = Field(
        default="video", description="short: a vertical video up to 3 minutes."
    )
    tags: list[Tag] | None = Field(default=None, max_length=100)
    file_size: int | None = Field(
        default=None, ge=1, description="The file's size in bytes, when known."
    )
    file_name: str | None = Field(
        default=None, max_length=200, description="The local file's name, used in the command."
    )


class PreparedYouTubeUpload(WriteOutput):
    post_id: uuid.UUID | None = None  # None in a preview
    channel: str
    title: str
    privacy: str
    publish_at: str | None = None  # workspace time and UTC; None for "now"
    checklist: list[ChecklistOut]
    upload_page_url: str | None = None
    upload_url: str | None = None
    chunk_bytes: int | None = None
    expires_at: str | None = None
    curl_hint: str | None = None
    next_step: str


def _options(args: PrepareYouTubeUploadInput) -> YouTubeOptions:
    try:
        return YouTubeOptions(
            title=args.title,
            privacy=args.privacy,
            made_for_kids=args.made_for_kids,
            synthetic_media=args.synthetic_media,
            tags=list(args.tags or []),
            format=args.format,
        )
    except ValidationError as error:
        raise ApiError(
            "validation_error",
            "Some arguments aren't valid. Fix them and try again.",
            errors=[
                FieldError(".".join(str(p) for p in e["loc"]) or "title", e["msg"])
                for e in error.errors(include_url=False)
            ],
        ) from error


def content_type_of(file_name: str | None) -> str:
    name = (file_name or "").lower()
    if name.endswith(".mov"):
        return "video/quicktime"
    if name.endswith(".mp4"):
        return "video/mp4"
    return "video/*"


def curl_hint(upload_url: str, file_name: str | None, content_type: str) -> str:
    name = (file_name or "VIDEO_FILE").replace("\\", "/").rsplit("/", 1)[-1]
    if any(c in name for c in '"$`'):
        name = "VIDEO_FILE"
    return (
        f'curl -sS -X PUT -H "Content-Type: {content_type}" --upload-file "{name}" '
        f'"{upload_url}"  # one PUT is fine; if it is cut, ask what arrived with '
        '-H "Content-Range: bytes */TOTAL" and send the rest with '
        '"Content-Range: bytes FIRST-LAST/TOTAL". Then call get_youtube_upload_status.'
    )


def _env(call: ToolCall) -> posts.Env:
    return posts.Env(deps=call.deps, now=call.now, timezone=call.timezone.key)


@tool(
    registry,
    name="prepare_youtube_upload",
    title="Prepare a YouTube upload",
    description=(
        "Make a post for a YouTube channel and open its upload: the video goes straight from the "
        "member's computer to YouTube, private until the chosen time, when YouTube publishes it "
        "(or at once for “now”). Ask the member whether the video is made for kids and whether "
        "it has realistic AI-made content: both are required and have no default. Previewed "
        "first: show the preview and call again only after they agree, with confirmed true and "
        "the preview's confirmation_token. The result has upload_page_url, a one-time page where "
        "the member drops the file, and upload_url with a curl command for apps that can run "
        "one where the file is. Then call get_youtube_upload_status. Uses one of YouTube's daily "
        "uploads. Part of Creator and above."
    ),
    input_model=PrepareYouTubeUploadInput,
    output_model=PreparedYouTubeUpload,
    scope="posts:write",
    access=Access.WRITE,
    min_role=Role.ADMIN,
    open_world=True,
    dedupe_window_s=confirmations.TTL_S,
)
async def prepare_youtube_upload(
    call: ToolCall, args: PrepareYouTubeUploadInput
) -> PreparedYouTubeUpload:
    require_scheduling(call)
    acct = await find_account(call.agent_context(), args.account_id)
    if acct is None or acct.platform != "youtube":
        raise ApiError(
            "validation_error",
            errors=[FieldError("account_id", "Give a connected YouTube channel.")],
        )
    when = resolve_when(call, args.publish_at)
    if when != "now" and not isinstance(when, datetime):
        raise ApiError(
            "validation_error",
            errors=[FieldError("publish_at", "Give a time, or “now”.")],
        )
    at = when if isinstance(when, datetime) else None
    options = _options(args)
    draft = ScheduledPostDraft(
        targets=[TargetIn(social_account_id=acct.id, options=options)],
        caption=args.description,
        publish_at=at,
    )
    channel = handle(acct)
    preview = not args.confirmed
    if not preview:
        confirmations.require(call, args, args.confirmation_token)
    env = _env(call)
    if preview:
        savepoint = await call.session.begin_nested()
        post = await posts.create(call.session, draft, env, user_id=call.principal.user_id)
        await end_preview(call, savepoint)
        return _result(
            call,
            post,
            channel=channel,
            options=options,
            preview=True,
            summary=(
                f"Preview: a {'Short' if args.format == 'short' else 'video'} for {channel}, "
                + (f"published {moment(call, at)}" if at else "published once it is uploaded")
                + ". Nothing is created yet"
            ),
            next_step=confirmations.next_step("open the upload"),
            token=confirmations.issue(call, args),
        )
    reservation = await _reserve_post(call)
    content_type = content_type_of(args.file_name)
    try:
        post = await posts.create(call.session, draft, env, user_id=call.principal.user_id)
        opened = await youtube_direct.start(
            call.session,
            call.redis,
            call.deps,
            scheduled_post_id=post.id,
            target_id=acct.id,
            file_size=args.file_size,
            content_type=content_type,
            now=call.now,
            timezone=call.timezone.key,
        )
        [target] = [
            t
            for t, a in await scheduled_posts_repo.targets_for(call.session, [post.id])
            if a.id == acct.id
        ]
        ticket = await mcp_uploads.youtube_ticket(
            call.session,
            user_id=call.principal.user_id,
            target_id=target.id,
            expires_at=opened.expires_at,
        )
    except BaseException:
        await reservation.refund()
        raise
    post = await posts.get(call.session, post.id, env)
    call.note("post.created", "scheduled_post", post.id, status=post.status, youtube=True)
    return _result(
        call,
        post,
        channel=channel,
        options=options,
        preview=False,
        summary=f"The upload to {channel} is open until {moment(call, opened.expires_at)}",
        next_step=(
            "Have the member open upload_page_url and drop the file, or run curl_hint where the "
            "file is. Then call get_youtube_upload_status with post_id."
        ),
        upload_page_url=call.dashboard_url(f"upload/{ticket.id}"),
        upload_url=opened.upload_url,
        chunk_bytes=opened.chunk_bytes,
        expires_at=moment(call, opened.expires_at),
        curl=curl_hint(opened.upload_url, args.file_name, content_type),
    )


def _result(
    call: ToolCall,
    post: ScheduledPost,
    *,
    channel: str,
    options: YouTubeOptions,
    preview: bool,
    summary: str,
    next_step: str,
    token: str | None = None,
    upload_page_url: str | None = None,
    upload_url: str | None = None,
    chunk_bytes: int | None = None,
    expires_at: str | None = None,
    curl: str | None = None,
) -> PreparedYouTubeUpload:
    # The video isn't there yet: "upload it" is what the upload is for, not a problem to fix.
    checklist = [
        c
        for c in post.checklist
        if not (c.key == "youtube" and c.message.startswith("Upload the video"))
    ]
    return PreparedYouTubeUpload(
        summary=summary[:400],
        preview=preview,
        confirmation_token=token,
        post_id=None if preview else post.id,
        channel=channel,
        title=options.title,
        privacy=options.privacy,
        publish_at=moment(call, post.publish_at),
        checklist=[
            ChecklistOut(key=c.key, ok=c.ok, message=c.message, field=c.field) for c in checklist
        ],
        upload_page_url=upload_page_url,
        upload_url=upload_url,
        chunk_bytes=chunk_bytes,
        expires_at=expires_at,
        curl_hint=curl,
        next_step=next_step,
    )


# ---------------------------------------------------------------- get_youtube_upload_status


class YouTubeUploadStatusInput(WriteInput):
    post_id: uuid.UUID = Field(description="The post_id prepare_youtube_upload returned.")


class YouTubeUploadStatus(WriteOutput):
    post_id: uuid.UUID
    post_status: str
    channel: str
    route: str  # direct: straight to YouTube; media: from the media tray at the time
    state: str  # waiting_for_file, uploading, processing, scheduled, published, failed
    video_id: str | None = None
    url: str | None = None
    bytes_received: int | None = None  # while uploading, when YouTube says
    upload_expires_at: str | None = None
    publish_at: str | None = None
    error: str | None = None
    next_step: str


NEXT = {
    "waiting_for_file": WAITING,
    "uploading": "Send the rest of the file, then call this again.",
    "processing": "YouTube is processing the video. Check again in a few minutes.",
    "scheduled": "Nothing to do: YouTube publishes it at the time.",
    "published": "It is on YouTube.",
    "failed": "Open the post in Amplychat to see why and try again.",
}


@tool(
    registry,
    name="get_youtube_upload_status",
    title="Check a YouTube upload",
    description=(
        "Where a YouTube post's video is: waiting for the file, uploading, processing, "
        "scheduled or published (with its link), or failed with the reason. When YouTube holds "
        "the whole file, this also finishes the upload in Amplychat: the post is scheduled, or "
        "published if it was for “now”."
    ),
    input_model=YouTubeUploadStatusInput,
    output_model=YouTubeUploadStatus,
    scope="posts:write",
    access=Access.WRITE,
    min_role=Role.ADMIN,
)
async def get_youtube_upload_status(
    call: ToolCall, args: YouTubeUploadStatusInput
) -> YouTubeUploadStatus:
    env = _env(call)
    post = await posts.get(call.session, args.post_id, env)
    found = [
        (t, a)
        for t, a in await scheduled_posts_repo.targets_for(call.session, [post.id])
        if a.platform == "youtube"
    ]
    if not found:
        raise ApiError(
            "validation_error",
            errors=[FieldError("post_id", "This post has no YouTube channel.")],
        )
    target, acct = found[0]
    received: int | None = None
    if views.is_session(target.container_id) and target.status == "pending":
        try:
            progress = await videos_for(acct, call.deps).progress(
                str(target.container_id), total=None
            )
        except PlatformError:
            progress = None
        if progress is not None and progress.video is not None:
            post, handover = await youtube_direct.complete(
                call.session,
                call.deps,
                scheduled_post_id=post.id,
                body=YouTubeUploadComplete(target_id=target.id, video_id=progress.video.id),
                env=env,
            )
            if handover is not None:

                async def hand_over() -> None:
                    await posts.hand_over(handover)

                call.after_commit.append(hand_over)
            call.note("post.scheduled", "scheduled_post", post.id, youtube=True)
        elif progress is not None:
            received = progress.received
    out = next(t for t in post.targets if t.social_account_id == acct.id)
    state = out.youtube.state if out.youtube else "waiting_for_file"
    return YouTubeUploadStatus(
        summary=f"The video is {state.replace('_', ' ')}",
        post_id=post.id,
        post_status=post.status,
        channel=handle(acct),
        route=out.youtube.route if out.youtube else "direct",
        state=state,
        video_id=out.youtube.video_id if out.youtube else None,
        url=out.youtube.url if out.youtube else None,
        bytes_received=received,
        upload_expires_at=moment(call, out.youtube.upload_expires_at) if out.youtube else None,
        publish_at=moment(call, post.publish_at),
        error=out.error.message if out.error else None,
        next_step=NEXT.get(state, WAITING),
    )
