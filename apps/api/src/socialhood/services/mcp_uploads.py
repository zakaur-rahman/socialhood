"""Media that AI apps bring in (C-165 phase B; docs/architecture/mcp/01-design.md §5): upload
tickets, the signed direct upload, the import from a public link, and finishing either into the
media library. The MCP tools (mcp/tools/media.py) and the drop page's routes
(api/v1/mcp_uploads.py) both use it, so there is one set of rules.

- **A ticket** (``mcp_uploads``) is a handle: a one-time permission to bring one file in within 30
  minutes. It is looked up in the caller's workspace on every use, so another workspace's ticket is
  "not found".
- **The signed upload** is Cloudinary's, for one file: ``ws/{workspace_id}/post/{ticket id}``
  (``file_id``, kept on the ticket as ``public_id``). The name is part of the signature, so
  sending the signature again replaces that one file instead of storing another, and finishing
  reads the name from the ticket, never from the caller. The tag ``mcp_upload_{id}`` is signed
  too: a ticket made before the name was signed has no ``public_id`` and is found by its tag.
- **The import** reads the link's headers here under the SEC-09 address rules (public addresses
  only, at every redirect), checks type and declared size, then has Cloudinary fetch the final
  address. No bytes pass through the API.
- **Finishing** registers the file with the library's own rules (``media_assets.register``: the
  workspace's folder, format, size, duration, the eager H.264 render), then marks the ticket. A
  file that breaks a rule is deleted from storage and the ticket says why (``rejected``).
- **Daily caps** (``mcp_uploads_daily``, ``mcp_upload_mb_daily``) count files that finished. A
  workspace holds at most ``OPEN_MAX`` unfinished tickets, so what waits in storage uncounted
  is bounded too.

- **YouTube tickets** (C-196, ``kind`` ``youtube``): made by prepare_youtube_upload for a post's
  YouTube target, valid as long as its upload session (24 hours). The upload page sends the file
  straight to YouTube's session (the target's), never to storage, and completes through the same
  service as the composer (services/post_publishing/youtube_direct.complete). Nothing to clean in
  storage.

- **Cleanup** (C-167; 01-design.md §5.3): a ticket that never finished (waiting, expired or
  rejected, no media asset) and expired more than ``STALE_AFTER`` ago has its one file deleted
  from storage (as an image, a video and a raw file: a signature doesn't fix which), unless the
  library holds it, and then its row is deleted:
  it can't be finished, the daily caps count only finished files, and the AI app that asked
  stopped waiting a day ago. ``clean_stale`` does one ticket; the daily job is
  jobs/tasks/purge.clean_mcp_uploads.

Nothing here commits except ``media_assets.register``, which commits as it always has, and
``import_url``, which commits its ticket before storage fetches the link.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import quota_error
from socialhood.billing.plans import entitlement
from socialhood.db.tenancy import require_workspace
from socialhood.errors import ApiError, FieldError
from socialhood.mcp import limits
from socialhood.media.cloudinary import (
    Cloudinary,
    CloudinaryError,
    ResourceType,
    StoredResource,
    workspace_folder,
)
from socialhood.media.purge import RESOURCE_TYPES, MediaPurger, StoredFile
from socialhood.models.mcp import McpUpload, UploadStatus
from socialhood.models.media import AssetPurpose, MediaAsset
from socialhood.models.publishing import IG_REEL_MAX_S, STORY_VIDEO_MAX_S, STORY_VIDEO_MIN_S
from socialhood.observability.logging import get_logger
from socialhood.repositories.base import scoped_delete
from socialhood.security import ssrf
from socialhood.services import media_assets
from socialhood.services.media_assets import IMAGE, MB, POST_VIDEO
from socialhood.services.scheduled_posts.rules import EXTRA_VIDEO_MAX_S
from socialhood.settings import Settings

log = get_logger(__name__)

Kind = Literal["image", "video"]
YOUTUBE = "youtube"
NOT_FOR_YOUTUBE = "This upload goes straight to YouTube. Check it with get_youtube_upload_status."
TICKET_TTL = timedelta(minutes=30)
STALE_AFTER = timedelta(hours=24)  # after its expiry, an unfinished ticket's files are deleted
TAG_PREFIX = "mcp_upload_"
NOT_FOUND = "No upload with this id. Start a new one with start_media_upload."
EXPIRED = "This upload expired. Start a new one with start_media_upload."
NOT_YET = (
    "No file has arrived for this upload yet. Upload the file with the command or the upload "
    "page, then finish."
)
CLOUDINARY_OFF = "Uploads aren't set up yet."
OPEN_MAX = 20  # unfinished tickets a workspace may hold: each can keep a file in storage
TOO_MANY_OPEN = (
    f"{OPEN_MAX} uploads were started here and never finished. Finish one of them, or try again "
    "tomorrow, when unfinished uploads are cleared."
)


def tag_of(upload_id: uuid.UUID) -> str:
    return f"{TAG_PREFIX}{upload_id}"


def file_id(workspace_id: uuid.UUID, upload_id: uuid.UUID) -> str:
    """The one file a ticket can bring in: its ``public_id`` in storage."""
    return f"{workspace_folder(workspace_id, AssetPurpose.POST.value)}/{upload_id.hex}"


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


async def get(
    session: AsyncSession, upload_id: uuid.UUID, *, for_update: bool = False
) -> McpUpload:
    statement = select(McpUpload).where(McpUpload.id == upload_id)
    if for_update:
        statement = statement.with_for_update()
    upload = (await session.scalars(statement)).one_or_none()
    if upload is None:
        raise ApiError("not_found", NOT_FOUND)
    return upload


def signature(cloudinary: Cloudinary, workspace_id: uuid.UUID, upload: McpUpload) -> dict[str, Any]:
    """Fresh signed fields for a ticket's one file (``file_id``), valid while Cloudinary accepts
    the timestamp (about an hour)."""
    try:
        return cloudinary.upload_signature(
            folder=workspace_folder(workspace_id, AssetPurpose.POST.value),
            resource_type=resource_type_of(upload.kind),
            tags=tag_of(upload.id),
            public_id=upload.id.hex,
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
    for name in (limits.UPLOADS, limits.UPLOAD_MB):
        await limits.check(
            redis, plan, name, workspace_id, now, words=_daily_words(name, entitlement(plan, name))
        )


async def _check_open(session: AsyncSession) -> None:
    waiting = await session.scalar(
        select(func.count())
        .select_from(McpUpload)
        .where(McpUpload.status == UploadStatus.WAITING.value)
    )
    if (waiting or 0) >= OPEN_MAX:
        raise ApiError("conflict", TOO_MANY_OPEN)


async def youtube_ticket(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    target_id: uuid.UUID,
    expires_at: datetime,
) -> McpUpload:
    """A waiting ``youtube`` ticket for a post's YouTube target (C-196), flushed: the upload page's
    one-time link. It expires with the target's upload session."""
    await _check_open(session)
    upload = McpUpload(
        user_id=user_id,
        kind=YOUTUBE,
        status=UploadStatus.WAITING.value,
        scheduled_post_target_id=target_id,
        expires_at=expires_at,
    )
    session.add(upload)
    await session.flush()
    return upload


