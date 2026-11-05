"""Media that AI apps bring in (C-165 phase B; docs/architecture/mcp/01-design.md §5): upload
tickets, the signed direct upload, the import from a public link, and finishing either into the
media library. The MCP tools (mcp/tools/media.py) and the drop page's routes
(api/v1/mcp_uploads.py) both use it, so there is one set of rules.

- **A ticket** (``mcp_uploads``) is a handle: a one-time permission to bring one file in within 30
  minutes. It is looked up in the caller's workspace on every use, so another workspace's ticket is
  "not found".
- **The signed upload** is Cloudinary's, for ``ws/{workspace_id}/post``. The ticket's tag
  ``mcp_upload_{id}`` is part of the signature, so the stored file carries it; finishing checks
  the tag, which proves the file came in with *this* ticket and not through any other signature.
- **The import** reads the link's headers here under the SEC-09 address rules (public addresses
  only, at every redirect), checks type and declared size, then has Cloudinary fetch the final
  address. No bytes pass through the API.
- **Finishing** registers the file with the library's own rules (``media_assets.register``: the
  workspace's folder, format, size, duration, the eager H.264 render), then marks the ticket. A
  file that breaks a rule is deleted from storage and the ticket says why (``rejected``).
- **Daily caps** (``mcp_uploads_daily``, ``mcp_upload_mb_daily``) count files that finished.

- **Cleanup** (C-167; 01-design.md §5.3): a ticket that never finished (waiting, expired or
  rejected, no media asset) and expired more than ``STALE_AFTER`` ago has the files carrying its
  tag deleted from storage, except any registered in the library, and then its row is deleted:
  it can't be finished, the daily caps count only finished files, and the AI app that asked
  stopped waiting a day ago. ``clean_stale`` does one ticket; the daily job is
  jobs/tasks/purge.clean_mcp_uploads.

Nothing here commits except ``media_assets.register``, which commits as it always has.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.errors import ApiError, FieldError
from socialhood.mcp import limits
from socialhood.media.cloudinary import (
    Cloudinary,
    CloudinaryError,
    ResourceType,
    workspace_folder,
)
from socialhood.media.purge import MediaPurger
from socialhood.models.mcp import McpUpload, UploadStatus
from socialhood.models.media import AssetPurpose, MediaAsset
from socialhood.models.publishing import IG_REEL_MAX_S, STORY_VIDEO_MAX_S, STORY_VIDEO_MIN_S
from socialhood.observability.logging import get_logger
from socialhood.repositories.base import scoped_delete
from socialhood.security import ssrf
from socialhood.services import media_assets
from socialhood.services.media_assets import IMAGE, MB, POST_VIDEO
from socialhood.services.scheduled_posts.rules import EXTRA_VIDEO_MAX_S

log = get_logger(__name__)

Kind = Literal["image", "video"]
TICKET_TTL = timedelta(minutes=30)
STALE_AFTER = timedelta(hours=24)  # after its expiry, an unfinished ticket's files are deleted
TAG_PREFIX = "mcp_upload_"
NOT_FOUND = "No upload with this id. Start a new one with start_media_upload."
EXPIRED = "This upload expired. Start a new one with start_media_upload."
NOT_YET = (
    "No file has arrived for this upload yet. Upload the file with the command or the upload "
    "page, then finish."
)
WRONG_TICKET = (
    "This file wasn't uploaded with this upload's command. Run the command start_media_upload "
    "gave and use the public_id it prints."
)
CLOUDINARY_OFF = "Uploads aren't set up yet."


def tag_of(upload_id: uuid.UUID) -> str:
    return f"{TAG_PREFIX}{upload_id}"


def limits_for(kind: Kind, *, post_video_max_mb: int) -> dict[str, Any]:
    """What each post kind accepts, from the publishing rules, so an AI app can trim a file
    before it uploads it (§5.3)."""
    if kind == "image":
        return {
            "formats": sorted(IMAGE.formats),
            "max_mb": IMAGE.max_bytes // MB,
            "note": "Instagram feed posts take 4:5 to 1.91:1; Stories 9:16.",
        }
    return {
        "formats": sorted(POST_VIDEO.formats),
        "max_mb": post_video_max_mb,
        "max_duration_s": {
            "reel": IG_REEL_MAX_S,
            "story": f"{STORY_VIDEO_MIN_S} to {STORY_VIDEO_MAX_S}",
            "carousel_item": EXTRA_VIDEO_MAX_S,
        },
        "note": (
            "Any video codec is accepted and re-encoded to H.264 for Instagram. Reels up to 15 "
            "minutes, Stories 3 to 60 seconds, videos in a carousel up to 90 seconds."
        ),
    }


def check_early(
    kind: Kind, size: int | None, duration_s: float | None, *, post_video_max_mb: int
) -> None:
    """422 when the stated size or length is already over a limit, before anything is uploaded."""
    errors: list[FieldError] = []
    cap = (IMAGE.max_bytes if kind == "image" else post_video_max_mb * MB) // MB
    if size is not None and size > cap * MB:
        errors.append(
            FieldError(
                "bytes", f"{'Images' if kind == 'image' else 'Videos'} can be up to {cap} MB."
            )
        )
    if duration_s is not None:
        if kind == "image":
            errors.append(FieldError("duration_s", "An image has no duration."))
        elif duration_s > IG_REEL_MAX_S:
            errors.append(FieldError("duration_s", "Videos can be up to 15 minutes."))
    if errors:
        raise ApiError("validation_error", errors=errors)


@dataclass(frozen=True)
class Started:
    upload: McpUpload
    signature: dict[str, Any]  # the signed form fields and upload_url


def effective_status(upload: McpUpload, now: datetime) -> UploadStatus:
    status = UploadStatus(upload.status)
    if status is UploadStatus.WAITING and upload.expires_at <= now:
        return UploadStatus.EXPIRED
    return status


async def get(session: AsyncSession, upload_id: uuid.UUID) -> McpUpload:
    upload = (
        await session.scalars(select(McpUpload).where(McpUpload.id == upload_id))
    ).one_or_none()
    if upload is None:
        raise ApiError("not_found", NOT_FOUND)
    return upload


def signature(cloudinary: Cloudinary, workspace_id: uuid.UUID, upload: McpUpload) -> dict[str, Any]:
    """Fresh signed fields for a ticket's one file, valid while Cloudinary accepts the
    timestamp (about an hour)."""
    try:
        return cloudinary.upload_signature(
            folder=workspace_folder(workspace_id, AssetPurpose.POST.value),
            resource_type=resource_type_of(upload.kind),
            tags=tag_of(upload.id),
            allowed_formats=media_assets.accepted_formats(
                AssetPurpose.POST.value, resource_type_of(upload.kind)
            ),
        )
    except CloudinaryError as error:
        raise ApiError("service_unavailable", CLOUDINARY_OFF) from error


def resource_type_of(kind: str) -> ResourceType:
    return "image" if kind == "image" else "video"


def _daily_words(name: str, limit: int | None) -> str:
    what = "files" if name == limits.UPLOADS else "megabytes"
    return (
        f"Your plan includes {limit:,} {what} uploaded from AI apps a day. "
        "They reset at midnight UTC."
    )


async def check_daily(redis: Redis, plan: str, workspace_id: uuid.UUID, now: datetime) -> None:
    from socialhood.billing.plans import entitlement

    for name in (limits.UPLOADS, limits.UPLOAD_MB):
        await limits.check(
            redis, plan, name, workspace_id, now, words=_daily_words(name, entitlement(plan, name))
        )


async def start(
    session: AsyncSession,
    cloudinary: Cloudinary,
    redis: Redis,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
    kind: Kind,
    size: int | None,
    duration_s: float | None,
    post_video_max_mb: int,
    now: datetime,
) -> Started:
    check_early(kind, size, duration_s, post_video_max_mb=post_video_max_mb)
    await check_daily(redis, plan, workspace_id, now)
    upload = McpUpload(
        id=uuid.uuid4(),
        user_id=user_id,
        kind=kind,
        status=UploadStatus.WAITING.value,
        expires_at=now + TICKET_TTL,
    )
    session.add(upload)
    await session.flush()
    return Started(upload, signature(cloudinary, workspace_id, upload))


@dataclass(frozen=True)
class Finished:
    upload: McpUpload
    asset: MediaAsset | None  # None when the file was rejected (``upload.reason`` says why)
    duplicate: bool = False  # the ticket was already finished


async def _reject(
    session: AsyncSession, cloudinary: Cloudinary, upload: McpUpload, public_id: str, reason: str
) -> Finished:
    upload.status = UploadStatus.REJECTED.value
    upload.reason = reason[:300]
    upload.public_id = public_id
    await session.flush()
    try:  # best effort: an unregistered file is not kept
        await cloudinary.destroy(public_id, resource_type_of(upload.kind))
    except Exception as error:
        log.warning("mcp_upload_destroy_failed", error=type(error).__name__)
    return Finished(upload, None)


async def finish(
    session: AsyncSession,
    cloudinary: Cloudinary,
    redis: Redis,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
    upload_id: uuid.UUID,
    public_id: str | None,
    post_video_max_mb: int,
    now: datetime,
) -> Finished:
    """Register the ticket's file in the library. A finished ticket returns its asset again; an
    expired one is 409; a file that breaks a rule is rejected (the result says why) and deleted."""
    upload = await get(session, upload_id)
    status = effective_status(upload, now)
    if status is UploadStatus.UPLOADED and upload.media_asset_id is not None:
        asset = await session.get(MediaAsset, upload.media_asset_id)
        return Finished(upload, asset, duplicate=True)
    if status is UploadStatus.EXPIRED:
        raise ApiError("conflict", EXPIRED)
    if status is UploadStatus.REJECTED:
        raise ApiError(
            "conflict", f"This upload was rejected: {upload.reason or 'the file broke a rule'}."
        )
    wanted = public_id or upload.public_id
    if not wanted:
        raise ApiError("conflict", NOT_YET)
    media_assets.purpose_of(wanted, workspace_id)  # the workspace's own post folder, else 422
    kind = resource_type_of(upload.kind)
    try:
        stored = await cloudinary.get_resource(wanted, kind)
    except CloudinaryError as error:
        raise ApiError("service_unavailable", "Couldn't check the upload. Try again.") from error
    if stored is None:
        raise ApiError(
            "validation_error",
            errors=[FieldError("public_id", "Upload not found. Upload the file again.")],
        )
    if tag_of(upload.id) not in stored.tags:
        raise ApiError("validation_error", errors=[FieldError("public_id", WRONG_TICKET)])
    return await _complete(
        session,
        cloudinary,
        redis,
        upload=upload,
        public_id=wanted,
        size=stored.bytes,
        workspace_id=workspace_id,
        user_id=user_id,
        plan=plan,
        post_video_max_mb=post_video_max_mb,
        now=now,
    )


async def _complete(
    session: AsyncSession,
    cloudinary: Cloudinary,
    redis: Redis,
    *,
    upload: McpUpload,
    public_id: str,
    size: int,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
    post_video_max_mb: int,
    now: datetime,
) -> Finished:
    await check_daily(redis, plan, workspace_id, now)
    megabytes = max(1, -(-size // MB))
    held: list[limits.Reservation] = []
    try:
        held.append(await limits.reserve(redis, plan, limits.UPLOADS, workspace_id, now))
        held.append(
            await limits.reserve(redis, plan, limits.UPLOAD_MB, workspace_id, now, amount=megabytes)
        )
        asset = await media_assets.register(
            session,
            cloudinary,
            workspace_id=workspace_id,
            user_id=user_id,
            public_id=public_id,
            resource_type=resource_type_of(upload.kind),
            post_video_max_mb=post_video_max_mb,
        )
    except ApiError as error:
        for reservation in held:
            await reservation.refund()
        if error.code == "unsupported_media":
            return await _reject(
                session, cloudinary, upload, public_id, error.detail or "The file isn't supported."
            )
        raise
    upload.status = UploadStatus.UPLOADED.value
    upload.public_id = public_id
    upload.media_asset_id = asset.id
    upload.reason = None
    await session.flush()
    return Finished(upload, asset)


# ---------------------------------------------------------------- import from a public link

IMPORT_URL_MAX = 500
IMPORT_QUERY_MAX = 200
IMPORT_TOO_LONG = "This link is too long to import. Upload the file with start_media_upload."
IMPORT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "video/mp4",
    "video/quicktime",
}
NOT_MEDIA = (
    "This link isn't a JPEG, PNG, WEBP or HEIC image or an MP4 or MOV video. Use a direct link "
    "to the file, not a web page."
)
# Pages that show a file, not the file: the link must be to the bytes (Drive and Dropbox need
# their "direct download" forms).
PROBE_FAILED = "Couldn't reach this link."


def _refused(error: ssrf.FetchError) -> ApiError:
    code = "service_unavailable" if error.retryable else "validation_error"
    if code == "validation_error":
        return ApiError(code, errors=[FieldError("url", error.message)])
    return ApiError(code, error.message)


def check_import_link(url: str) -> str:
    """The host of a link that may be imported, with no network: a preview must not reach it. The
    length is limited because the address itself reaches whoever runs that host, so it isn't a
    place for much text. Drive and Dropbox direct links fit; a long signed link doesn't."""
    if not url.lower().startswith("https://"):
        raise ApiError(
            "validation_error", errors=[FieldError("url", "Use an https:// link to the file.")]
        )
    try:
        parsed = ssrf.check_url(url)
    except ssrf.FetchError as error:
        raise _refused(error) from error
    if len(url) > IMPORT_URL_MAX or len(parsed.query) > IMPORT_QUERY_MAX:
        raise ApiError("validation_error", errors=[FieldError("url", IMPORT_TOO_LONG)])
    return parsed.host


