"""C-165 phase A: each MCP read tool through the SDK client against the mounted app, a happy
path and an error path, results matching their output schema, customer text only in ``_text``
fields."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jsonschema
import mcp_types as types
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.mcp.results import UNTRUSTED_NOTE
from tests.support.ai import make_source
from tests.support.automations import make_automation
from tests.support.mcp import (
    connect,
    error_of,
    make_key,
    structured,
)
from tests.support.sending import Setup, clean_outbox


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


@pytest.fixture
async def key(client: httpx.AsyncClient, setup: Setup) -> str:
    made, _ = await make_key(client, setup)
    return made


async def call(app: FastAPI, key: str, name: str, args: dict[str, Any]) -> types.CallToolResult:
    """Call ``name`` and check a success against the tool's advertised output schema."""
    async with connect(app, key) as mcp:
        tools = {t.name: t for t in (await mcp.list_tools()).tools}
        result = await mcp.call_tool(name, args)
    if not result.is_error:
        schema = tools[name].output_schema
        assert schema is not None
        jsonschema.validate(result.structured_content, schema)
    return result


async def test_get_workspace(mcp_app: FastAPI, key: str, setup: Setup) -> None:
    result = structured(await call(mcp_app, key, "get_workspace", {}))
    assert result["workspace"]["timezone"] == "UTC"
    assert result["dashboard_url"].endswith("/home")
    error = error_of(await call(mcp_app, key, "get_workspace", {"workspace_id": setup.wid}))
    assert error["code"] == "validation_error"  # one connection, one workspace: no argument
    assert error["field_errors"][0]["field"] == "workspace_id"


async def test_list_accounts(mcp_app: FastAPI, key: str, setup: Setup) -> None:
    result = structured(await call(mcp_app, key, "list_accounts", {}))
    [account] = result["items"]
    assert account["id"] == setup.account_id
    assert account["status"] == "active"
    assert account["needs_reconnect"] is False
    whatsapp = structured(await call(mcp_app, key, "list_accounts", {"platform": "whatsapp"}))
    assert whatsapp["items"] == []
    error = error_of(await call(mcp_app, key, "list_accounts", {"platform": "tiktok"}))
    assert error["code"] == "validation_error"


async def test_scheduled_posts(
    client: httpx.AsyncClient, mcp_app: FastAPI, key: str, setup: Setup
) -> None:
    made = await client.post(
        f"/v1/w/{setup.wid}/scheduled-posts",
        json={
            "caption": "Diwali boxes are back",
            "targets": [{"social_account_id": setup.account_id}],
            "publish_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
        headers=setup.headers,
    )
    assert made.status_code == 201, made.text
    post_id = made.json()["id"]

    drafts = structured(await call(mcp_app, key, "list_scheduled_posts", {"status": "draft"}))
    assert [p["post_id"] for p in drafts["items"]] == [post_id]
    assert drafts["items"][0]["caption_start"] == "Diwali boxes are back"
    assert "UTC)" in drafts["items"][0]["publish_at"]  # local time and UTC
    assert drafts["items"][0]["dashboard_url"].endswith(f"/schedule/{post_id}")
    bad = error_of(await call(mcp_app, key, "list_scheduled_posts", {"period": "blorp"}))
    assert bad["code"] == "validation_error"

    post = structured(await call(mcp_app, key, "get_scheduled_post", {"post_id": post_id}))
    assert post["status"] == "draft"
    assert post["caption"] == "Diwali boxes are back"
    assert post["accounts"][0]["account_id"] == setup.account_id
    assert post["ready"] is False  # no media yet
    assert any(c["key"] == "media" and not c["ok"] for c in post["checklist"])
    missing = error_of(await call(mcp_app, key, "get_scheduled_post", {"post_id": "nope"}))
    assert missing["code"] == "validation_error"


async def test_get_best_times(mcp_app: FastAPI, key: str, setup: Setup) -> None:
    result = structured(await call(mcp_app, key, "get_best_times", {"account": setup.account_id}))
    assert result["enough_history"] is False
    assert len(result["days"]) == 7
    assert result["days"][0]["weekday"] == "Monday"
    assert result["caveats"]
    error = error_of(await call(mcp_app, key, "get_best_times", {"account": "@nobody.here"}))
    assert error["code"] == "not_found"


async def test_list_media(mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO media_assets (workspace_id, public_id, resource_type, purpose, "
                "format, bytes, width, height, secure_url) VALUES (:w, :p, 'image', 'post', "
                "'jpg', 1000, 1080, 1350, 'https://res.cloudinary.com/x/image/upload/a.jpg')"
            ),
            {"w": setup.wid, "p": f"ws/{setup.wid}/post/a"},
        )
    result = structured(await call(mcp_app, key, "list_media", {}))
    [item] = result["items"]
    assert (item["type"], item["format"], item["width"]) == ("image", "jpg", 1080)
    assert result["next_cursor"] is None
    error = error_of(
        await call(mcp_app, key, "list_media", {"since": "2026-10-10", "until": "2026-10-01"})
    )
    assert error["code"] == "validation_error"


async def test_get_media_upload(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    upload_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO mcp_uploads (id, workspace_id, kind, status, expires_at) "
                "VALUES (:id, :w, 'video', 'waiting', :at)"
            ),
            {"id": upload_id, "w": setup.wid, "at": datetime.now(UTC) + timedelta(minutes=30)},
        )
    result = structured(await call(mcp_app, key, "get_media_upload", {"upload_id": str(upload_id)}))
    assert (result["status"], result["kind"], result["media_id"]) == ("waiting", "video", None)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE mcp_uploads SET expires_at = :at WHERE id = :id"),
            {"id": upload_id, "at": datetime.now(UTC) - timedelta(minutes=1)},
        )
    expired = structured(
        await call(mcp_app, key, "get_media_upload", {"upload_id": str(upload_id)})
    )
    assert expired["status"] == "expired"
    error = error_of(await call(mcp_app, key, "get_media_upload", {"upload_id": str(uuid.uuid4())}))
    assert error["code"] == "not_found"


