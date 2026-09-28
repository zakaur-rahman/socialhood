"""Files, audio, video and stickers in replies (FR-INB-08 with Meta's per-platform limits)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.jobs.runtime import Runtime
from socialhood.platforms.deps import deps_from
from socialhood.platforms.sandbox import outbox
from socialhood.repositories import inbox
from socialhood.services import sending
from tests.support.api import Clerk
from tests.support.inbox import make_account, make_asset, make_thread, make_workspace
from tests.support.sending import (
    Setup,
    clean_outbox,
    post_message,
    run_send,
    use_app_runtime,
    workspace_with_thread,
)

MB = 1024 * 1024
HEART = "❤️"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
def worker(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Runtime:
    return use_app_runtime(app, monkeypatch)


@pytest.fixture
async def setup(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    return await workspace_with_thread(client, clerk, engine)


# ---- Instagram: images, video, audio and PDF files; the heart sticker


@pytest.mark.parametrize(
    ("resource_type", "fmt", "kind"),
    [("raw", "pdf", "file"), ("video", "m4a", "audio"), ("video", "webm", "video")],
)
async def test_instagram_sends_files_audio_and_video(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    worker: Runtime,
    queue: None,
    resource_type: str,
    fmt: str,
    kind: str,
) -> None:
    asset = await make_asset(engine, workspace_id=setup.wid, resource_type=resource_type, fmt=fmt)
    response = await post_message(client, setup, text=None, attachment_asset_ids=[str(asset)])
    assert response.status_code == 202, response.text
    message = response.json()
    assert message["kind"] == kind
    assert message["attachments"][0]["type"] == kind

    await run_send(setup, message)
    [sent] = outbox.SENT
    assert sent.message.attachment is not None
    assert sent.message.attachment.type == kind
    # Audio and files go as uploaded; only images and video are converted for delivery.
    if kind in ("file", "audio"):
        assert sent.message.attachment.url.endswith(f"sample.{fmt}")


@pytest.mark.parametrize(
    ("resource_type", "fmt", "size", "detail"),
    [
        ("video", "mp4", 26 * MB, "Instagram videos can be up to 25 MB."),
        ("raw", "docx", MB, "Instagram files can be PDF."),
        ("video", "mp3", MB, "Instagram audio files can be AAC, M4A, MP4, WAV."),
    ],
)
async def test_instagrams_limits_are_enforced(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    resource_type: str,
    fmt: str,
    size: int,
    detail: str,
) -> None:
    asset = await make_asset(
        engine, workspace_id=setup.wid, resource_type=resource_type, fmt=fmt, size=size
    )
    response = await post_message(client, setup, text=None, attachment_asset_ids=[str(asset)])
    assert response.status_code == 415, response.text
    assert response.json()["detail"] == detail


async def test_the_heart_sticker(
    client: httpx.AsyncClient, setup: Setup, worker: Runtime, queue: None
) -> None:
    response = await post_message(client, setup, text=None, sticker="like_heart")
    assert response.status_code == 202, response.text
    message = response.json()
    assert (message["kind"], message["text"], message["attachments"]) == ("sticker", HEART, [])

    await run_send(setup, message)
    [sent] = outbox.SENT
    assert sent.message.sticker == "like_heart"
    assert sent.message.text is None


async def test_a_sticker_goes_on_its_own(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    response = await post_message(client, setup, text="Thanks!", sticker="like_heart")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "sticker"

    webp = await make_asset(engine, workspace_id=setup.wid, fmt="webp", width=512, height=512)
    refused = await post_message(client, setup, text=None, sticker_asset_id=str(webp))
    assert refused.status_code == 415
    assert refused.json()["detail"] == "Instagram can only send its heart sticker."


# ---- WhatsApp: WebP stickers, documents; no heart


async def whatsapp_conversation(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    wid = await make_workspace(engine)
    account = await make_account(
        engine, wid, platform="whatsapp", platform_account_id="1098765432101"
    )
    thread = await make_thread(
        engine,
        workspace_id=wid,
        account_id=account,
        platform="whatsapp",
        contact_ref="919876543210",
        last_inbound_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    return wid, thread.conversation_id


async def queue_reply(
    app: FastAPI, engine: AsyncEngine, wid: uuid.UUID, conversation_id: uuid.UUID, **values: object
) -> dict[str, object]:
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            conv = await inbox.get_conversation(session, conversation_id)
            assert conv is not None
            msg = await sending.queue_outbound(
                session,
                conv,
                source="human",
                client_id=uuid.uuid4(),
                deps=deps_from(app.state.http, app.state.settings),
                **values,  # type: ignore[arg-type]
            )
            await session.rollback()  # nothing needs keeping; the job is never run
            return {"kind": msg.kind, "attachments": msg.attachments, "text": msg.text}


async def test_whatsapp_sends_a_webp_sticker(app: FastAPI, engine: AsyncEngine) -> None:
    wid, conversation_id = await whatsapp_conversation(engine)
    sticker = await make_asset(
        engine, workspace_id=wid, fmt="webp", size=60_000, width=512, height=512
    )
    msg = await queue_reply(app, engine, wid, conversation_id, sticker_asset_id=sticker)
    assert msg["kind"] == "sticker"
    [attachment] = msg["attachments"]  # type: ignore[misc]
    assert attachment["type"] == "sticker"
    assert attachment["send_url"].endswith("sample.webp")  # sent as uploaded, not as a JPEG


@pytest.mark.parametrize(
    ("fmt", "size", "width"),
    [("png", 60_000, 512), ("webp", 600_000, 512), ("webp", 60_000, 800)],
    ids=["not-webp", "too-big", "not-512"],
)
async def test_whatsapp_stickers_must_be_512_webp(
    app: FastAPI, engine: AsyncEngine, fmt: str, size: int, width: int
) -> None:
    wid, conversation_id = await whatsapp_conversation(engine)
    asset = await make_asset(
        engine, workspace_id=wid, fmt=fmt, size=size, width=width, height=width
    )
    with pytest.raises(ApiError) as caught:
        await queue_reply(app, engine, wid, conversation_id, sticker_asset_id=asset)
    assert caught.value.code == "unsupported_media"
    assert caught.value.detail == "WhatsApp stickers are 512 x 512 WebP images up to 500 KB."


async def test_whatsapp_has_no_heart_but_sends_documents(app: FastAPI, engine: AsyncEngine) -> None:
    wid, conversation_id = await whatsapp_conversation(engine)
    with pytest.raises(ApiError) as caught:
        await queue_reply(app, engine, wid, conversation_id, sticker="like_heart")
    assert caught.value.detail == "WhatsApp has no heart sticker."

    doc = await make_asset(engine, workspace_id=wid, resource_type="raw", fmt="docx", size=40 * MB)
    msg = await queue_reply(app, engine, wid, conversation_id, attachment_asset_ids=[doc])
    assert msg["kind"] == "file"
