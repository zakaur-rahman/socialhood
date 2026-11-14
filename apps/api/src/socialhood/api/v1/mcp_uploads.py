"""The upload page for AI apps (C-165 phase B; 01-design.md §5.1): an AI app that cannot run a
shell command on the computer holding a file gives the member a link; the page behind it reads the
ticket here, uploads the file straight to Cloudinary with the ticket's signature, and completes
it. The AI app then sees the ticket as ``uploaded`` (get_media_upload) and uses the media.

Owners and admins, like the tools (``media:write``). A ticket that is not this workspace's is 404.
Nothing about the file passes through the API: the browser uploads to storage under the name the
ticket's signature fixes, and completing reads that name from the ticket (services/mcp_uploads.py).

A ``youtube`` ticket (C-196, from prepare_youtube_upload) carries ``youtube``: the post's YouTube
upload session instead of a storage signature. The page PUTs the file to ``upload_url`` in pieces
of ``chunk_bytes``, then completes with ``{video_id}`` (from YouTube's last answer), which goes
through the same completion as the composer's (the post is scheduled, or published for "now").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.deps import CanManagePublishing, Session
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError, FieldError
from socialhood.media.cloudinary import Cloudinary
from socialhood.models.connections import SocialAccount
from socialhood.models.mcp import McpUpload, UploadStatus
from socialhood.models.publishing import ScheduledPostTarget
from socialhood.platforms.deps import deps_from
from socialhood.platforms.youtube.publishing import videos_for
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.publishing import YouTubeUploadComplete
from socialhood.services import audit, mcp_uploads
from socialhood.services.post_publishing import youtube_direct
from socialhood.services.scheduled_posts import posts, views

router = APIRouter(prefix="/v1/w/{wid}", tags=["media"])

KindName = Literal["image", "video", "youtube"]
StatusName = Literal["waiting", "uploaded", "expired", "rejected"]


class DropSignature(ResponseModel):
    """The signed fields of the ticket's one upload (cloud_name, api_key, timestamp, folder, tags,
    public_id, signature) and where to send them."""

    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    tags: str
    public_id: str  # the file's name inside ``folder``: a second upload replaces the first
    allowed_formats: str
    signature: str
    upload_url: str


class YouTubeTicket(ResponseModel):
    """A ``youtube`` ticket's upload while it waits (C-196): PUT the file to ``upload_url`` in
    pieces of ``chunk_bytes`` (``Content-Range``; 308 go on, 200/201 done with the video's id),
    then complete with that id."""

    upload_url: str
    chunk_bytes: int
    title: str
    channel_name: str


class McpUploadTicket(ResponseModel):
    id: uuid.UUID
    kind: KindName
    status: StatusName
    expires_at: datetime
    reason: str | None = None  # why the file was rejected
    media_asset_id: uuid.UUID | None = None
    limits: dict[str, Any]
    upload: DropSignature | None = None  # only while the ticket waits for a file
    youtube: YouTubeTicket | None = None  # a youtube ticket's, only while it waits
    scheduled_post_id: uuid.UUID | None = None  # a youtube ticket's post


class McpUploadCompletion(RequestModel):
    """A ``youtube`` ticket's finished upload: the video id from YouTube's answer. Other tickets
    send no body."""

    video_id: str | None = Field(default=None, min_length=1, max_length=64)


def _channel_name(acct: SocialAccount) -> str:
    return acct.display_name or (f"@{acct.username}" if acct.username else "Your channel")


async def _youtube(
    request: Request, session: AsyncSession, upload: McpUpload, now: datetime
) -> tuple[UploadStatus, YouTubeTicket | None, uuid.UUID | None]:
    """A youtube ticket's status from its target (uploaded once the video is on the post, expired
    with its session) and, while it waits, where the file goes."""
    target = (
        await session.get(ScheduledPostTarget, upload.scheduled_post_target_id)
        if upload.scheduled_post_target_id
        else None
    )
    if target is None:
        return UploadStatus.EXPIRED, None, None
    if target.platform_media_id:
        return UploadStatus.UPLOADED, None, target.scheduled_post_id
    status = mcp_uploads.effective_status(upload, now)
    if status is not UploadStatus.WAITING or not views.is_session(target.container_id):
        return UploadStatus.EXPIRED, None, target.scheduled_post_id
    acct = await session.get(SocialAccount, target.social_account_id)
    if acct is None:  # pragma: no cover - deleting the account deletes its targets
        return UploadStatus.EXPIRED, None, target.scheduled_post_id
    deps = deps_from(request.app.state.http, request.app.state.settings)
    return (
        UploadStatus.WAITING,
        YouTubeTicket(
            upload_url=str(target.container_id),
            chunk_bytes=videos_for(acct, deps).chunk_bytes,
            title=str((target.sent_metadata or {}).get("title") or ""),
            channel_name=_channel_name(acct),
        ),
        target.scheduled_post_id,
    )


async def _youtube_out(
    request: Request, session: AsyncSession, upload: McpUpload, now: datetime
) -> McpUploadTicket:
    status, youtube, post_id = await _youtube(request, session, upload, now)
    return McpUploadTicket(
        id=upload.id,
        kind="youtube",
        status=status.value,
        expires_at=upload.expires_at,
        limits={"note": "Any video YouTube takes, up to 256 GB."},
        youtube=youtube,
        scheduled_post_id=post_id,
    )


def _cloudinary(request: Request) -> Cloudinary:
    return Cloudinary(request.app.state.http, request.app.state.settings)


def _out(
    upload: McpUpload,
    status: UploadStatus,
    *,
    cloudinary: Cloudinary,
    workspace_id: uuid.UUID,
    post_video_max_mb: int,
) -> McpUploadTicket:
    kind: KindName = "image" if upload.kind == "image" else "video"
    return McpUploadTicket(
        id=upload.id,
        kind=kind,
        status=status.value,
        expires_at=upload.expires_at,
        reason=upload.reason,
        media_asset_id=upload.media_asset_id,
        limits=mcp_uploads.limits_for(
            "video" if kind == "youtube" else kind, post_video_max_mb=post_video_max_mb
        ),
        upload=(
            DropSignature.model_validate(mcp_uploads.signature(cloudinary, workspace_id, upload))
            if status is UploadStatus.WAITING
            else None
        ),
    )


@router.get("/mcp-uploads/{upload_id}", operation_id="get_mcp_upload")
async def get_mcp_upload(
    request: Request, upload_id: uuid.UUID, ctx: CanManagePublishing, session: Session
) -> McpUploadTicket:
    """The upload an AI app asked for, with the signed fields to send the file to storage while it
    waits (a ``youtube`` ticket: its YouTube upload address instead). 404 for a ticket that isn't
    this workspace's."""
    upload = await mcp_uploads.get(session, upload_id)
    if upload.kind == mcp_uploads.YOUTUBE:
        return await _youtube_out(request, session, upload, datetime.now(UTC))
    return _out(
        upload,
        mcp_uploads.effective_status(upload, datetime.now(UTC)),
        cloudinary=_cloudinary(request),
        workspace_id=ctx.workspace_id,
        post_video_max_mb=request.app.state.settings.post_video_max_mb,
    )