async def import_url(
    session: AsyncSession,
    cloudinary: Cloudinary,
    redis: Redis,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
    url: str,
    kind: Kind | None,
    post_video_max_mb: int,
    now: datetime,
    resolve: ssrf.Resolver | None = None,
) -> Finished:
    """Bring a file in from a public link. Order matters: the address rules and the declared type
    and size first (nothing is stored for a refused link), then storage fetches the final
    address, then the library's rules (format, size and length as stored)."""
    await check_daily(redis, plan, workspace_id, now)
    check_import_link(url)
    try:
        probed = await ssrf.probe(url, resolve=resolve)
    except ssrf.FetchError as error:
        raise _refused(error) from error
    if not probed.url.lower().startswith("https://"):
        raise ApiError(
            "validation_error", errors=[FieldError("url", "The link redirects away from https.")]
        )
    if probed.content_type not in IMPORT_TYPES:
        raise ApiError("unsupported_media", NOT_MEDIA)
    found: Kind = "image" if probed.content_type.startswith("image/") else "video"
    if kind is not None and kind != found:
        raise ApiError(
            "validation_error",
            errors=[
                FieldError("kind", f"This link is {'an image' if found == 'image' else 'a video'}.")
            ],
        )
    try:
        check_early(found, probed.content_length, None, post_video_max_mb=post_video_max_mb)
    except ApiError as error:
        raise ApiError(
            "unsupported_media", error.errors[0].message if error.errors else None
        ) from error
    upload = McpUpload(
        id=uuid.uuid4(),
        user_id=user_id,
        kind=found,
        status=UploadStatus.WAITING.value,
        expires_at=now + TICKET_TTL,
    )
    session.add(upload)
    await session.flush()
    try:
        stored = await cloudinary.upload(
            probed.url,
            folder=workspace_folder(workspace_id, AssetPurpose.POST.value),
            resource_type=resource_type_of(found),
            tags=tag_of(upload.id),
        )
    except CloudinaryError as error:
        log.warning("mcp_import_failed", reason=str(error))
        upload.status = UploadStatus.REJECTED.value
        upload.reason = "Amplychat's storage couldn't fetch this link."
        await session.flush()
        return Finished(upload, None)
    return await _complete(
        session,
        cloudinary,
        redis,
        upload=upload,
        public_id=stored.public_id,
        size=stored.bytes,
        workspace_id=workspace_id,
        user_id=user_id,
        plan=plan,
        post_video_max_mb=post_video_max_mb,
        now=now,
    )


# ---------------------------------------------------------------- cleanup (C-167)


async def clean_stale(session: AsyncSession, media: MediaPurger, upload_id: uuid.UUID) -> int:
    """Delete an unfinished ticket's files from storage (never one the library holds), then the
    ticket, in the current workspace. Returns the files deleted; 0 for a ticket that finished or
    is gone. Raises CloudinaryError when storage can't be reached (the row stays, so the next
    day's run tries again). The caller commits."""
    ticket = await session.get(McpUpload, upload_id)
    if ticket is None or ticket.status == UploadStatus.UPLOADED or ticket.media_asset_id:
        return 0
    workspace_id = require_workspace()
    files = await media.list_tagged(workspace_id, tag_of(ticket.id))
    doomed = files
    if files:
        registered = set(
            await session.scalars(
                select(MediaAsset.public_id).where(
                    MediaAsset.public_id.in_([f.public_id for f in files])
                )
            )
        )
        doomed = [f for f in files if f.public_id not in registered]
        if doomed:
            await media.delete_files(workspace_id, doomed)
    await session.execute(scoped_delete(McpUpload, id=ticket.id))
    return len(doomed)
