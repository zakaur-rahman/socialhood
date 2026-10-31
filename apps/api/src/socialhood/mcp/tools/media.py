"""Media uploads (01-design.md §5): get_media_upload, the read side of an upload ticket.

Phase B adds start_media_upload, finish_media_upload and import_media_from_url, which make and
finish tickets; this reads one. A ticket id is a handle the model passes back, looked up in the
connection's workspace like any other id, so another workspace's ticket is "not found".
"""

from __future__ import annotations

import uuid

from pydantic import Field
from sqlalchemy import select

from socialhood.errors import ApiError
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import ToolInput, ToolOutput, registry, tool
from socialhood.mcp.tools.common import moment
from socialhood.models.identity import Role
from socialhood.models.mcp import McpUpload, UploadStatus

NOT_FOUND = "No upload with this id. Start a new one with start_media_upload."


class GetMediaUploadInput(ToolInput):
    upload_id: uuid.UUID = Field(description="The upload_id start_media_upload returned.")


class UploadResult(ToolOutput):
    upload_id: uuid.UUID
    kind: str  # image, video
    status: str  # waiting, uploaded, expired, rejected
    media_id: uuid.UUID | None = None  # once uploaded: what a post takes
    reason: str | None = None  # why it was rejected
    expires_at: str | None = None


SUMMARIES = {
    UploadStatus.WAITING: "The upload is waiting for the file",
    UploadStatus.UPLOADED: "The file is uploaded and in the media library",
    UploadStatus.EXPIRED: "The upload expired before a file arrived",
    UploadStatus.REJECTED: "The file was rejected",
}


@tool(
    registry,
    name="get_media_upload",
    title="Check a media upload",
    description=(
        "The status of a media upload: waiting for the file, uploaded (with the media_id a post "
        "takes), expired, or rejected (with the reason)."
    ),
    input_model=GetMediaUploadInput,
    output_model=UploadResult,
    scope="media:write",
    min_role=Role.ADMIN,
)
async def get_media_upload(call: ToolCall, args: GetMediaUploadInput) -> UploadResult:
    upload = (
        await call.session.scalars(select(McpUpload).where(McpUpload.id == args.upload_id))
    ).one_or_none()
    if upload is None:
        raise ApiError("not_found", NOT_FOUND)
    status = UploadStatus(upload.status)
    if status is UploadStatus.WAITING and upload.expires_at <= call.now:
        status = UploadStatus.EXPIRED  # read as expired; the cleanup job marks the row
    return UploadResult(
        summary=SUMMARIES[status],
        upload_id=upload.id,
        kind=upload.kind,
        status=status.value,
        media_id=upload.media_asset_id if status is UploadStatus.UPLOADED else None,
        reason=upload.reason if status is UploadStatus.REJECTED else None,
        expires_at=moment(call, upload.expires_at) if status is UploadStatus.WAITING else None,
    )
