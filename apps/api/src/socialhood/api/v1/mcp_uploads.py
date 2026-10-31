"""The upload page for AI apps (C-165 phase B; 01-design.md §5.1): an AI app that cannot run a
shell command on the computer holding a file gives the member a link; the page behind it reads the
ticket here, uploads the file straight to Cloudinary with the ticket's signature, and completes
it. The AI app then sees the ticket as ``uploaded`` (get_media_upload) and uses the media.

Owners and admins, like the tools (``media:write``). A ticket that is not this workspace's is 404.
Nothing about the file passes through the API: the browser uploads to storage and sends only the
``public_id`` it got back, which is checked against the ticket's tag (services/mcp_uploads.py).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import Field

from socialhood.auth.deps import CanManagePublishing, Session
from socialhood.billing.plans import current_plan
from socialhood.media.cloudinary import Cloudinary
from socialhood.models.mcp import McpUpload, UploadStatus
from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.services import audit, mcp_uploads

router = APIRouter(prefix="/v1/w/{wid}", tags=["media"])

KindName = Literal["image", "video"]
StatusName = Literal["waiting", "uploaded", "expired", "rejected"]


class DropSignature(ResponseModel):
    """The signed fields of the ticket's one upload (cloud_name, api_key, timestamp, folder, tags,
    signature) and where to send them."""

    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    tags: str
    signature: str
    upload_url: str


class McpUploadTicket(ResponseModel):
    id: uuid.UUID
    kind: KindName
    status: StatusName
    expires_at: datetime
    reason: str | None = None  # why the file was rejected
    media_asset_id: uuid.UUID | None = None
    limits: dict[str, Any]
    upload: DropSignature | None = None  # only while the ticket waits for a file


class McpUploadComplete(RequestModel):
    public_id: str = Field(max_length=255)  # Cloudinary allows 255


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
        limits=mcp_uploads.limits_for(kind, post_video_max_mb=post_video_max_mb),
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
    waits. 404 for a ticket that isn't this workspace's."""
    upload = await mcp_uploads.get(session, upload_id)
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
    body: McpUploadComplete,
    ctx: CanManagePublishing,
    session: Session,
) -> McpUploadTicket:
    """After the browser uploaded the file: check it came in with this ticket and add it to the
    media library. 422 on ``public_id`` for a file that isn't this ticket's; 415 never (a file
    over a limit is a ``rejected`` ticket, with the reason); 409 for an expired ticket; 402
    quota_exceeded past the plan's daily upload caps."""
    settings = request.app.state.settings
    finished = await mcp_uploads.finish(
        session,
        _cloudinary(request),
        request.app.state.redis,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        plan=await current_plan(session),
        upload_id=upload_id,
        public_id=body.public_id,
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
