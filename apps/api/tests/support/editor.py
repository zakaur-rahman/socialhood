"""The editor's golden fixtures (TR-MED-04) and what P7b tests need: media renders, a Cloudinary
configuration and signed Cloudinary notifications (TR-MED-05). The fixtures file is shared with
the web's vitest suite (packages/editor-fixtures). No test reaches Cloudinary: its HTTP API is
mocked with respx (as tests/integration/test_media_assets.py does)."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.media.editor.spec import EditSpec, spec_hash
from socialhood.media.editor.transform import AssetMeta, build, drawable
from socialhood.models.media import MediaAsset, MediaRender
from socialhood.security.signatures import sign_cloudinary_notification
from socialhood.settings import Settings

FIXTURES = (
    Path(__file__).resolve().parents[4] / "packages" / "editor-fixtures" / "transform-cases.json"
)

CLOUD = "socialhood-test"
API_KEY = "123456789012345"
API_SECRET = "cloudinary-test-secret"


def with_cloudinary(settings: Settings) -> Settings:
    """``settings`` with the test Cloudinary account (the default test settings have none)."""
    return settings.model_copy(
        update={
            "cloudinary_cloud_name": CLOUD,
            "cloudinary_api_key": API_KEY,
            "cloudinary_api_secret": SecretStr(API_SECRET),
        }
    )


def eager_notification(
    public_id: str, transformation: str, *, batch_id: str = "batch-1", **entry: Any
) -> dict[str, Any]:
    """Cloudinary's notification that an eager render finished (``notification_type: eager``).
    The entry's transformation comes back URL-decoded, as Cloudinary sends it."""
    from urllib.parse import unquote

    decoded = unquote(transformation)
    return {
        "notification_type": "eager",
        "batch_id": batch_id,
        "asset_id": "0f1e2d3c4b5a69788796a5b4c3d2e1f0",
        "public_id": public_id,
        "eager": [
            {
                "transformation": decoded,
                "width": entry.pop("width", 1080),
                "height": entry.pop("height", 1920),
                "bytes": entry.pop("bytes", 2_400_000),
                "format": entry.pop("format", "mp4"),
                "url": f"http://res.cloudinary.com/{CLOUD}/video/upload/{transformation}/v1/{public_id}.mp4",
                "secure_url": (
                    f"https://res.cloudinary.com/{CLOUD}/video/upload/{transformation}/v1/"
                    f"{public_id}.mp4"
                ),
                **entry,
            }
        ],
    }


def notification_headers(
    raw: bytes, *, secret: str = API_SECRET, at: float | None = None, algorithm: str = "sha1"
) -> dict[str, str]:
    stamp = int(time.time() if at is None else at)
    headers = sign_cloudinary_notification(raw, stamp, secret, algorithm=algorithm)
    return {"content-type": "application/json", **headers}


async def post_notification(client: httpx.AsyncClient, payload: dict[str, Any]) -> httpx.Response:
    raw = json.dumps(payload).encode()
    return await client.post("/webhooks/cloudinary", content=raw, headers=notification_headers(raw))


def load_fixtures() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data


def lenient_spec(raw: dict[str, Any]) -> EditSpec:
    """A fixture's spec as the builder sees it. The API refuses text it can't draw (emoji outside
    the BMP); the builders drop it instead, and a fixture checks that they agree. So validate
    with the drawable text, then put the original text back."""
    texts = raw.get("texts", [])
    cleaned = {**raw, "texts": [{**t, "text": drawable(t["text"]) or "x"} for t in texts]}
    spec = EditSpec.model_validate(cleaned)
    layers = [
        layer.model_copy(update={"text": t["text"]})
        for layer, t in zip(spec.texts, texts, strict=True)
    ]
    return spec.model_copy(update={"texts": layers})


async def make_render(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    asset_id: uuid.UUID | str,
    spec: dict[str, Any] | None = None,
    status: str | None = None,
    requested_by_user_id: uuid.UUID | str | None = None,
    **values: Any,
) -> uuid.UUID:
    """A media_renders row for an asset, built from the spec like the service will: kind from the
    asset, the transformation from the builder. An image render is ``ready`` with its URL (photos
    render on the fly); a video render is ``pending`` unless ``status`` says otherwise (``ready``
    gets a URL and a size). Other columns go in ``values``."""
    wid = uuid.UUID(str(workspace_id))
    edit = EditSpec.model_validate(spec or {"preset": "vivid"})
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            asset = await session.get(MediaAsset, uuid.UUID(str(asset_id)))
            assert asset is not None, "no such asset in this workspace"
            kind = "video" if asset.resource_type == "video" else "image"
            meta = AssetMeta(
                cloud_name="demo",
                public_id=asset.public_id,
                resource_type=kind,
                width=asset.width or 1080,
                height=asset.height or 1080,
                duration_s=asset.duration_s,
            )
            built = build(meta, edit, logo_public_id=f"ws/{wid}/post/logo")
            state = status or ("ready" if kind == "image" else "pending")
            if state == "ready":
                values.setdefault("url", built.url)
                values.setdefault("width", built.width)
                values.setdefault("height", built.height)
                values.setdefault("duration_s", built.duration_s)
                values.setdefault("ready_at", datetime.now(UTC))
            if state == "failed":
                values.setdefault("error", "Cloudinary couldn't render this video.")
            columns: dict[str, Any] = {
                "media_asset_id": asset.id,
                "kind": kind,
                "spec": edit.model_dump(mode="json"),
                "spec_hash": spec_hash(edit),
                "transformation": built.transformation,
                "format": built.format,
                "status": state,
                "requested_by_user_id": (
                    uuid.UUID(str(requested_by_user_id)) if requested_by_user_id else None
                ),
            }
            row = MediaRender(**(columns | values))
            session.add(row)
            await session.commit()
            return row.id
