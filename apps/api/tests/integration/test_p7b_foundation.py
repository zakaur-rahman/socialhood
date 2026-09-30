"""P7b foundation (§5.7, §5.9; FR-PUB-20…24, TR-MED-04, TR-MED-05, SEC-04): the keys, checks and
cascades of media_renders, the edit columns of scheduled_post_assets, the Cloudinary webhook's
fail-closed intake, and a post item's edit in the API, through the factories every P7b test uses."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.main import create_app
from socialhood.media.editor.spec import EditSpec, spec_hash
from socialhood.settings import Settings
from socialhood.webhooks import cloudinary as cloudinary_webhook
from tests.support.api import Clerk, sign_in
from tests.support.editor import (
    eager_notification,
    make_render,
    notification_headers,
    post_notification,
    with_cloudinary,
)
from tests.support.inbox import make_asset, make_workspace
from tests.support.publishing import make_scheduled_post


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_cloudinary(api_settings)


@pytest.fixture
async def wid(engine: AsyncEngine, clean_db: None) -> uuid.UUID:
    return await make_workspace(engine)


async def _scalar(engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def _execute(engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def _video(engine: AsyncEngine, wid: uuid.UUID) -> uuid.UUID:
    return await make_asset(
        engine,
        workspace_id=wid,
        purpose="post",
        resource_type="video",
        fmt="mp4",
        width=1920,
        height=1080,
    )


# ---------------------------------------------------------------- media_renders


async def test_a_photo_render_is_ready_at_once_and_a_video_render_waits(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    photo = await make_asset(engine, workspace_id=wid, purpose="post")
    video = await _video(engine, wid)
    ready = await make_render(engine, workspace_id=wid, asset_id=photo)
    waiting = await make_render(engine, workspace_id=wid, asset_id=video, spec={"speed": 2})
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, kind, status, format, url IS NOT NULL FROM media_renders")
        )
        rows = {row[0]: tuple(row[1:]) for row in result.all()}
    assert rows[ready] == ("image", "ready", "jpg", True)
    assert rows[waiting] == ("video", "pending", "mp4", False)


async def test_the_same_edit_of_the_same_asset_is_one_render(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    video = await _video(engine, wid)
    await make_render(engine, workspace_id=wid, asset_id=video, spec={"preset": "noir"})
    with pytest.raises(IntegrityError, match="uq_media_renders_media_asset_id_spec_hash"):
        await make_render(engine, workspace_id=wid, asset_id=video, spec={"preset": "noir"})
    # Another edit of it, or the same edit of another asset, is another render.
    await make_render(engine, workspace_id=wid, asset_id=video, spec={"preset": "warm"})
    await make_render(
        engine, workspace_id=wid, asset_id=await _video(engine, wid), spec={"preset": "noir"}
    )
    assert await _scalar(engine, "SELECT count(*) FROM media_renders") == 3


@pytest.mark.parametrize(
    ("values", "check"),
    [
        ({"status": "done"}, "ck_media_renders_status"),
        ({"status": "ready", "url": None}, "ck_media_renders_ready"),
        ({"status": "failed", "error": None}, "ck_media_renders_failed"),
        ({"format": "jpg"}, "ck_media_renders_format"),
        ({"spec_hash": "not-a-hash"}, "ck_media_renders_spec_hash"),
        ({"poll_count": -1}, "ck_media_renders_counters"),
    ],
)
async def test_render_rows_are_checked(
    engine: AsyncEngine, wid: uuid.UUID, values: dict[str, Any], check: str
) -> None:
    video = await _video(engine, wid)
    with pytest.raises(IntegrityError, match=check):
        await make_render(engine, workspace_id=wid, asset_id=video, **values)


async def test_renders_go_with_their_asset_and_items_keep_their_edit(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    video = await _video(engine, wid)
    edit = {"trim": {"start_s": 1, "end_s": 5}, "preset": "vivid"}
    render = await make_render(engine, workspace_id=wid, asset_id=video, spec=edit)
    post = await make_scheduled_post(
        engine, workspace_id=wid, asset_ids=[video], edits=[edit], render_ids=[render]
    )
    stored = await _scalar(
        engine,
        "SELECT edit_spec FROM scheduled_post_assets WHERE scheduled_post_id = :p",
        p=post.id,
    )
    assert EditSpec.model_validate(stored) == EditSpec.model_validate(edit)
    assert spec_hash(EditSpec.model_validate(stored)) == await _scalar(
        engine, "SELECT spec_hash FROM media_renders WHERE id = :r", r=render
    )
    # Deleting the render leaves the edit, to render again.
    await _execute(engine, "DELETE FROM media_renders WHERE id = :r", r=render)
    assert (
        await _scalar(
            engine,
            "SELECT render_id IS NULL AND edit_spec IS NOT NULL FROM scheduled_post_assets"
            " WHERE scheduled_post_id = :p",
            p=post.id,
        )
        is True
    )
    # An asset's renders go with it (an asset in a post can't be deleted: RESTRICT).
    other = await _video(engine, wid)
    await make_render(engine, workspace_id=wid, asset_id=other)
    await _execute(engine, "DELETE FROM media_assets WHERE id = :a", a=other)
    assert (
        await _scalar(
            engine, "SELECT count(*) FROM media_renders WHERE media_asset_id = :a", a=other
        )
        == 0
    )


async def test_an_item_can_only_point_at_a_render_of_its_edit(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    video = await _video(engine, wid)
    render = await make_render(engine, workspace_id=wid, asset_id=video)
    with pytest.raises(IntegrityError, match="ck_scheduled_post_assets_render_has_edit"):
        await make_scheduled_post(engine, workspace_id=wid, asset_ids=[video], render_ids=[render])


# ---------------------------------------------------------------- the Cloudinary webhook


async def _stored(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT provider, dedupe_key, event_type, status, payload FROM webhook_events"
                " ORDER BY received_at"
            )
        )
        return [dict(row._mapping) for row in rows]


@pytest.mark.usefixtures("queue")
async def test_a_signed_notification_is_stored_once_and_queued(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    wid = uuid.uuid4()
    payload = eager_notification(f"ws/{wid}/post/clip", "so_1,eo_5/vc_h264,ac_aac,q_auto")
    first = await post_notification(client, payload)
    again = await post_notification(client, payload)  # Cloudinary retries
    assert (first.status_code, again.status_code) == (200, 200)
    [row] = await _stored(engine)
    assert (row["provider"], row["event_type"], row["status"]) == (
        "cloudinary",
        "eager",
        "received",
    )
    assert row["dedupe_key"].startswith("cloudinary:")
    assert row["payload"]["batch_id"] == "batch-1"
    jobs = await _scalar(
        engine,
        "SELECT count(*) FROM procrastinate_jobs WHERE task_name = 'process_webhook_event'",
    )
    assert jobs == 1


@pytest.mark.parametrize(
    "tamper", ["unsigned", "wrong_secret", "changed_body", "stale", "not_json", "not_an_object"]
)
async def test_an_unverified_notification_is_refused_and_stores_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine, tamper: str
) -> None:
    raw = json.dumps(eager_notification(f"ws/{uuid.uuid4()}/post/c", "q_auto")).encode()
    headers = notification_headers(raw)
    body = raw
    expected = 401
    if tamper == "unsigned":
        headers = {"content-type": "application/json"}
    elif tamper == "wrong_secret":
        headers = notification_headers(raw, secret="not-the-secret")
    elif tamper == "changed_body":
        body = raw.replace(b"batch-1", b"batch-2")
    elif tamper == "stale":
        headers = notification_headers(raw, at=time.time() - 3 * 3600)
    elif tamper == "not_json":
        body = b"not json"
        headers = notification_headers(body)
        expected = 400
    elif tamper == "not_an_object":
        body = b"[1, 2]"
        headers = notification_headers(body)
        expected = 400
    response = await client.post("/webhooks/cloudinary", content=body, headers=headers)
    assert response.status_code == expected, response.text
    assert await _stored(engine) == []


async def test_without_a_secret_the_cloudinary_webhook_fails_closed(
    api_settings: Settings, clean_db: None, engine: AsyncEngine
) -> None:
    app = create_app(api_settings.model_copy(update={"cloudinary_api_secret": None}))
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            raw = json.dumps(eager_notification("ws/x/post/c", "q_auto")).encode()
            response = await client.post(
                "/webhooks/cloudinary", content=raw, headers=notification_headers(raw)
            )
        assert response.status_code == 503
        assert response.json()["code"] == "service_unavailable"
        assert await _stored(engine) == []
    finally:
        await app.state.http.aclose()
        await app.state.redis.aclose()
        await app.state.engine.dispose()


@pytest.mark.usefixtures("queue")
async def test_a_stored_notification_is_routed_to_its_workspace_and_left_for_tb2(
    app: FastAPI, client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from socialhood.services.webhook_processing import process_event

    wid = await make_workspace(engine)
    payload = eager_notification(f"ws/{wid}/post/clip", "vc_h264,ac_aac,q_auto")
    raw = json.dumps(payload).encode()
    assert cloudinary_webhook.router.routes  # mounted at /webhooks/cloudinary
    response = await client.post(
        "/webhooks/cloudinary", content=raw, headers=notification_headers(raw)
    )
    assert response.status_code == 200, response.text
    event_id = await _scalar(engine, "SELECT id FROM webhook_events")
    status = await process_event(async_sessionmaker(engine, expire_on_commit=False), event_id)
    assert status is not None
    assert status.value == "ignored"
    assert (
        await _scalar(engine, "SELECT workspace_id FROM webhook_events WHERE id = :e", e=event_id)
        == wid
    )


# ---------------------------------------------------------------- a post item's edit in the API


async def test_a_post_shows_each_items_edit_and_public_id(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    owner, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    photo = await make_asset(engine, workspace_id=wid, purpose="post", height=1350)
    video = await _video(engine, uuid.UUID(wid))
    edit = {"crop": {"aspect": "4:5"}, "texts": [{"text": "Sale, today"}]}
    post = await make_scheduled_post(
        engine, workspace_id=wid, asset_ids=[photo, video], edits=[None, edit]
    )
    response = await client.get(
        f"/v1/w/{wid}/scheduled-posts/{post.id}", headers=clerk.headers(owner)
    )
    assert response.status_code == 200, response.text
    first, second = response.json()["assets"]
    assert first["edit"] is None
    assert first["public_id"].startswith(f"ws/{wid}/post/")
    assert second["edit"] == EditSpec.model_validate(edit).model_dump(mode="json")
    assert second["render"] is None  # TB.4 fills it
