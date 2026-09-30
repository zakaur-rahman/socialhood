"""The P7b contract's shared names agree with each other (FR-PUB-20…27, TR-MED-04, TR-MED-05): the
API's render names are the stored ones, the plan's video render allowance, the checklist's edits
key, the event, the Cloudinary notification signature and routing, the render shapes, every P7b
route in the API, and the render job module registered."""

from __future__ import annotations

import hashlib
import importlib
import uuid
from datetime import UTC, datetime
from typing import Any, get_args

import pytest

from socialhood.billing.entitlements import THINGS, quota_error
from socialhood.billing.plans import ENTITLEMENTS, entitlement
from socialhood.jobs.app import TASK_MODULES
from socialhood.main import create_app
from socialhood.media.editor.spec import EditSpec, spec_hash
from socialhood.models.media import MediaAsset, MediaRender, RenderKind, RenderStatus
from socialhood.models.platform import WebhookProvider
from socialhood.realtime.events import EventType
from socialhood.schemas.editor import RenderKindName, RenderStatusName
from socialhood.schemas.publishing import CHECKLIST_KEYS, PostAsset, ScheduledPostDraft
from socialhood.security.signatures import (
    sign_cloudinary_notification,
    verify_cloudinary_notification,
)
from socialhood.services.media_renders import asset_meta, ref_out, render_out
from socialhood.services.webhook_handlers.cloudinary import workspace_of
from socialhood.services.webhook_processing import HANDLERS

# operation id -> (method, path, pending task; None once built): §2.15's media-renders rows.
P7B_ROUTES = {
    "create_media_render": ("post", "/v1/w/{wid}/media-renders", "TB.2"),
    "get_media_render": ("get", "/v1/w/{wid}/media-renders/{render_id}", "TB.2"),
}
P7B_JOB_MODULES = ("socialhood.jobs.tasks.renders",)
SECRET = "cloudinary-test-secret"
NOW = 1_790_000_000.0


def test_api_names_are_the_stored_ones() -> None:
    assert set(get_args(RenderStatusName)) == {s.value for s in RenderStatus}
    assert set(get_args(RenderKindName)) == {k.value for k in RenderKind}
    assert WebhookProvider.CLOUDINARY in HANDLERS
    assert "media_render.updated" in get_args(EventType)


def test_video_renders_are_a_monthly_allowance_on_every_plan() -> None:
    assert ENTITLEMENTS["video_renders_monthly"] == {"free": 10, "pro": 200, "max": 1000}
    assert entitlement("free", "video_renders_monthly") == 10
    error = quota_error("video_renders_monthly", 10)
    assert error.code == "quota_exceeded"
    assert error.plan_limit is not None
    assert (error.plan_limit.entitlement, error.plan_limit.limit) == ("video_renders_monthly", 10)
    assert error.detail == "Your plan includes 10 edited video renders a month."
    assert "video_renders_monthly" in THINGS


def test_the_checklist_checks_edits_after_the_media() -> None:
    keys = list(CHECKLIST_KEYS)
    assert keys.index("edits") == keys.index("media_files") + 1


def test_a_draft_may_carry_edits_and_leaving_them_out_keeps_them() -> None:
    draft = ScheduledPostDraft.model_validate({"asset_ids": []})
    assert draft.edits is None  # left out: each item keeps its edit
    edited = ScheduledPostDraft.model_validate(
        {"asset_ids": [str(uuid.uuid4())] * 2, "edits": [{"preset": "vivid"}, None]}
    )
    assert edited.edits is not None
    assert edited.edits[0] == EditSpec(preset="vivid")
    assert edited.edits[1] is None
    assert "edit" in PostAsset.model_fields
    assert "render" in PostAsset.model_fields


# ---------------------------------------------------------------- Cloudinary notifications


def _headers(raw: bytes, *, at: float = NOW, algorithm: str = "sha1") -> dict[str, str]:
    return sign_cloudinary_notification(raw, int(at), SECRET, algorithm=algorithm)


def test_a_notification_signature_is_sha1_of_body_timestamp_and_secret() -> None:
    raw = b'{"notification_type":"eager"}'
    headers = _headers(raw)
    expected = hashlib.sha1(raw + str(int(NOW)).encode() + SECRET.encode()).hexdigest()  # noqa: S324
    assert headers == {"X-Cld-Timestamp": str(int(NOW)), "X-Cld-Signature": expected}
    assert verify_cloudinary_notification(raw, headers, SECRET, now=NOW)
    # Accounts set to SHA-256 sign with it; lower-case header names work too.
    sha256 = {k.lower(): v for k, v in _headers(raw, algorithm="sha256").items()}
    assert len(sha256["x-cld-signature"]) == 64
    assert verify_cloudinary_notification(raw, sha256, SECRET, now=NOW)


