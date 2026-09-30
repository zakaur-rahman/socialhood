"""Media renders (P7b; FR-PUB-20…24, TR-MED-04, TR-MED-05; docs/editor-spike.md).

The foundation holds the shapes (``render_out``, ``ref_out``) and the builder's input
(``asset_meta``); TB.2 builds the rest, TB.3 the counting and caps, TB.4 the post items:

- ``create_or_reuse(session, ctx, body, cloudinary)``: load the asset (404 unless a post upload
  of this workspace), check ``spec.problems`` and the logo (an image upload of this workspace;
  its public id feeds the builder), hash the spec; an existing (asset, hash) row is returned
  (200; a failed one goes back to pending and is started again); else check
  ``video_renders_monthly`` for a video (TB.3), build the transformation, insert the row (photo:
  ready with the build's URL and size at once; video: pending, with cover_url when cover_s is
  set), link the drafts' items that hold this edit (render_id), queue media_render.updated and
  enqueue start_render after the commit. A race on uq_media_renders_media_asset_id_spec_hash
  returns the winner's row.
- ``start(sessionmaker, redis, cloudinary, render_id)``, ``finish(...)`` (from a notification
  entry or a poll: ready with width, height, bytes and duration, or failed), ``poll(...)`` and
  ``sweep(...)`` for jobs/tasks/renders.py and services/webhook_handlers/cloudinary.py.
- ``used_in_period(session, kind, start, end)`` (TB.3): renders of ``kind`` created in the usage
  period, failed ones left out; billing/usage.py counts video_renders_monthly with it, and the
  billing page shows photo edits with it (no limit).
"""

from __future__ import annotations

from typing import cast

from socialhood.media.editor.spec import EditSpec
from socialhood.media.editor.transform import AssetMeta
from socialhood.models.media import MediaAsset, MediaRender
from socialhood.schemas.editor import MediaRender as MediaRenderOut
from socialhood.schemas.editor import MediaRenderRef, RenderStatusName


def asset_meta(asset: MediaAsset, cloud_name: str) -> AssetMeta | None:
    """What the builder needs of an upload; None when it can't be edited (no dimensions, or not
    an image or video)."""
    if asset.resource_type not in ("image", "video") or not asset.width or not asset.height:
        return None
    return AssetMeta(
        cloud_name=cloud_name,
        public_id=asset.public_id,
        resource_type="video" if asset.resource_type == "video" else "image",
        width=asset.width,
        height=asset.height,
        duration_s=asset.duration_s,
    )


def render_out(row: MediaRender) -> MediaRenderOut:
    return MediaRenderOut(
        id=row.id,
        asset_id=row.media_asset_id,
        kind="video" if row.kind == "video" else "image",
        status=cast(RenderStatusName, row.status),
        spec=EditSpec.model_validate(row.spec),
        url=row.url,
        cover_url=row.cover_url,
        width=row.width,
        height=row.height,
        duration_s=row.duration_s,
        bytes=row.bytes,
        error=row.error,
        requested_by_user_id=row.requested_by_user_id,
        created_at=row.created_at,
        ready_at=row.ready_at,
    )


def ref_out(row: MediaRender) -> MediaRenderRef:
    return MediaRenderRef(
        id=row.id,
        status=cast(RenderStatusName, row.status),
        url=row.url,
        cover_url=row.cover_url,
        width=row.width,
        height=row.height,
        duration_s=row.duration_s,
        error=row.error,
    )
