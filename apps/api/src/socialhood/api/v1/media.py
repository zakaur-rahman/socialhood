"""Media uploads (T3.7; TR-MED-01, TR-MED-02): a signature for a direct browser upload to
Cloudinary, then registration of the uploaded asset after checking its folder and limits. The
media library (FR-PUB-13, T7.1) lists the uploads for posts.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request

from socialhood.auth.deps import AnyMember, Session
from socialhood.media.cloudinary import Cloudinary
from socialhood.schemas.inbox import (
    MediaAssetCreate,
    MediaAssetOut,
    UploadSignature,
    UploadSignatureRequest,
)
from socialhood.schemas.publishing import MediaAssetList
from socialhood.services import media_assets
from socialhood.services.scheduled_posts import library

router = APIRouter(prefix="/v1/w/{wid}", tags=["media"])


def _cloudinary(request: Request) -> Cloudinary:
    return Cloudinary(request.app.state.http, request.app.state.settings)


@router.post("/media-assets/upload-signature", operation_id="create_upload_signature")
async def create_upload_signature(
    request: Request, body: UploadSignatureRequest, ctx: AnyMember, session: Session
) -> UploadSignature:
    """Parameters for uploading one file from the browser into ws/{workspace_id}/{purpose}."""
    return media_assets.upload_signature(
        _cloudinary(request),
        ctx.workspace_id,
        purpose=body.purpose,
        resource_type=body.resource_type,
    )


@router.post("/media-assets", status_code=201, operation_id="register_media_asset")
async def register_media_asset(
    request: Request, body: MediaAssetCreate, ctx: AnyMember, session: Session
) -> MediaAssetOut:
    """Register an uploaded file: it must be in this workspace's folder (else 422 on public_id)
    and within the limits (else 415 unsupported_media). Registering it again returns it."""
    asset = await media_assets.register(
        session,
        _cloudinary(request),
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        public_id=body.public_id,
        resource_type=body.resource_type,
    )
    return media_assets.asset_out(asset)


@router.get("/media-assets", operation_id="list_media_assets")
async def list_media_assets(
    ctx: AnyMember,
    session: Session,
    asset_type: Annotated[Literal["image", "video"] | None, Query(alias="type")] = None,
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 40,
) -> MediaAssetList:
    """The media library (FR-PUB-13): images and videos uploaded for posts, newest first,
    narrowed by type and by upload date (``since`` and ``until`` in the workspace time zone, both
    included; 422 on ``until`` before ``since``)."""
    return await library.list_library(
        session,
        asset_type=asset_type,
        since=since,
        until=until,
        cursor=cursor,
        limit=limit,
        timezone=ctx.workspace.timezone,
    )
