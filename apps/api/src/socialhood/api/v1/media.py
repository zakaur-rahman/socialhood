"""Media uploads (T3.7; TR-MED-01, TR-MED-02): a signature for a direct browser upload to
Cloudinary, then registration of the uploaded asset after checking its folder and limits."""

from __future__ import annotations

from fastapi import APIRouter, Request

from socialhood.auth.deps import AnyMember, Session
from socialhood.media.cloudinary import Cloudinary
from socialhood.schemas.inbox import (
    MediaAssetCreate,
    MediaAssetOut,
    UploadSignature,
    UploadSignatureRequest,
)
from socialhood.services import media_assets

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
