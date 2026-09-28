"""Media uploads (T3.7; TR-MED-01, TR-MED-02): a signature for a direct browser upload to
Cloudinary, then registration of the uploaded asset after checking its folder and limits.

The signatures below are the P3 contract; T3.7 implements the bodies.
"""

from __future__ import annotations

from fastapi import APIRouter

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.inbox import (
    MediaAssetCreate,
    MediaAssetOut,
    UploadSignature,
    UploadSignatureRequest,
)

router = APIRouter(prefix="/v1/w/{wid}", tags=["media"])


# Stub until T3.7 lands: the tenancy suite skips x-pending routes. Delete this and the
# openapi_extra arguments when implementing.
PENDING = {"x-pending": "T3.7"}


@router.post(
    "/media-assets/upload-signature", operation_id="create_upload_signature", openapi_extra=PENDING
)
async def create_upload_signature(
    body: UploadSignatureRequest, ctx: AnyMember, session: Session
) -> UploadSignature:
    raise NotImplementedError("T3.7")


@router.post(
    "/media-assets", status_code=201, operation_id="register_media_asset", openapi_extra=PENDING
)
async def register_media_asset(
    body: MediaAssetCreate, ctx: AnyMember, session: Session
) -> MediaAssetOut:
    raise NotImplementedError("T3.7")