async def _ticket(
    session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, kind: Kind, now: datetime
) -> McpUpload:
    """A new waiting ticket, flushed; 409 when the workspace already holds ``OPEN_MAX`` that
    never finished (the daily cleanup clears them)."""
    await _check_open(session)
    upload_id = uuid.uuid4()
    upload = McpUpload(
        id=upload_id,
        user_id=user_id,
        kind=kind,
        status=UploadStatus.WAITING.value,
        public_id=file_id(workspace_id, upload_id),
        expires_at=now + TICKET_TTL,
    )
    session.add(upload)
    await session.flush()
    return upload


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
    upload = await _ticket(session, workspace_id=workspace_id, user_id=user_id, kind=kind, now=now)
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
    post_video_max_mb: int,
    now: datetime,
) -> Finished:
    """Register the ticket's file in the library. A finished ticket returns its asset again; an
    expired one is 409; a file that breaks a rule is rejected (the result says why) and deleted.
    The row is locked, so two finishes at once count the daily caps once."""
    upload = await get(session, upload_id, for_update=True)
    if upload.kind == YOUTUBE:
        raise ApiError("conflict", NOT_FOR_YOUTUBE)
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
    if upload.public_id is None:  # made before the file's name was signed: its time has passed
        raise ApiError("conflict", EXPIRED)
    # ``register`` commits, which ends the lock: a finish that ran at the same moment, or one
    # that failed after it, has registered the file and counted the caps already.
    registered = await media_assets.find_by_public_id(session, upload.public_id)
    if registered is not None:
        upload.status = UploadStatus.UPLOADED.value
        upload.media_asset_id = registered.id
        await session.flush()
        return Finished(upload, registered, duplicate=True)
    try:
        stored = await cloudinary.get_resource(upload.public_id, resource_type_of(upload.kind))
    except CloudinaryError as error:
        raise ApiError("service_unavailable", "Couldn't check the upload. Try again.") from error
    if stored is None:
        raise ApiError("conflict", NOT_YET)
    return await _complete(
        session,
        cloudinary,
        redis,
        upload=upload,
        stored=stored,
        workspace_id=workspace_id,
        user_id=user_id,
        plan=plan,
        post_video_max_mb=post_video_max_mb,
        now=now,
    )


