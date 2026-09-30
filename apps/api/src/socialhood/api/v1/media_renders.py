"""The media editor's renders (P7b; §2.15 …/media-renders; FR-PUB-20…24, TR-MED-04, TR-MED-05).

An edit is a spec on a post item; its rendered file is a render. Photos render on the fly, so a
photo render is ``ready`` at once; a video render is ``pending`` until start_render sends it to
Cloudinary, ``rendering`` while Cloudinary works, then ``ready`` or ``failed``
(media_render.updated each time). The editor builds its previews itself from the shared builder
(lib/editor/transform.ts, the twin of media/editor/transform.py), so there is no preview route.

The routes below are the P7b contract; TB.2 builds them (services/media_renders.py) and removes
their ``openapi_extra`` markers, so the tenancy suite covers them then.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import Admin, Session
from socialhood.schemas.editor import MediaRender, MediaRenderCreate

router = APIRouter(prefix="/v1/w/{wid}", tags=["editor"])


@router.post(
    "/media-renders",
    status_code=201,
    operation_id="create_media_render",
    openapi_extra=pending("TB.2"),
    responses={200: {"model": MediaRender, "description": "The same edit, rendered before"}},
)
async def create_media_render(
    request: Request, response: Response, body: MediaRenderCreate, ctx: Admin, session: Session
) -> MediaRender:
    """FR-PUB-21: render ``spec`` of a post upload. 201 with a new render (a photo's is ready, a
    video's pending with start_render enqueued); 200 with the existing one when this asset has
    that spec already (a failed one is started again). 404 when the asset isn't this workspace's;
    422 on ``spec.{field}`` when the spec can't apply (media/editor/spec.problems, a logo that
    isn't an image upload of this workspace, an asset without dimensions); 402 quota_exceeded
    (``video_renders_monthly``, the plan's limit) for a new video render past the allowance."""
    raise NotImplementedError("TB.2")


@router.get(
    "/media-renders/{render_id}", operation_id="get_media_render", openapi_extra=pending("TB.2")
)
async def get_media_render(render_id: uuid.UUID, ctx: Admin, session: Session) -> MediaRender:
    """One render, for a composer that missed its media_render.updated."""
    raise NotImplementedError("TB.2")
