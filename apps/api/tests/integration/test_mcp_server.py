"""C-165 phase A: the MCP server mounted at /mcp. Protocol (both eras, stateless), API-key
authentication and its 401s, the scope, role, plan and mode gates, the daily cap and rate
limits, the audit row, and that a key never reaches another workspace."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.security.ratelimit import LIMITS, Limit
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import set_plan
from tests.support.mcp import (
    ACCEPT,
    BASE,
    URL,
    connect,
    error_of,
    http_client,
    make_key,
    rpc,
    structured,
)
from tests.support.sending import Setup, clean_outbox, workspace_with_thread

PRM = f"{BASE}/.well-known/oauth-protected-resource/mcp"


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


async def audit_rows(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT * FROM mcp_tool_calls ORDER BY created_at"))
        return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------- protocol


async def test_initialize_list_and_call_with_the_handshake(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI
) -> None:
    key, _ = await make_key(client, setup, "conversations:read")
    async with connect(mcp_app, key, mode="legacy") as mcp:
        assert mcp.server_info is not None
        assert mcp.server_info.name == "Amplychat"
        assert mcp.protocol_version == "2025-11-25"
        assert "get_workspace" in (mcp.instructions or "")
        tools = (await mcp.list_tools()).tools
        assert [t.name for t in tools] == [
            "get_conversation",
            "get_workspace",
            "list_accounts",
            "list_conversations",
        ]
        for t in tools:
            assert t.annotations is not None
            assert t.annotations.read_only_hint is True
            assert t.annotations.destructive_hint is False
            assert t.annotations.idempotent_hint is True
            assert t.annotations.open_world_hint is False
            assert t.output_schema is not None
            assert t.title
        result = structured(await mcp.call_tool("get_workspace", {}))
        assert result["workspace"]["id"] == setup.wid
        assert result["workspace"]["plan"] == "pro"
        assert result["member"]["role"] == "owner"
        assert result["connection"]["kind"] == "api_key"
        assert result["connection"]["mode"] == "full"
        assert "workspace:read" in result["connection"]["scopes"]


async def test_the_stateless_2026_era_and_auto_negotiation(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI
) -> None:
    key, _ = await make_key(client, setup)
    for mode in ("2026-07-28", "auto"):
        async with connect(mcp_app, key, mode=mode) as mcp:
            assert mcp.protocol_version == "2026-07-28"
            names = [t.name for t in (await mcp.list_tools()).tools]
            assert names == sorted(names)
            assert "list_scheduled_posts" in names
            result = structured(await mcp.call_tool("list_accounts", {}))
            assert [a["id"] for a in result["items"]] == [setup.account_id]


def _init() -> dict[str, Any]:
    return {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "raw-http", "version": "0"},
    }


async def test_two_requests_need_no_session(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI
) -> None:
    """Stateless: no Mcp-Session-Id is issued, and a request without initialize is served, so
    any worker can answer any request."""
    key, _ = await make_key(client, setup)
    headers = {**ACCEPT, "MCP-Protocol-Version": "2025-11-25"}
    async with http_client(mcp_app, key) as http:
        first = await http.post(URL, json=rpc("initialize", _init()), headers=headers)
        assert first.status_code == 200, first.text
        assert "mcp-session-id" not in first.headers
        assert first.headers["x-robots-tag"] == "noindex, nofollow"
        for request_id in (2, 3):  # no session id, no initialize on this "connection"
            listed = await http.post(URL, json=rpc("tools/list", {}, request_id), headers=headers)
            assert listed.status_code == 200, listed.text
            assert "mcp-session-id" not in listed.headers
            assert listed.json()["id"] == request_id
            assert "get_workspace" in {t["name"] for t in listed.json()["result"]["tools"]}
        called = await http.post(
            URL,
            json=rpc("tools/call", {"name": "get_workspace", "arguments": {}}, 4),
            headers=headers,
        )
        assert called.json()["result"]["structuredContent"]["workspace"]["id"] == setup.wid


async def test_an_unknown_tool_is_a_protocol_error(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI
) -> None:
    key, _ = await make_key(client, setup)
    async with http_client(mcp_app, key) as http:
        response = await http.post(
            URL,
            json=rpc("tools/call", {"name": "delete_everything", "arguments": {}}),
            headers={**ACCEPT, "MCP-Protocol-Version": "2025-11-25"},
        )
    assert response.json()["error"]["code"] == -32602
    assert "Unknown tool" in response.json()["error"]["message"]


async def test_dns_rebinding_protection(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI
) -> None:
    key, _ = await make_key(client, setup)
    headers = {**ACCEPT, "MCP-Protocol-Version": "2025-11-25"}
    async with http_client(mcp_app, key) as http:
        evil_origin = await http.post(
            URL,
            json=rpc("tools/list", {}),
            headers={**headers, "Origin": "https://evil.example"},
        )
        assert evil_origin.status_code == 403
        evil_host = await http.post(
            "http://evil.test/mcp", json=rpc("tools/list", {}), headers=headers
        )
        assert evil_host.status_code == 421


# ---------------------------------------------------------------- authentication


async def test_no_token_is_401_pointing_at_the_resource_metadata(
    mcp_app: FastAPI, setup: Setup
) -> None:
    async with http_client(mcp_app, None) as http:
        response = await http.post(URL, json=rpc("tools/list", {}), headers=ACCEPT)
        assert response.status_code == 401
        # RFC 6750 §3.1: no error code when the request carried no credentials.
        assert response.headers["www-authenticate"] == f'Bearer resource_metadata="{PRM}"'
        for path in (PRM, f"{BASE}/.well-known/oauth-protected-resource"):
            prm = await http.get(path)
            assert prm.status_code == 200
            assert prm.json()["resource"] == URL  # exactly the URL clients connect to
            assert prm.json()["authorization_servers"] == [BASE]
            assert prm.json()["bearer_methods_supported"] == ["header"]
            assert "posts:write" in prm.json()["scopes_supported"]


@pytest.mark.parametrize(
    "token",
    [
        "shk_" + "x" * 43,  # the shape of a key, but no key
        "not-a-key",
        "sho_" + "x" * 43,  # OAuth access tokens arrive in phase C
    ],
)
async def test_a_bad_token_is_401_invalid_token(mcp_app: FastAPI, setup: Setup, token: str) -> None:
    async with http_client(mcp_app, token) as http:
        response = await http.post(URL, json=rpc("tools/list", {}), headers=ACCEPT)
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith('Bearer error="invalid_token"')
    assert 'error_description="That API key isn\'t valid."' in challenge
    assert f'resource_metadata="{PRM}"' in challenge


async def test_a_revoked_key_stops_at_once(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI
) -> None:
    key, key_id = await make_key(client, setup)
    async with connect(mcp_app, key) as mcp:
        structured(await mcp.call_tool("get_workspace", {}))
    revoked = await client.delete(f"/v1/w/{setup.wid}/api-keys/{key_id}", headers=setup.headers)
    assert revoked.status_code == 200
    async with http_client(mcp_app, key) as http:
        response = await http.post(URL, json=rpc("tools/list", {}), headers=ACCEPT)
    assert response.status_code == 401
    assert "revoked" in response.headers["www-authenticate"]


async def test_a_key_whose_maker_left_is_refused(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    key, key_id = await make_key(client, setup)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE api_keys SET created_by_user_id = NULL WHERE id = :k"), {"k": key_id}
        )
    async with http_client(mcp_app, key) as http:
        response = await http.post(URL, json=rpc("tools/list", {}), headers=ACCEPT)
    assert response.status_code == 401
    assert "no longer in the workspace" in response.headers["www-authenticate"]


async def test_guessing_keys_is_limited_per_ip(
    mcp_app: FastAPI, setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(LIMITS, "public", Limit("public", 2, 60))
    async with http_client(mcp_app, "shk_" + "y" * 43) as http:
        codes = [
            (await http.post(URL, json=rpc("tools/list", {}), headers=ACCEPT)).status_code
            for _ in range(3)
        ]
    assert codes == [401, 401, 429]


# ---------------------------------------------------------------- scopes, roles, plan, mode


async def test_tools_need_their_scope(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    key, _ = await make_key(client, setup, "contacts:read")  # a public-API-only key
    async with connect(mcp_app, key) as mcp:
        names = [t.name for t in (await mcp.list_tools()).tools]
        assert names == ["get_workspace", "list_accounts"]  # workspace:read is always granted
        error = error_of(await mcp.call_tool("list_conversations", {}))
    assert error["code"] == "forbidden"
    assert "conversations:read" in error["message"]
    rows = await audit_rows(engine)
    assert (rows[-1]["tool"], rows[-1]["outcome"], rows[-1]["error_code"]) == (
        "list_conversations",
        "refused",
        "forbidden",
    )


async def test_the_role_caps_the_tools(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    key, _ = await make_key(client, setup)
    async with engine.begin() as conn:  # the key's maker is demoted after making it
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": setup.wid},
        )
    async with connect(mcp_app, key) as mcp:
        names = {t.name for t in (await mcp.list_tools()).tools}
        assert "list_conversations" in names
        assert not names & {"list_scheduled_posts", "list_automations", "search_knowledge"}
        error = error_of(await mcp.call_tool("list_automations", {}))
        assert error["code"] == "forbidden"
        assert structured(await mcp.call_tool("get_workspace", {}))["member"]["role"] == "agent"


async def test_free_reads_with_a_daily_cap(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine, redis: Redis
) -> None:
    key, _ = await make_key(client, setup)
    await set_plan(engine, setup.wid, "free")  # a key made on Pro, the workspace back on Free
    async with connect(mcp_app, key) as mcp:
        workspace = structured(await mcp.call_tool("get_workspace", {}))
        assert workspace["workspace"]["plan"] == "free"
        assert workspace["connection"]["mode"] == "read_drafts"
        assert workspace["connection"]["mode_setting"] == "full"
        assert workspace["connection"]["plan_allows"] == "read_drafts"
        assert workspace["usage"] == {"tool_calls_today": 1, "tool_calls_daily_limit": 100}
        structured(await mcp.call_tool("list_conversations", {}))  # reads stay open on Free
        await redis.set(f"mcp-calls:{setup.wid}:{datetime.now(UTC):%Y-%m-%d}", 100)
        error = error_of(await mcp.call_tool("list_accounts", {}))
    assert error["code"] == "quota_exceeded"
    assert error["entitlement"] == "mcp_calls_daily"
    assert error["limit"] == 100
    assert "100 AI app tool calls a day" in error["message"]
    assert error["plans_url"].endswith("/pricing")


async def test_the_kill_switch_turns_the_workspace_off(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    key, _ = await make_key(client, setup)
    await set_mode(engine, setup.wid, "off")
    async with connect(mcp_app, key) as mcp:
        assert [t.name for t in (await mcp.list_tools()).tools] == ["get_workspace"]
        error = error_of(await mcp.call_tool("list_conversations", {}))
        assert error["code"] == "forbidden"
        assert "turned off" in error["message"]
        workspace = structured(await mcp.call_tool("get_workspace", {}))
        assert workspace["connection"]["mode"] == "off"
        assert "turned off" in workspace["caveats"][0]
    await set_mode(engine, setup.wid, "read_only")
    async with connect(mcp_app, key) as mcp:
        structured(await mcp.call_tool("list_conversations", {}))


async def set_mode(engine: AsyncEngine, wid: str, mode: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET ai_connections_mode = :m WHERE id = :w"),
            {"m": mode, "w": wid},
        )


async def test_calls_are_rate_limited_per_connection(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(LIMITS, "mcp", Limit("mcp", 2, 60))
    key, _ = await make_key(client, setup)
    other, _ = await make_key(client, setup, name="Claude Code")
    async with connect(mcp_app, key) as mcp:
        structured(await mcp.call_tool("get_workspace", {}))
        structured(await mcp.call_tool("get_workspace", {}))
        error = error_of(await mcp.call_tool("get_workspace", {}))
    assert error["code"] == "rate_limited"
    assert error["retry_after_s"] >= 1
    async with connect(mcp_app, other) as mcp:  # another connection has its own window
        structured(await mcp.call_tool("get_workspace", {}))


# ---------------------------------------------------------------- audit and tenancy


async def test_every_call_leaves_an_audit_row(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    key, key_id = await make_key(client, setup)
    async with connect(mcp_app, key) as mcp:
        structured(await mcp.call_tool("list_conversations", {"query": "price", "limit": 3}))
        error_of(await mcp.call_tool("list_conversations", {"limit": 500}))
    ok, refused = await audit_rows(engine)
    assert str(ok["workspace_id"]) == setup.wid
    assert str(ok["api_key_id"]) == key_id
    assert ok["credential_kind"] == "api_key"
    assert ok["credential_label"] == "API key “Codex laptop”"
    assert ok["user_id"] is not None
    assert ok["tool"] == "list_conversations"
    assert ok["arguments"] == {"query": "price", "limit": 3}
    assert len(ok["arguments_digest"]) == 64
    assert ok["outcome"] == "ok"
    assert ok["error_code"] is None
    assert ok["latency_ms"] >= 0
    assert ok["client_name"]  # the client's clientInfo, else its User-Agent
    assert (refused["outcome"], refused["error_code"]) == ("refused", "validation_error")


async def test_a_key_never_reaches_another_workspace(
    client: httpx.AsyncClient, clerk: Clerk, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    other = await workspace_with_thread(client, clerk, engine, email="other@example.com")
    await set_plan(engine, other.wid, "pro")
    key, _ = await make_key(client, setup)
    async with connect(mcp_app, key) as mcp:
        error = error_of(
            await mcp.call_tool("get_conversation", {"conversation_id": other.conversation_id})
        )
        assert error["code"] == "not_found"
        mine = structured(await mcp.call_tool("list_conversations", {}))
        assert [c["conversation_id"] for c in mine["items"]] == [setup.conversation_id]
        accounts = structured(await mcp.call_tool("list_accounts", {}))
        assert [a["id"] for a in accounts["items"]] == [setup.account_id]
        error = error_of(await mcp.call_tool("get_best_times", {"account": other.account_id}))
        assert error["code"] == "not_found"


async def test_ids_of_unknown_rows_are_not_found(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI
) -> None:
    key, _ = await make_key(client, setup)
    async with connect(mcp_app, key) as mcp:
        for name, args in (
            ("get_conversation", {"conversation_id": str(uuid.uuid4())}),
            ("get_scheduled_post", {"post_id": str(uuid.uuid4())}),
            ("get_media_upload", {"upload_id": str(uuid.uuid4())}),
        ):
            assert error_of(await mcp.call_tool(name, args))["code"] == "not_found", name


async def test_the_mcp_server_can_be_switched_off(api_settings: Settings, clean_db: None) -> None:
    from socialhood.main import create_app

    application = create_app(api_settings.model_copy(update={"mcp_enabled": False}))
    try:
        assert application.state.mcp is None
        async with http_client(application, "shk_" + "z" * 43) as http:
            assert (await http.post(URL, json=rpc("tools/list", {}))).status_code == 404
    finally:
        await application.state.http.aclose()
        await application.state.redis.aclose()
        await application.state.engine.dispose()


async def test_owners_and_admins_set_the_mode(
    client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    url = f"/v1/w/{setup.wid}/ai-connections/settings"
    shown = await client.get(url, headers=setup.headers)
    assert shown.json() == {
        "mode": "full",
        "effective_mode": "full",
        "plan_allows": ["off", "read_only", "read_drafts", "full"],
    }
    key, _ = await make_key(client, setup)
    changed = await client.put(url, json={"mode": "off"}, headers=setup.headers)
    assert changed.status_code == 200, changed.text
    assert changed.json()["effective_mode"] == "off"
    async with connect(mcp_app, key) as mcp:  # the next call sees it
        assert [t.name for t in (await mcp.list_tools()).tools] == ["get_workspace"]
    async with engine.connect() as conn:
        action = (await conn.execute(text("SELECT action FROM audit_events"))).scalar_one()
    assert action == "ai_connections.mode_changed"
    await set_plan(engine, setup.wid, "free")
    refused = await client.put(url, json={"mode": "full"}, headers=setup.headers)
    assert refused.status_code == 402
    assert refused.json()["entitlement"] == "ai_connections"
    assert (await client.put(url, json={"mode": "read_drafts"}, headers=setup.headers)).json()[
        "effective_mode"
    ] == "read_drafts"
