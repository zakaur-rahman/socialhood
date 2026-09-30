"""The media editor's shapes (P7b; §2.15 …/media-renders, §5.10 MediaRender; FR-PUB-20…27,
TR-MED-04, TR-MED-05).

The P7b contract. An edit is an ``EditSpec`` (media/editor/spec.py) kept on the post's item
(``ScheduledPostDraft.edits``, ``PostAsset.edit``); its rendered file is a ``MediaRender``. Photos
render on the fly, so a photo's render is ``ready`` the moment it is created; a video's is
``pending``, then ``rendering`` while Cloudinary works, then ``ready`` or ``failed``.
``media_render.updated`` carries the render (TR-RT-03), so the composer patches its item without
polling.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from socialhood.media.editor.spec import EditSpec
from socialhood.schemas.common import RequestModel, ResponseModel

RenderKindName = Literal["image", "video"]
RenderStatusName = Literal["pending", "rendering", "ready", "failed"]


class MediaRenderCreate(RequestModel):
    """POST …/media-renders: render ``spec`` of the post upload ``asset_id``.

    The same spec of the same asset is one render: asking again returns it (200) instead of a new
    one (201), and a failed one starts again. Refusals: 404 when the asset isn't this workspace's;
    422 on ``spec.{field}`` when the spec can't apply to the media (a look on a video, a trim past
    its end, a logo that isn't an image of this workspace); 402 quota_exceeded
    (``video_renders_monthly`` with the plan's limit) for a new video render past the month's
    allowance. Photo renders aren't limited (they are counted)."""

    asset_id: uuid.UUID
    spec: EditSpec


class MediaRender(ResponseModel):
    """§5.10 MediaRender: one edit of one upload and its rendered file."""

    id: uuid.UUID
    asset_id: uuid.UUID
    kind: RenderKindName
    status: RenderStatusName
    spec: EditSpec
    url: str | None = None  # the rendered file, once ready (photos: at once)
    cover_url: str | None = None  # a video's cover frame (spec.cover_s), for the Reel
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None  # video, after trim and speed
    bytes: int | None = None
    error: str | None = None  # why it failed, in plain words
    requested_by_user_id: uuid.UUID | None = None
    created_at: datetime
    ready_at: datetime | None = None


class MediaRenderRef(ResponseModel):
    """A post item's render (``PostAsset.render``): enough for the composer's badge ("Rendering",
    "Couldn't render") and the preview."""

    id: uuid.UUID
    status: RenderStatusName
    url: str | None = None
    cover_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    error: str | None = None
