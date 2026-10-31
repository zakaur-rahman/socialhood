"""The MCP server under test (C-165): the API app with /mcp, its transport running, a Pro
workspace with a conversation, API keys made through the app, and the official SDK client
connected to the mounted app in-process (httpx2's ASGI transport; no network, no port).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import httpx2
import mcp_types as types
import pytest
from fastapi import FastAPI
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.main import create_app
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import set_plan
from tests.support.sending import Setup, workspace_with_thread

BASE = "http://api.test"
URL = f"{BASE}/mcp"
READ_SCOPES = (
    "conversations:read",
    "automations:read",
    "posts:read",
    "media:write",
    "comments:read",
    "analytics:read",
    "knowledge:read",
)


async def make_key(
    client: httpx.AsyncClient, setup: Setup, *scopes: str, name: str = "Codex laptop"
) -> tuple[str, str]:
    """A key made through the app (by the workspace's owner); returns (key, key id)."""
    response = await client.post(
        f"/v1/w/{setup.wid}/api-keys",
        json={"name": name, "scopes": list(scopes) or list(READ_SCOPES)},
        headers=setup.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["key"], response.json()["id"]


def http_client(app: FastAPI, key: str | None, **headers: str) -> httpx2.AsyncClient:
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url=BASE, headers=headers
    )


@asynccontextmanager
async def connect(app: FastAPI, key: str, *, mode: str = "legacy") -> AsyncIterator[Client]:
    """The SDK's client, connected with ``key`` (``mode``: legacy, auto or 2026-07-28)."""
    async with (
        http_client(app, key) as http,
        Client(
            streamable_http_client(URL, http_client=http, terminate_on_close=False),
            mode=mode,
            cache=None,
            client_info=types.Implementation(name="pytest-client", version="1.0"),
        ) as client,
    ):
        yield client


def structured(result: types.CallToolResult) -> dict[str, Any]:
    assert not result.is_error, result.content
    assert isinstance(result.structured_content, dict)
    return result.structured_content


def error_of(result: types.CallToolResult) -> dict[str, Any]:
    """The ``error`` object of a tool error."""
    assert result.is_error, result.structured_content
    block = result.content[0]
    assert isinstance(block, types.TextContent)
    body = json.loads(block.text)
    assert isinstance(body["error"], dict)
    return body["error"]


def rpc(method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> dict[str, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


# ---------------------------------------------------------------- fixtures (tests/conftest.py)


@pytest.fixture
async def mcp_app(api_settings: Settings, clean_db: None) -> AsyncIterator[FastAPI]:
    """An API app at http://api.test with the MCP transport running (create_app's lifespan does
    this in a server). It shares the test database with ``app``, where keys are made."""
    application = create_app(api_settings.model_copy(update={"api_base_url": BASE}))
    assert application.state.mcp is not None
    stale = [key async for key in application.state.redis.scan_iter("rl:*")]
    if stale:  # per-IP windows start empty for each test, as for ``app``
        await application.state.redis.delete(*stale)
    started, stop = asyncio.Event(), asyncio.Event()

    async def serve() -> None:  # one task enters and leaves the transport's task group
        async with application.state.mcp.session_manager.run():
            started.set()
            await stop.wait()

    task = asyncio.create_task(serve())
    await started.wait()
    try:
        yield application
    finally:
        stop.set()
        await task
        await application.state.http.aclose()
        await application.state.redis.aclose()
        await application.state.engine.dispose()


@pytest.fixture
async def mcp_setup(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    """A Pro workspace with one conversation (keys are made on Pro, PD-6)."""
    made = await workspace_with_thread(client, clerk, engine)
    await set_plan(engine, made.wid, "pro")
    return made