def _megabytes(size: int) -> int:
    return max(1, -(-size // MB))


async def _complete(
    session: AsyncSession,
    cloudinary: Cloudinary,
    redis: Redis,
    *,
    upload: McpUpload,
    stored: StoredResource,  # the ticket's file, as storage holds it
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
    post_video_max_mb: int,
    now: datetime,
) -> Finished:
    public_id = file_id(workspace_id, upload.id)
    await check_daily(redis, plan, workspace_id, now)
    held: list[limits.Reservation] = []
    try:
        held.append(await limits.reserve(redis, plan, limits.UPLOADS, workspace_id, now))
        held.append(
            await limits.reserve(
                redis, plan, limits.UPLOAD_MB, workspace_id, now, amount=_megabytes(stored.bytes)
            )
        )
        asset = await media_assets.register(
            session,
            cloudinary,
            workspace_id=workspace_id,
            user_id=user_id,
            public_id=public_id,
            resource_type=resource_type_of(upload.kind),
            post_video_max_mb=post_video_max_mb,
            resource=stored,
        )
    except BaseException as error:  # nothing was registered, whatever failed: the day gets it back
        for reservation in held:
            await reservation.refund()
        if isinstance(error, ApiError) and error.code == "unsupported_media":
            return await _reject(
                session, cloudinary, upload, public_id, error.detail or "The file isn't supported."
            )
        raise
    upload.status = UploadStatus.UPLOADED.value
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
OWN_HOST = "This link is to Amplychat itself. Use a link to the file where it is hosted."


def _refused(error: ssrf.FetchError) -> ApiError:
    code = "service_unavailable" if error.retryable else "validation_error"
    if code == "validation_error":
        return ApiError(code, errors=[FieldError("url", error.message)])
    return ApiError(code, error.message)


def own_hosts(settings: Settings) -> frozenset[str]:
    """Amplychat's own API and app hosts: the API never fetches from itself (§5.1)."""
    urls = (settings.api_base_url, settings.web_base_url)
    hosts = (urlsplit(url).hostname for url in urls if url)
    return frozenset(host for host in hosts if host)


def check_import_link(url: str, own: Collection[str] = ()) -> str:
    """The host of a link that may be imported, with no network: a preview must not reach it. The
    length is limited because the address itself reaches whoever runs that host, so it isn't a
    place for much text. Drive and Dropbox direct links fit; a long signed link doesn't. A link
    to one of ``own`` (``own_hosts``) is refused."""
    if not url.lower().startswith("https://"):
        raise ApiError(
            "validation_error", errors=[FieldError("url", "Use an https:// link to the file.")]
        )
    try:
        parsed = ssrf.check_url(url)
    except ssrf.FetchError as error:
        raise _refused(error) from error
    if parsed.host.lower() in own:
        raise ApiError("validation_error", errors=[FieldError("url", OWN_HOST)])
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
    own: Collection[str] = (),
    resolve: ssrf.Resolver | None = None,
) -> Finished:
    """Bring a file in from a public link. Order matters: the address rules and the declared type
    and size first (nothing is stored for a refused link), then the ticket is committed, so
    whatever fails next leaves a ticket the cleanup finds, then storage fetches the final address
    into the ticket's file, then the library's rules (format, size and length as stored)."""
    await check_daily(redis, plan, workspace_id, now)
    check_import_link(url, own)
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
    limit = entitlement(plan, limits.UPLOAD_MB)
    if limit is not None and probed.content_length:
        left = limit - await limits.used(redis, limits.UPLOAD_MB, workspace_id, now)
        if _megabytes(probed.content_length) > left:  # refused before storage holds the file
            raise quota_error(limits.UPLOAD_MB, limit, _daily_words(limits.UPLOAD_MB, limit))
    upload = await _ticket(session, workspace_id=workspace_id, user_id=user_id, kind=found, now=now)
    await session.commit()
    try:
        stored = await cloudinary.upload(
            probed.url,
            folder=workspace_folder(workspace_id, AssetPurpose.POST.value),
            resource_type=resource_type_of(found),
            public_id=upload.id.hex,
            tags=tag_of(upload.id),
        )
    except (CloudinaryError, httpx.HTTPError) as error:
        # A timeout included: storage may still finish the fetch, into the ticket's own file.
        log.warning("mcp_import_failed", reason=str(error) or type(error).__name__)
        upload.status = UploadStatus.REJECTED.value
        upload.reason = "Amplychat's storage couldn't fetch this link."
        await session.flush()
        return Finished(upload, None)
    return await _complete(
        session,
        cloudinary,
        redis,
        upload=upload,
        stored=stored,
        workspace_id=workspace_id,
        user_id=user_id,
        plan=plan,
        post_video_max_mb=post_video_max_mb,
        now=now,
    )


# ---------------------------------------------------------------- cleanup (C-167)


async def clean_stale(session: AsyncSession, media: MediaPurger, upload_id: uuid.UUID) -> int:
    """Delete an unfinished ticket's file from storage (never one the library holds), then the
    ticket, in the current workspace. Returns the files it asked storage to delete; 0 for a
    ticket that finished or is gone. Raises CloudinaryError when storage can't be reached (the
    row stays, so the next day's run tries again). The caller commits."""
    ticket = await session.get(McpUpload, upload_id)
    if ticket is None or ticket.status == UploadStatus.UPLOADED or ticket.media_asset_id:
        return 0
    if ticket.kind == YOUTUBE:  # its file went to YouTube, never to storage
        await session.execute(scoped_delete(McpUpload, id=ticket.id))
        return 0
    workspace_id = require_workspace()
    if ticket.public_id is None:  # made before the file's name was signed: found by its tag
        files = await media.list_tagged(workspace_id, tag_of(ticket.id))
    else:  # one name; which of the three kinds holds it isn't known, and a missing one is fine
        files = [StoredFile(ticket.public_id, kind) for kind in RESOURCE_TYPES]
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
