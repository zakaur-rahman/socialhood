"""Uploaded media (T3.7; TR-MED-01, TR-MED-02, FR-INB-08).

The browser uploads straight to Cloudinary with a signature for ``ws/{workspace_id}/{purpose}``,
then registers the upload. Registration reads the asset back with the Admin API, checks it sits in
this workspace's folder and within the limits, and stores a ``media_assets`` row. Messages and
posts refer to assets by id, so a workspace can only ever send its own files.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.media.cloudinary import (
    Cloudinary,
    CloudinaryError,
    ResourceType,
    StoredResource,
    workspace_folder,
)
from socialhood.models.media import AssetPurpose, MediaAsset
from socialhood.observability.logging import get_logger
from socialhood.schemas.inbox import MediaAssetOut, UploadSignature

log = get_logger(__name__)

MB = 1024 * 1024
# Purposes a client may upload for; ``inbound`` is written only by the server (TR-MED-03).
CLIENT_PURPOSES = frozenset({AssetPurpose.POST, AssetPurpose.MESSAGE, AssetPurpose.KNOWLEDGE})
# A signed upload's public id is the signed folder plus Cloudinary's random name (raw files keep
# their extension), so anything else did not come from our signature.
_PUBLIC_ID = re.compile(
    r"^ws/(?P<wid>[0-9a-f-]{36})/(?P<purpose>[a-z]+)/[A-Za-z0-9_-]+(?:\.[A-Za-z0-9]{1,8})?$"
)

MediaKind = Literal["image", "video", "document"]
AttachmentType = Literal["image", "video", "file"]


@dataclass(frozen=True)
class Limit:
    """TR-MED-02 (verify against Instagram's current specs, T0.9)."""

    kind: MediaKind
    label: str
    formats: frozenset[str]
    max_bytes: int
    max_duration_s: float | None = None


IMAGE = Limit("image", "Images", frozenset({"jpg", "jpeg", "png", "webp", "heic"}), 8 * MB)
VIDEO = Limit("video", "Videos", frozenset({"mp4", "mov"}), 100 * MB, max_duration_s=90)
DOCUMENT = Limit("document", "Documents", frozenset({"pdf"}), 20 * MB)
UNSUPPORTED = "Use JPEG, PNG, WEBP or HEIC images, MP4 or MOV video up to 90 seconds, or PDF files."

MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "pdf": "application/pdf",
}

# What platforms fetch: images as JPEG and video as H.264 MP4 (TR-MED-02), whatever was uploaded.
IMAGE_DELIVERY = "f_jpg,q_auto,w_1440,c_limit"
VIDEO_DELIVERY = "vc_h264,ac_aac,f_mp4"


# ---------------------------------------------------------------- upload and registration


def upload_signature(
    cloudinary: Cloudinary, workspace_id: uuid.UUID, *, purpose: str, resource_type: ResourceType
) -> UploadSignature:
    try:
        params = cloudinary.upload_signature(
            folder=workspace_folder(workspace_id, purpose), resource_type=resource_type
        )
    except CloudinaryError as error:
        raise ApiError("service_unavailable", "Uploads aren't set up yet.") from error
    return UploadSignature.model_validate(params)


def purpose_of(public_id: str, workspace_id: uuid.UUID) -> str:
    """The purpose folder of an upload in this workspace's folder, else a 422 on public_id."""
    match = _PUBLIC_ID.fullmatch(public_id)
    if match is None or match["wid"] != str(workspace_id):
        raise _field_error("This file wasn't uploaded to this workspace. Upload it again.")
    if match["purpose"] not in CLIENT_PURPOSES:
        raise _field_error("This file wasn't uploaded for a message, post or knowledge.")
    return match["purpose"]


def check_limits(resource: StoredResource) -> Limit:
    """The limit the asset falls under; 415 unsupported_media when it breaks one."""
    fmt = file_format(resource.format, resource.public_id)
    if resource.resource_type == "image" and fmt in IMAGE.formats:
        limit = IMAGE
    elif resource.resource_type == "video" and fmt in VIDEO.formats:
        limit = VIDEO
    elif fmt in DOCUMENT.formats:
        limit = DOCUMENT
    else:
        raise ApiError("unsupported_media", UNSUPPORTED)
    if resource.bytes > limit.max_bytes:
        raise ApiError(
            "unsupported_media", f"{limit.label} can be up to {limit.max_bytes // MB} MB."
        )
    if (
        limit.max_duration_s is not None
        and resource.duration_s is not None
        and resource.duration_s > limit.max_duration_s
    ):
        raise ApiError(
            "unsupported_media", f"{limit.label} can be up to {limit.max_duration_s:.0f} seconds."
        )
    return limit