@pytest.mark.parametrize(
    "tamper", ["no_secret", "wrong_secret", "changed_body", "stale", "future", "no_headers", "bad"]
)
def test_anything_else_fails_closed(tamper: str) -> None:
    raw = b'{"notification_type":"eager"}'
    headers: dict[str, str] = _headers(raw)
    secret, body = SECRET, raw
    if tamper == "no_secret":
        secret = ""
    elif tamper == "wrong_secret":
        headers = sign_cloudinary_notification(raw, int(NOW), "other")
    elif tamper == "changed_body":
        body = raw.replace(b"eager", b"upload")
    elif tamper == "stale":
        headers = _headers(raw, at=NOW - 7201)
    elif tamper == "future":
        headers = _headers(raw, at=NOW + 301)
    elif tamper == "no_headers":
        headers = {}
    elif tamper == "bad":
        headers = {"X-Cld-Timestamp": "soon", "X-Cld-Signature": "zz"}
    assert not verify_cloudinary_notification(body, headers, secret, now=NOW)


def test_a_notification_belongs_to_the_workspace_whose_folder_holds_the_asset() -> None:
    wid = uuid.uuid4()
    assert workspace_of({"public_id": f"ws/{wid}/post/abc"}) == wid
    assert workspace_of({"public_id": "samples/sea-turtle"}) is None
    assert workspace_of({"public_id": f"elsewhere/ws/{wid}/post/abc"}) is None
    assert workspace_of({}) is None


# ---------------------------------------------------------------- shapes


def test_a_render_row_becomes_the_api_shape() -> None:
    wid, asset_id, render_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    spec = EditSpec(preset="noir", speed=1.5)
    now = datetime(2026, 9, 30, 9, 0, tzinfo=UTC)
    row = MediaRender(
        id=render_id,
        workspace_id=wid,
        media_asset_id=asset_id,
        kind="video",
        spec=spec.model_dump(mode="json"),
        spec_hash=spec_hash(spec),
        transformation="e_contrast:45/e_saturation:-100/vc_h264,ac_aac,q_auto",
        format="mp4",
        status="ready",
        url="https://res.cloudinary.com/c/video/upload/x/ws/a.mp4",
        width=1080,
        height=1920,
        duration_s=8.0,
        bytes=1234,
        created_at=now,
        ready_at=now,
    )
    out = render_out(row)
    assert (out.id, out.asset_id, out.kind, out.status, out.spec) == (
        render_id,
        asset_id,
        "video",
        "ready",
        spec,
    )
    ref = ref_out(row)
    assert (ref.status, ref.url, ref.duration_s) == ("ready", row.url, 8.0)


def test_an_asset_without_a_size_cant_be_edited() -> None:
    wid = uuid.uuid4()
    base: dict[str, Any] = {
        "workspace_id": wid,
        "public_id": f"ws/{wid}/post/a",
        "purpose": "post",
        "bytes": 1,
    }
    photo = MediaAsset(resource_type="image", width=1080, height=1350, **base)
    meta = asset_meta(photo, "cloud")
    assert meta is not None
    assert (meta.cloud_name, meta.resource_type, meta.width) == ("cloud", "image", 1080)
    assert (
        asset_meta(MediaAsset(resource_type="image", width=None, height=None, **base), "c") is None
    )
    assert asset_meta(MediaAsset(resource_type="raw", width=10, height=10, **base), "c") is None


# ---------------------------------------------------------------- routes and jobs


def test_every_p7b_route_is_in_the_api(api_settings: Any) -> None:
    openapi = create_app(api_settings).openapi()
    found = {
        operation["operationId"]: (method, path, operation.get("x-pending"))
        for path, operations in openapi["paths"].items()
        for method, operation in operations.items()
        if operation.get("operationId") in P7B_ROUTES
    }
    assert found == P7B_ROUTES
    # The Cloudinary webhook is not part of the product API's contract; there is no preview
    # route (the web builds previews with its twin of the builder).
    assert not any(path.startswith("/webhooks") for path in openapi["paths"])
    create = openapi["paths"]["/v1/w/{wid}/media-renders"]["post"]["responses"]
    assert {"200", "201"} <= set(create)
    schemas = openapi["components"]["schemas"]
    assert {"EditSpec", "MediaRender", "MediaRenderCreate", "MediaRenderRef"} <= set(schemas)


def test_the_render_job_module_is_registered() -> None:
    for module in P7B_JOB_MODULES:
        assert module in TASK_MODULES
        importlib.import_module(module)
