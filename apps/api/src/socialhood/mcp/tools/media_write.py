"""Media uploads (01-design.md §5): start_media_upload, finish_media_upload and
import_media_from_url. No media bytes pass through the API.

- ``start_media_upload`` makes a ticket (``mcp_uploads``) and returns Cloudinary's signed upload
  as a ready ``curl`` command (for AI apps with a shell: Claude Code, Codex) and the link of the
  drop page (for everyone else: a member opens it and drops the file).
- ``finish_media_upload`` checks the file arrived with that ticket and registers it in the media
  library with the library's own rules.
- ``import_media_from_url`` takes a public https link: its address is checked here (public
  addresses only, at every redirect), then storage fetches it.

``get_media_upload`` (tools/media.py) reads a ticket, for the drop page flow. A ticket id is a
handle the model passes back, looked up in the connection's workspace like any other id. The
rules live in ``services/mcp_uploads.py``, shared with the drop page's routes.

These are draft-tier tools (``Access.DRAFT``): a file only lands in the media library, nothing is
public, and Free workspaces may upload for drafts.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import Field

from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import Access, WriteInput, WriteOutput, registry, tool
from socialhood.mcp.tools.common import moment
from socialhood.media.cloudinary import Cloudinary
from socialhood.models.identity import Role
from socialhood.models.mcp import UploadStatus
from socialhood.services import mcp_uploads


def cloudinary_of(call: ToolCall) -> Cloudinary:
    return Cloudinary(call.deps.http, call.settings)


class UploadedMedia(WriteOutput):
    upload_id: uuid.UUID
    status: str  # uploaded or rejected
    media_id: uuid.UUID | None = None  # what create_post takes
    type: str | None = None  # image, video
    format: str | None = None
    bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    problems: list[str] = Field(default_factory=list)  # why the file was rejected


def uploaded(finished: mcp_uploads.Finished, *, how: str, call: ToolCall) -> UploadedMedia:
    upload, asset = finished.upload, finished.asset
    if asset is None:
        reason = upload.reason or "The file was rejected."
        return UploadedMedia(
            summary=f"The file was rejected: {reason}",
            upload_id=upload.id,
            status=UploadStatus.REJECTED.value,
            problems=[reason],
        )
    if not finished.duplicate:
        call.note("media.uploaded", "media_asset", asset.id, source=how, kind=asset.resource_type)
    return UploadedMedia(
        summary=f"The {asset.resource_type} is in the media library",
        upload_id=upload.id,
        status=UploadStatus.UPLOADED.value,
        media_id=asset.id,
        type=asset.resource_type,
        format=asset.format,
        bytes=asset.bytes,
        width=asset.width,
        height=asset.height,
        duration_s=asset.duration_s,
    )


# ---------------------------------------------------------------- start_media_upload


class StartMediaUploadInput(WriteInput):
    kind: Literal["image", "video"]
    filename: str | None = Field(
        default=None, max_length=200, description="The local file's name, used in the command."
    )
    bytes: int | None = Field(
        default=None,
        ge=1,
        description="The file's size, so a file over the limit is refused early.",
    )
    duration_s: float | None = Field(
        default=None, gt=0, description="A video's length in seconds, checked against the limits."
    )


class StartedUpload(WriteOutput):
    upload_id: uuid.UUID
    kind: str
    expires_at: str
    curl: str  # run it where the file is; it prints JSON with a public_id
    upload_url: str
    fields: dict[str, Any]  # the same signed fields, for a client without curl
    upload_page_url: str | None = None  # a member opens it and drops the file
    limits: dict[str, Any]
    next_step: str


def curl_command(fields: dict[str, Any], url: str, filename: str | None) -> str:
    name = (filename or "FILE").replace("\\", "/").rsplit("/", 1)[-1]
    if any(c in name for c in '"$`'):
        name = "FILE"
    parts = [f'-F "file=@{name}"']
    for key in ("api_key", "timestamp", "folder", "tags", "signature"):
        if key in fields:
            parts.append(f'-F "{key}={fields[key]}"')
    return f"curl -sS {' '.join(parts)} {url}"


@tool(
    registry,
    name="start_media_upload",
    title="Start a media upload",
    description=(
        "Get a one-time way to bring an image or video into the media library, valid for 30 "
        "minutes: a curl command with signed fields, for an app that can run shell commands on "
        "the computer holding the file, and a link to an upload page where a member drops the "
        "file, for any other app. Then call finish_media_upload (command) or get_media_upload "
        "(page). The result lists the size and length limits for posts, Reels and Stories."
    ),
    input_model=StartMediaUploadInput,
    output_model=StartedUpload,
    scope="media:write",
    access=Access.DRAFT,
    min_role=Role.ADMIN,
)
async def start_media_upload(call: ToolCall, args: StartMediaUploadInput) -> StartedUpload:
    started = await mcp_uploads.start(
        call.session,
        cloudinary_of(call),
        call.redis,
        workspace_id=call.workspace.id,
        user_id=call.principal.user_id,
        plan=call.plan,
        kind=args.kind,
        size=args.bytes,
        duration_s=args.duration_s,
        post_video_max_mb=call.settings.post_video_max_mb,
        now=call.now,
    )
    fields = dict(started.signature)
    url = str(fields.pop("upload_url"))
    upload = started.upload
    return StartedUpload(
        summary="Upload ticket ready for 30 minutes",
        upload_id=upload.id,
        kind=upload.kind,
        expires_at=moment(call, upload.expires_at) or "",
        curl=curl_command(fields, url, args.filename),
        upload_url=url,
        fields={k: v for k, v in fields.items() if k != "cloud_name"},
        upload_page_url=call.dashboard_url(f"upload/{upload.id}"),
        limits=mcp_uploads.limits_for(args.kind, post_video_max_mb=call.settings.post_video_max_mb),
        next_step=(
            "Run the curl command where the file is, then call finish_media_upload with "
            "upload_id and the public_id it prints. Or have a member open upload_page_url and "
            "drop the file, then call get_media_upload."
        ),
    )


# ---------------------------------------------------------------- finish_media_upload


class FinishMediaUploadInput(WriteInput):
    upload_id: uuid.UUID = Field(description="The upload_id start_media_upload returned.")
    public_id: str | None = Field(
        default=None,
        max_length=512,
        description="The public_id the upload printed. Not needed after the upload page.",
    )


@tool(
    registry,
    name="finish_media_upload",
    title="Finish a media upload",
    description=(
        "Check an uploaded file against the limits and add it to the media library. Returns the "
        "media_id that create_post takes, or the reason the file was rejected (format, size or "
        "length). Finishing the same upload again returns the same media."
    ),
    input_model=FinishMediaUploadInput,
    output_model=UploadedMedia,
    scope="media:write",
    access=Access.DRAFT,
    min_role=Role.ADMIN,
)
async def finish_media_upload(call: ToolCall, args: FinishMediaUploadInput) -> UploadedMedia:
    finished = await mcp_uploads.finish(
        call.session,
        cloudinary_of(call),
        call.redis,
        workspace_id=call.workspace.id,
        user_id=call.principal.user_id,
        plan=call.plan,
        upload_id=args.upload_id,
        public_id=args.public_id,
        post_video_max_mb=call.settings.post_video_max_mb,
        now=call.now,
    )
    return uploaded(finished, how="upload", call=call)


# ---------------------------------------------------------------- import_media_from_url


class ImportMediaInput(WriteInput):
    url: str = Field(
        min_length=8,
        max_length=2000,
        description="A public https link to the image or video file itself.",
    )
    kind: Literal["image", "video"] | None = Field(
        default=None, description="Checked against what the link serves."
    )


@tool(
    registry,
    name="import_media_from_url",
    title="Import media from a link",
    description=(
        "Add an image or video to the media library from a public https link to the file itself "
        "(a CDN link, or a Drive or Dropbox direct-download link). Links to private networks are "
        "refused, as are web pages and files over the limits. Returns the media_id that "
        "create_post takes."
    ),
    input_model=ImportMediaInput,
    output_model=UploadedMedia,
    scope="media:write",
    access=Access.DRAFT,
    min_role=Role.ADMIN,
    open_world=True,
)
async def import_media_from_url(call: ToolCall, args: ImportMediaInput) -> UploadedMedia:
    finished = await mcp_uploads.import_url(
        call.session,
        cloudinary_of(call),
        call.redis,
        workspace_id=call.workspace.id,
        user_id=call.principal.user_id,
        plan=call.plan,
        url=args.url,
        kind=args.kind,
        post_video_max_mb=call.settings.post_video_max_mb,
        now=call.now,
    )
    return uploaded(finished, how="import", call=call)