async def test_conversations_label_customer_text(mcp_app: FastAPI, key: str, setup: Setup) -> None:
    async with connect(mcp_app, key) as mcp:
        listed = await mcp.call_tool("list_conversations", {"view": "all"})
        detail = await mcp.call_tool(
            "get_conversation", {"conversation_id": setup.conversation_id, "limit": 5}
        )
        refused = await mcp.call_tool("list_conversations", {"account": "@nobody.here"})
    items = structured(listed)["items"]
    assert [i["conversation_id"] for i in items] == [setup.conversation_id]
    assert items[0]["contact_name_text"]
    assert items[0]["dashboard_url"].endswith(f"/inbox/{setup.conversation_id}")
    text_copy = listed.content[0]
    assert isinstance(text_copy, types.TextContent)
    assert UNTRUSTED_NOTE in text_copy.text  # the label sits before the customer's words
    body = structured(detail)
    assert body["conversation_id"] == setup.conversation_id
    assert body["messages"]
    assert all(set(m) >= {"sender", "message_text"} for m in body["messages"])
    assert "text" not in body["messages"][0]  # customer words only in *_text fields
    assert error_of(refused)["code"] == "not_found"


async def test_get_post_comments_summary(mcp_app: FastAPI, key: str) -> None:
    result = structured(await call(mcp_app, key, "get_post_comments_summary", {}))
    assert result["scope"].startswith("comments made")
    assert result["sentiment"]["total"] == 0
    assert result["topics"] == []
    assert result["unanswered_questions"] == []
    latest = error_of(await call(mcp_app, key, "get_post_comments_summary", {"post": "latest"}))
    assert latest["code"] == "not_found"
    bad = error_of(await call(mcp_app, key, "get_post_comments_summary", {"post": "my reel"}))
    assert (bad["code"], bad["field_errors"][0]["field"]) == ("validation_error", "post")


async def test_get_analytics_summary(mcp_app: FastAPI, key: str) -> None:
    account = structured(await call(mcp_app, key, "get_analytics_summary", {"scope": "account"}))
    assert account["scope"] == "account"
    assert account["metrics"]
    assert account["current"]["days"] >= 1
    top = structured(
        await call(mcp_app, key, "get_analytics_summary", {"scope": "top_posts", "limit": 3})
    )
    assert (top["metric"], top["top_posts"], top["considered"]) == ("reach", [], 0)
    error = error_of(await call(mcp_app, key, "get_analytics_summary", {"scope": "post"}))
    assert error["code"] == "validation_error"
    missing = error_of(
        await call(
            mcp_app, key, "get_analytics_summary", {"scope": "post", "post_id": str(uuid.uuid4())}
        )
    )
    assert missing["code"] == "not_found"


async def test_search_knowledge(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    source = await make_source(engine, workspace_id=setup.wid)
    result = structured(
        await call(mcp_app, key, "search_knowledge", {"query": "How much is shipping?"})
    )
    assert result["passages"][0]["source_id"] == str(source)
    assert "free on orders" in result["passages"][0]["excerpt_text"]
    error = error_of(await call(mcp_app, key, "search_knowledge", {"query": ""}))
    assert error["code"] == "validation_error"


async def test_list_automations(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    automation = await make_automation(engine, workspace_id=setup.wid, account_id=setup.account_id)
    result = structured(await call(mcp_app, key, "list_automations", {"status": "active"}))
    [item] = result["items"]
    assert item["automation_id"] == str(automation)
    assert item["name"] == "Send the link"
    assert item["dashboard_url"].endswith(f"/automations/{automation}")
    error = error_of(await call(mcp_app, key, "list_automations", {"status": "deleted"}))
    assert error["code"] == "validation_error"
