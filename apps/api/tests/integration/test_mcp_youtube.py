"""C-196: the MCP YouTube tools through the SDK client against the mounted app:
prepare_youtube_upload's preview and confirmed call (the post, the open upload, the upload page's
ticket, the curl hint), get_youtube_upload_status finishing an upload YouTube holds, and the
upload page's ``youtube`` ticket (GET and complete)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.youtube.fake import SESSION_PREFIX, FakeYouTube
from tests.support.mcp import confirm, connect, error_of, make_key, structured
from tests.support.sending import Setup, clean_outbox
from tests.support.youtube import clear_upload_quota, make_channel

WRITE_SCOPES = ("posts:read", "posts:write", "media:write")


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
async def channel(mcp_app: FastAPI, mcp_setup: Setup, engine: AsyncEngine) -> uuid.UUID:
    await clear_upload_quota(mcp_app.state.redis)
    return await make_channel(engine, mcp_setup.wid)


@pytest.fixture
async def key(client: httpx.AsyncClient, mcp_setup: Setup) -> str:
    made, _ = await make_key(client, mcp_setup, *WRITE_SCOPES)
    return made


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


def args(channel: uuid.UUID, **values: Any) -> dict[str, Any]:
    return {
        "account_id": str(channel),
        "title": "Sourdough in 60 seconds",
        "description": "How we fold the dough",
        "privacy": "public",
        "made_for_kids": False,
        "synthetic_media": False,
        "publish_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "file_name": "bread.mp4",
        "file_size": 2048,
        **values,
    }


async def call(app: FastAPI, key: str, name: str, arguments: dict[str, Any]) -> Any:
    async with connect(app, key) as mcp:
        return await mcp.call_tool(name, arguments)


async def test_prepare_is_previewed_then_opens_the_upload(
    mcp_app: FastAPI,
    key: str,
    channel: uuid.UUID,
    engine: AsyncEngine,
    fake_youtube: FakeYouTube,
) -> None:
    preview = structured(await call(mcp_app, key, "prepare_youtube_upload", args(channel)))
    assert (preview["preview"], preview["post_id"]) == (True, None)
    assert preview["confirmation_token"]
    assert "UTC)" in preview["publish_at"]
    assert all(item["ok"] for item in preview["checklist"]), preview["checklist"]
    assert await rows(engine, "SELECT 1 FROM scheduled_posts") == []
    assert fake_youtube.inserts == 0  # nothing reaches YouTube in a preview

    done = structured(await confirm(mcp_app, key, "prepare_youtube_upload", args(channel)))
    assert done["preview"] is False
    assert done["upload_url"].startswith(SESSION_PREFIX)
    assert done["chunk_bytes"] == 8 * 1024 * 1024
    assert done["upload_url"] in done["curl_hint"]
    assert '--upload-file "bread.mp4"' in done["curl_hint"]
    assert fake_youtube.inserts == 1
    [opened] = fake_youtube.named("open_session")
    assert (opened["size"], opened["metadata"]["privacy"]) == (2048, "private")
    [post] = await rows(engine, "SELECT id, status FROM scheduled_posts")
    assert (str(post["id"]), post["status"]) == (done["post_id"], "draft")
    [ticket] = await rows(engine, "SELECT * FROM mcp_uploads")
    assert ticket["kind"] == "youtube"
    assert done["upload_page_url"].endswith(f"/upload/{ticket['id']}")
    [audit] = await rows(engine, "SELECT * FROM audit_events WHERE action = 'post.created'")
    assert audit["target_id"] == done["post_id"]


async def test_made_for_kids_has_no_default(mcp_app: FastAPI, key: str, channel: uuid.UUID) -> None:
    missing = args(channel)
    del missing["made_for_kids"]
    result = await call(mcp_app, key, "prepare_youtube_upload", missing)
    assert result.is_error


async def test_only_a_youtube_channel_takes_an_upload(
    mcp_app: FastAPI, key: str, channel: uuid.UUID, mcp_setup: Setup
) -> None:
    result = await call(
        mcp_app, key, "prepare_youtube_upload", args(channel, account_id=mcp_setup.account_id)
    )
    assert error_of(result)["code"] == "validation_error"


async def test_the_status_finishes_an_upload_youtube_holds(
    mcp_app: FastAPI,
    key: str,
    channel: uuid.UUID,
    fake_youtube: FakeYouTube,
    engine: AsyncEngine,
) -> None:
    done = structured(await confirm(mcp_app, key, "prepare_youtube_upload", args(channel)))
    status = structured(
        await call(mcp_app, key, "get_youtube_upload_status", {"post_id": done["post_id"]})
    )
    assert (status["state"], status["route"], status["post_status"]) == (
        "uploading",
        "direct",
        "draft",
    )
    assert status["bytes_received"] == 0

    video = fake_youtube.finish_upload(done["upload_url"])  # Claude Code's curl
    status = structured(
        await call(mcp_app, key, "get_youtube_upload_status", {"post_id": done["post_id"]})
    )
    assert (status["state"], status["post_status"], status["video_id"]) == (
        "scheduled",
        "scheduled",
        video.id,
    )
    assert status["url"] == f"https://www.youtube.com/watch?v={video.id}"
    [post] = await rows(engine, "SELECT status FROM scheduled_posts")
    assert post["status"] == "scheduled"


async def test_the_upload_page_s_youtube_ticket(
    mcp_app: FastAPI,
    key: str,
    channel: uuid.UUID,
    mcp_setup: Setup,
    client: httpx.AsyncClient,
    fake_youtube: FakeYouTube,
) -> None:
    done = structured(await confirm(mcp_app, key, "prepare_youtube_upload", args(channel)))
    ticket_id = done["upload_page_url"].rsplit("/", 1)[1]
    url = f"/v1/w/{mcp_setup.wid}/mcp-uploads/{ticket_id}"

    got = (await client.get(url, headers=mcp_setup.headers)).json()
    assert (got["kind"], got["status"], got["upload"]) == ("youtube", "waiting", None)
    assert got["youtube"] == {
        "upload_url": done["upload_url"],
        "chunk_bytes": 8 * 1024 * 1024,
        "title": "Sourdough in 60 seconds",
        "channel_name": "Maple Bakery",
    }
    assert got["scheduled_post_id"] == done["post_id"]

    nothing = await client.post(f"{url}/complete", json={}, headers=mcp_setup.headers)
    assert nothing.status_code == 422

    video = fake_youtube.finish_upload(done["upload_url"])
    finished = await client.post(
        f"{url}/complete", json={"video_id": video.id}, headers=mcp_setup.headers
    )
    assert finished.status_code == 200, finished.text
    assert (finished.json()["status"], finished.json()["youtube"]) == ("uploaded", None)
    post = (
        await client.get(
            f"/v1/w/{mcp_setup.wid}/scheduled-posts/{done['post_id']}", headers=mcp_setup.headers
        )
    ).json()
    assert post["status"] == "scheduled"
    assert post["targets"][0]["youtube"]["video_id"] == video.id