async def register(
    session: AsyncSession,
    cloudinary: Cloudinary,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    public_id: str,
    resource_type: ResourceType,
) -> MediaAsset:
    """Store an uploaded asset once (registering it again returns the same row) and commit."""
    purpose = purpose_of(public_id, workspace_id)
    existing = await find_by_public_id(session, public_id)
    if existing is not None:
        return existing
    resource = await _lookup(cloudinary, public_id, resource_type)
    check_limits(resource)
    asset = MediaAsset(
        public_id=public_id,
        resource_type=resource.resource_type,
        purpose=purpose,
        format=file_format(resource.format, resource.public_id),
        original_filename=None,
        secure_url=resource.secure_url,
        bytes=resource.bytes,
        width=resource.width,
        height=resource.height,
        duration_s=resource.duration_s,
        created_by_user_id=user_id,
    )
    try:
        async with session.begin_nested():
            session.add(asset)
            await session.flush()
    except IntegrityError:
        # Registered twice at once: the other request stored it.
        existing = await find_by_public_id(session, public_id)
        if existing is None:
            raise
        return existing
    await session.commit()
    return asset


async def _lookup(
    cloudinary: Cloudinary, public_id: str, resource_type: ResourceType
) -> StoredResource:
    try:
        resource = await cloudinary.get_resource(public_id, resource_type)
    except CloudinaryError as error:
        log.warning("media_lookup_failed", reason=str(error))
        raise ApiError("service_unavailable", "Couldn't check the upload. Try again.") from error
    if resource is None:
        raise _field_error("Upload not found. Upload the file again.")
    return resource


def asset_out(asset: MediaAsset) -> MediaAssetOut:
    out = MediaAssetOut.model_validate(asset)
    # Cloudinary reports a format, not a MIME type.
    return out.model_copy(update={"mime_type": MIME_TYPES.get((asset.format or "").lower())})


# ---------------------------------------------------------------- lookups and attachments


async def find_by_public_id(session: AsyncSession, public_id: str) -> MediaAsset | None:
    return (
        await session.scalars(select(MediaAsset).where(MediaAsset.public_id == public_id))
    ).one_or_none()


async def load(session: AsyncSession, asset_ids: Sequence[uuid.UUID]) -> list[MediaAsset]:
    """This workspace's assets in the order given; 422 when any id is unknown here."""
    if not asset_ids:
        return []
    rows = await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(set(asset_ids))))
    by_id = {a.id: a for a in rows.all()}
    missing = [i for i in asset_ids if i not in by_id]
    if missing:
        raise ApiError(
            "validation_error",
            errors=[FieldError("attachment_asset_ids", "Attachment not found. Upload it again.")],
        )
    return [by_id[i] for i in asset_ids]


def attachment_type(asset: MediaAsset) -> AttachmentType:
    fmt = file_format(asset.format, asset.public_id)
    if asset.resource_type == "image" and fmt not in DOCUMENT.formats:
        return "image"
    if asset.resource_type == "video":
        return "video"
    return "file"


def attachment(asset: MediaAsset) -> dict[str, Any]:
    """A message attachment (§5.10 Attachment) plus what the send job needs: the delivery URL,
    and the platform id of the part once it is sent."""
    fmt = file_format(asset.format, asset.public_id)
    kind = attachment_type(asset)
    return {
        "id": str(asset.id),
        "type": kind,
        "url": asset.secure_url,
        "mime_type": MIME_TYPES.get(fmt or ""),
        "size_bytes": asset.bytes,
        "width": asset.width,
        "height": asset.height,
        "duration_s": asset.duration_s,
        "filename": asset.original_filename or _filename(asset.public_id, fmt),
        "thumbnail_url": None,
        "asset_id": str(asset.id),
        "public_id": asset.public_id,
        "send_url": delivery_url(asset.secure_url or "", kind),
        "send_mime_type": _send_mime(kind, fmt),
        "platform_message_id": None,
    }


def delivery_url(secure_url: str, kind: AttachmentType) -> str:
    if kind == "image":
        return _transformed(secure_url, IMAGE_DELIVERY, "jpg")
    if kind == "video":
        return _transformed(secure_url, VIDEO_DELIVERY, "mp4")
    return secure_url


def file_format(fmt: str | None, public_id: str) -> str | None:
    if fmt:
        return fmt.lower()
    name = public_id.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else None


def _transformed(url: str, transformation: str, extension: str) -> str:
    head, sep, tail = url.partition("/upload/")
    if not sep:
        return url
    last = tail.rsplit("/", 1)[-1]
    stem = tail[: -(len(last.rsplit(".", 1)[-1]) + 1)] if "." in last else tail
    return f"{head}/upload/{transformation}/{stem}.{extension}"


def _send_mime(kind: AttachmentType, fmt: str | None) -> str | None:
    if kind == "image":
        return "image/jpeg"
    if kind == "video":
        return "video/mp4"
    return MIME_TYPES.get(fmt or "")


def _filename(public_id: str, fmt: str | None) -> str:
    name = public_id.rsplit("/", 1)[-1]
    if fmt and not name.lower().endswith(f".{fmt}"):
        return f"{name}.{fmt}"
    return name


def _field_error(message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError("public_id", message)])