@router.post("/mcp-uploads/{upload_id}/complete", operation_id="complete_mcp_upload")
async def complete_mcp_upload(
    request: Request,
    upload_id: uuid.UUID,
    ctx: CanManagePublishing,
    session: Session,
    body: McpUploadCompletion | None = None,
) -> McpUploadTicket:
    """After the browser uploaded the file: add the ticket's file to the media library. 409 when
    no file has arrived or the ticket expired; 415 never (a file over a limit is a ``rejected``
    ticket, with the reason); 402 quota_exceeded past the plan's daily upload caps.

    A ``youtube`` ticket takes ``{video_id}`` and completes the post's YouTube upload as the
    composer does (complete_youtube_upload's answers: 422 for a video that isn't the upload's,
    409 when the upload expired)."""
    if (await mcp_uploads.get(session, upload_id)).kind == mcp_uploads.YOUTUBE:
        return await _complete_youtube(request, upload_id, ctx, session, body)
    settings = request.app.state.settings
    finished = await mcp_uploads.finish(
        session,
        _cloudinary(request),
        request.app.state.redis,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        plan=await current_plan(session),
        upload_id=upload_id,
        post_video_max_mb=settings.post_video_max_mb,
        now=datetime.now(UTC),
    )
    if finished.asset is not None and not finished.duplicate:
        await audit.record(
            session, ctx, "media.uploaded", "media_asset", finished.asset.id, source="upload page"
        )
    await session.commit()
    return _out(
        finished.upload,
        UploadStatus(finished.upload.status),
        cloudinary=_cloudinary(request),
        workspace_id=ctx.workspace_id,
        post_video_max_mb=settings.post_video_max_mb,
    )


async def _complete_youtube(
    request: Request,
    upload_id: uuid.UUID,
    ctx: CanManagePublishing,
    session: AsyncSession,
    body: McpUploadCompletion | None,
) -> McpUploadTicket:
    now = datetime.now(UTC)
    upload = await mcp_uploads.get(session, upload_id, for_update=True)
    if body is None or not body.video_id:
        raise ApiError(
            "validation_error", errors=[FieldError("video_id", "Send the video id YouTube gave.")]
        )
    target = (
        await session.get(ScheduledPostTarget, upload.scheduled_post_target_id)
        if upload.scheduled_post_target_id
        else None
    )
    if target is None:
        raise ApiError("conflict", mcp_uploads.EXPIRED)
    env = posts.Env(
        deps=deps_from(request.app.state.http, request.app.state.settings),
        now=now,
        timezone=ctx.workspace.timezone,
    )
    _, handover = await youtube_direct.complete(
        session,
        env.deps,
        scheduled_post_id=target.scheduled_post_id,
        body=YouTubeUploadComplete(target_id=target.id, video_id=body.video_id),
        env=env,
    )
    upload.status = UploadStatus.UPLOADED.value
    upload.reason = None
    await session.flush()
    out = await _youtube_out(request, session, upload, now)
    await commit_and_publish(session, request.app.state.redis)
    if handover is not None:
        await posts.hand_over(handover)
    return out
