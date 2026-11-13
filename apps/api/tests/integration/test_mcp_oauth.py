"""C-165 phase C: the OAuth authorization server and OAuth tokens on /mcp.

The whole flow end to end (register, authorize, consent as the signed-in Clerk test user, token,
a tool call), then the security properties one by one: PKCE, exact redirect URIs, single-use
codes, refresh rotation and reuse detection, audience binding, expiry, revocation, workspace
binding, the scope step-up (HTTP 403 and ChatGPT's tool-result form), CIMD fetch safety, DCR
input validation, the rate limits, and the operators' block list (scripts/block_oauth_client.py)."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import httpx2
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.security import ssrf
from socialhood.security.ratelimit import LIMITS, Limit
from tests.support.api import Clerk, sign_in
from tests.support.mcp import ACCEPT, BASE, URL, connect, error_of, http_client, rpc, structured
from tests.support.oauth import (
    CHATGPT,
    FORM,
    LOOPBACK,
    RESOURCE,
    Flow,
    public_flow,
    query,
    register,
)
from tests.support.sending import Setup, clean_outbox

CIMD_URL = "https://client.example/oauth/metadata.json"
BLOCK_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "block_oauth_client.py"


def load_block_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("block_oauth_client", BLOCK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


block_script = load_block_script()


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


async def _sql(engine: AsyncEngine, statement: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(statement), params)


async def _rows(engine: AsyncEngine, statement: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(statement), params)]


async def _mcp_status(app: FastAPI, token: str) -> httpx2.Response:
    headers = {**ACCEPT, "MCP-Protocol-Version": "2025-11-25"}
    async with http_client(app, token) as http:
        return await http.post(URL, json=rpc("tools/list", {}), headers=headers)


# ---------------------------------------------------------------- discovery


async def test_metadata_names_a_working_issuer(mcp_app: FastAPI) -> None:
    async with http_client(mcp_app, None) as http:
        prm = (await http.get("/.well-known/oauth-protected-resource/mcp")).json()
        meta = (await http.get("/.well-known/oauth-authorization-server")).json()
    assert prm["resource"] == RESOURCE
    assert prm["authorization_servers"] == [meta["issuer"]] == [BASE]
    assert meta["authorization_endpoint"] == f"{BASE}/oauth/authorize"
    assert meta["token_endpoint"] == f"{BASE}/oauth/token"
    assert meta["registration_endpoint"] == f"{BASE}/oauth/register"
    assert meta["revocation_endpoint"] == f"{BASE}/oauth/revoke"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["response_types_supported"] == ["code"]
    assert "none" in meta["token_endpoint_auth_methods_supported"]
    assert meta["client_id_metadata_document_supported"] is True
    assert meta["authorization_response_iss_parameter_supported"] is True
    assert "offline_access" in meta["scopes_supported"]
    assert "offline_access" not in prm["scopes_supported"]  # the spec: not a resource scope


# ---------------------------------------------------------------- end to end


async def test_connect_consent_token_and_call_a_tool(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    request_id = await flow.request_id()

    consent = await flow.consent(setup, request_id)
    assert consent.status_code == 200, consent.text
    page = consent.json()
    assert page["client"]["name"] == "Inspector"
    assert page["client"]["loopback"] is True
    assert page["client"]["redirect_host"] == "127.0.0.1"
    assert page["client"]["verified_host"] is None  # registered itself: name not checked
    assert page["client"]["logo_url"] is None
    assert [g["id"] for g in page["groups"]] == ["publishing", "inbox"]
    assert [w["id"] for w in page["workspaces"]] == [setup.wid]
    assert page["workspaces"][0]["can_connect"] is True
    assert page["member"]["email"] == "owner@example.com"

    approved = await flow.approve(setup, request_id)
    back = query(approved.json()["redirect_to"])
    assert approved.json()["redirect_to"].startswith(LOOPBACK + "?")
    assert back["state"] == flow.state
    assert back["iss"] == BASE

    issued = await flow.exchange(back["code"])
    assert issued.status_code == 200, issued.text
    assert issued.headers["cache-control"] == "no-store"
    body = issued.json()
    assert body["access_token"].startswith("sho_")
    assert body["refresh_token"].startswith("shr_")
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["scope"].split() == ["workspace:read", "posts:read", "conversations:read"]

    async with connect(mcp_app, body["access_token"]) as mcp:
        names = {t.name for t in (await mcp.list_tools()).tools}
        assert {"get_workspace", "list_conversations", "list_scheduled_posts"} <= names
        assert "search_knowledge" not in names
        result = structured(await mcp.call_tool("get_workspace", {}))
    assert result["workspace"]["id"] == setup.wid
    assert result["connection"]["kind"] == "oauth"

    stored = await _rows(engine, "SELECT token_hash FROM oauth_tokens")
    assert all(body["access_token"] not in str(r) for r in stored)  # hashes only
    audit = await _rows(engine, "SELECT * FROM mcp_tool_calls")
    assert audit[-1]["credential_kind"] == "oauth"
    assert audit[-1]["connection_id"] is not None
    assert audit[-1]["api_key_id"] is None

    async with http_client(mcp_app, None, **setup.headers) as http:
        listed = (await http.get(f"/v1/w/{setup.wid}/ai-connections")).json()
    assert listed["can_manage_all"] is True
    [item] = listed["items"]
    assert item["client_name"] == "Inspector"
    assert item["is_yours"] is True
    assert item["calls_7d"] == 1
    assert item["recent_calls"][0]["tool"] == "get_workspace"


# ---------------------------------------------------------------- PKCE


async def test_pkce_is_required_and_the_wrong_verifier_fails(
    mcp_app: FastAPI, setup: Setup
) -> None:
    # A client known by its metadata document gets its errors back at its redirect URI.
    mcp_app.state.cimd_fetch = FakeFetch(_document())
    listed = Flow(app=mcp_app, client_id=CIMD_URL)
    for overrides in (
        {"code_challenge": None},
        {"code_challenge_method": "plain"},
        {"code_challenge_method": None},
        {"code_challenge": "short"},
    ):
        response = await listed.authorize(**overrides)
        assert response.status_code == 302
        back = query(response.headers["location"])
        assert back["error"] == "invalid_request"
        assert back["state"] == listed.state
        assert back["iss"] == BASE

    flow = await public_flow(mcp_app)
    code = await flow.code(setup)
    wrong = await flow.exchange(code, code_verifier="x" * 64)
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "invalid_grant"
    missing = await flow.exchange(code, code_verifier=None)  # type: ignore[arg-type]
    assert missing.json()["error"] == "invalid_grant"


# ---------------------------------------------------------------- redirect URIs


async def test_redirect_uris_match_exactly_and_loopback_on_any_port(
    mcp_app: FastAPI, setup: Setup
) -> None:
    flow = await public_flow(mcp_app)
    for bad in (
        "https://evil.example/callback",
        "http://127.0.0.1:33418/other",
        "http://127.0.0.1.evil.example/callback",
        LOOPBACK + "?x=1",
    ):
        response = await flow.authorize(redirect_uri=bad)
        assert response.status_code == 400  # shown to the person, never redirected
        assert "location" not in response.headers
        assert "can't connect" in response.text
    other_port = "http://127.0.0.1:51999/callback"
    ok = await flow.authorize(redirect_uri=other_port)
    assert ok.status_code == 302

    # The token request must name the authorization's redirect URI exactly.
    code = await flow.code(setup)
    mismatch = await flow.exchange(code, redirect_uri=other_port)
    assert mismatch.json()["error"] == "invalid_grant"


async def test_an_unknown_client_is_shown_not_redirected(mcp_app: FastAPI) -> None:
    flow = Flow(app=mcp_app, client_id="dcr_does_not_exist")
    response = await flow.authorize()
    assert response.status_code == 400
    assert "location" not in response.headers


async def test_a_self_registered_clients_errors_are_shown_not_redirected(mcp_app: FastAPI) -> None:
    """Anyone can register any redirect URI, so an error before consent never sends the browser
    there: a link to us would otherwise land on it with no click and no sign-in."""
    flow = await public_flow(mcp_app, redirect_uri="https://evil.example/x")
    for overrides in (
        {"response_type": "token"},
        {"code_challenge": None},
        {"resource": "https://other.example/mcp"},
        {"state": "s" * 1001},
    ):
        response = await flow.authorize(**overrides)
        assert response.status_code == 400
        assert "location" not in response.headers
        assert "can't connect" in response.text
    assert (await flow.authorize()).status_code == 302  # a good request still reaches consent


# ---------------------------------------------------------------- codes


async def test_a_code_works_once_and_its_reuse_revokes_the_connection(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    code = await flow.code(setup)
    first = await flow.exchange(code)
    assert first.status_code == 200
    assert (await _mcp_status(mcp_app, first.json()["access_token"])).status_code == 200

    again = await flow.exchange(code)
    assert again.status_code == 400
    assert again.json()["error"] == "invalid_grant"
    refused = await _mcp_status(mcp_app, first.json()["access_token"])
    assert refused.status_code == 401
    assert "disconnected" in refused.headers["www-authenticate"]
    [row] = await _rows(engine, "SELECT revoke_reason FROM mcp_connections")
    assert row["revoke_reason"] == "code_reuse"


async def test_an_expired_code_and_another_clients_code_fail(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    other = await public_flow(mcp_app)
    code = await flow.code(setup)
    stolen = await other.exchange(code, code_verifier=flow.verifier)
    assert stolen.json()["error"] == "invalid_grant"
    await _sql(engine, "UPDATE oauth_codes SET expires_at = now() - interval '1 second'")
    late = await flow.exchange(code)
    assert late.json()["error"] == "invalid_grant"


# ---------------------------------------------------------------- refresh


async def test_refresh_rotates_and_reuse_revokes_the_family(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    first = await flow.tokens(setup)
    rotated = await flow.refresh(first["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert (await _mcp_status(mcp_app, second["access_token"])).status_code == 200

    reused = await flow.refresh(first["refresh_token"])
    assert reused.status_code == 400
    assert reused.json()["error"] == "invalid_grant"
    # The whole connection is gone: the newest tokens too.
    assert (await _mcp_status(mcp_app, second["access_token"])).status_code == 401
    dead = await flow.refresh(second["refresh_token"])
    assert dead.json()["error"] == "invalid_grant"
    [row] = await _rows(engine, "SELECT revoke_reason FROM mcp_connections")
    assert row["revoke_reason"] == "refresh_reuse"


async def test_a_refresh_cant_add_scopes_or_change_resource(mcp_app: FastAPI, setup: Setup) -> None:
    flow = await public_flow(mcp_app)
    first = await flow.tokens(setup)
    wider = await flow.refresh(first["refresh_token"], scope="posts:write")
    assert wider.json()["error"] == "invalid_scope"
    elsewhere = await flow.refresh(first["refresh_token"], resource="https://other.example/mcp")
    assert elsewhere.json()["error"] == "invalid_target"
    same = await flow.refresh(first["refresh_token"], scope="posts:read offline_access")
    assert same.status_code == 200


async def test_an_idle_connection_ends(mcp_app: FastAPI, setup: Setup, engine: AsyncEngine) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    await _sql(
        engine,
        "UPDATE mcp_connections SET last_used_at = now() - interval '31 days', "
        "created_at = now() - interval '40 days'",
    )
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 401
    assert (await flow.refresh(issued["refresh_token"])).json()["error"] == "invalid_grant"


# ---------------------------------------------------------------- audience


async def test_tokens_are_bound_to_this_servers_mcp(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    elsewhere = await flow.authorize(resource="https://other.example/mcp")
    assert elsewhere.status_code == 400  # shown, as for any self-registered client
    assert "only issues tokens for its /mcp endpoint" in elsewhere.text
    # Upper-case scheme and host are the same resource (the spec asks servers to accept them).
    assert (await flow.authorize(resource="HTTP://API.TEST/mcp/")).status_code == 302

    code = await flow.code(setup)
    wrong = await flow.exchange(code, resource="https://other.example/mcp")
    assert wrong.json()["error"] == "invalid_target"

    issued = await flow.tokens(setup)
    await _sql(engine, "UPDATE mcp_connections SET resource = 'https://other.example/mcp'")
    refused = await _mcp_status(mcp_app, issued["access_token"])
    assert refused.status_code == 401
    assert "another server" in refused.headers["www-authenticate"]


# ---------------------------------------------------------------- expiry and revocation


async def test_an_expired_access_token_is_refused(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    await _sql(
        engine,
        "UPDATE oauth_tokens SET expires_at = now() - interval '1 second' WHERE kind = 'access'",
    )
    refused = await _mcp_status(mcp_app, issued["access_token"])
    assert refused.status_code == 401
    assert 'error="invalid_token"' in refused.headers["www-authenticate"]
    assert "expired" in refused.headers["www-authenticate"]
    assert (await flow.refresh(issued["refresh_token"])).status_code == 200


async def test_revoking_in_settings_stops_the_connection_at_once(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 200
    [row] = await _rows(engine, "SELECT id FROM mcp_connections")
    async with http_client(mcp_app, None, **setup.headers) as http:
        gone = await http.delete(f"/v1/w/{setup.wid}/ai-connections/{row['id']}")
        assert gone.status_code == 204
        listed = (await http.get(f"/v1/w/{setup.wid}/ai-connections")).json()
    assert listed["items"] == []
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 401
    assert (await flow.refresh(issued["refresh_token"])).json()["error"] == "invalid_grant"
    audit = await _rows(engine, "SELECT action FROM audit_events")
    assert {"action": "ai_connections.revoked"} in audit


async def test_disconnect_all(mcp_app: FastAPI, setup: Setup) -> None:
    flow = await public_flow(mcp_app)
    one, two = await flow.tokens(setup), await flow.tokens(setup)
    async with http_client(mcp_app, None, **setup.headers) as http:
        done = await http.post(f"/v1/w/{setup.wid}/ai-connections/revoke-all")
    assert done.json() == {"revoked": 2}
    for issued in (one, two):
        assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 401


async def test_rfc7009_revocation(mcp_app: FastAPI, setup: Setup) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    assert (await flow.revoke("shr_not-a-token-we-know-of-at-all")).status_code == 200
    other = await public_flow(mcp_app)
    assert (await other.revoke(issued["refresh_token"])).status_code == 200  # ignored
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 200

    assert (await flow.revoke(issued["access_token"])).status_code == 200
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 401
    renewed = (await flow.refresh(issued["refresh_token"])).json()
    assert (await flow.revoke(renewed["refresh_token"])).status_code == 200
    assert (await _mcp_status(mcp_app, renewed["access_token"])).status_code == 401


# ---------------------------------------------------------------- workspaces and members


async def test_one_connection_one_workspace(
    mcp_app: FastAPI, setup: Setup, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    flow = await public_flow(mcp_app)
    _, stranger = await sign_in(client, clerk, email="stranger@example.com")
    foreign = stranger["workspaces"][0]["id"]
    request_id = await flow.request_id()
    refused = await flow.approve(setup, request_id, workspace_id=foreign)
    assert refused.status_code == 404
    issued = await flow.tokens(setup)
    async with connect(mcp_app, issued["access_token"]) as mcp:
        result = structured(await mcp.call_tool("get_workspace", {}))
    assert result["workspace"]["id"] == setup.wid


async def test_a_member_who_leaves_loses_the_connection(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    await _sql(engine, "DELETE FROM workspace_members WHERE workspace_id = :w", w=setup.wid)
    refused = await _mcp_status(mcp_app, issued["access_token"])
    assert refused.status_code == 401
    assert "no longer a member" in refused.headers["www-authenticate"]
    assert (await flow.refresh(issued["refresh_token"])).json()["error"] == "invalid_grant"


async def test_a_removed_members_connection_stays_revoked_when_they_return(
    mcp_app: FastAPI, setup: Setup, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    """Removing a member revokes their AI app connections (§3.6), so inviting them back doesn't
    quietly give an old app its access again."""
    sam_clerk, sam = await sign_in(client, clerk, email="sam@example.com")
    join = "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (:w, :u, 'agent')"
    await _sql(engine, join, w=setup.wid, u=sam["id"])
    as_sam = Setup(sam_clerk, setup.wid, setup.account_id, setup.thread, clerk.headers(sam_clerk))
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(as_sam)
    owners = await flow.tokens(setup)
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 200

    removed = await client.delete(f"/v1/w/{setup.wid}/members/{sam['id']}", headers=setup.headers)
    assert removed.status_code == 204, removed.text
    rows = await _rows(
        engine,
        "SELECT revoke_reason FROM mcp_connections WHERE user_id = :u",
        u=sam["id"],
    )
    assert rows == [{"revoke_reason": "member"}]
    audit = await _rows(engine, "SELECT action, detail FROM audit_events")
    [revoked] = [a for a in audit if a["action"] == "ai_connections.revoked"]
    assert revoked["detail"]["client"] == "Inspector"
    assert "removed from the workspace" in revoked["detail"]["reason"]
    [removal] = [a for a in audit if a["action"] == "member.removed"]
    assert removal["detail"]["revoked_ai_connections"] == 1
    assert (await _mcp_status(mcp_app, owners["access_token"])).status_code == 200  # only theirs

    await _sql(engine, join, w=setup.wid, u=sam["id"])  # invited back, and they accept
    refused = await _mcp_status(mcp_app, issued["access_token"])
    assert refused.status_code == 401
    assert "disconnected" in refused.headers["www-authenticate"]
    assert (await flow.refresh(issued["refresh_token"])).json()["error"] == "invalid_grant"


async def test_a_workspace_with_ai_connections_off_cant_be_chosen(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    await _sql(engine, "UPDATE workspaces SET ai_connections_mode = 'off'")
    flow = await public_flow(mcp_app)
    request_id = await flow.request_id()
    page = (await flow.consent(setup, request_id)).json()
    assert page["workspaces"][0]["can_connect"] is False
    assert (await flow.approve(setup, request_id)).status_code == 403


async def test_deny_and_a_request_is_decided_once(mcp_app: FastAPI, setup: Setup) -> None:
    flow = await public_flow(mcp_app)
    request_id = await flow.request_id()
    async with http_client(mcp_app, None, **setup.headers) as http:
        denied = await http.post(f"/v1/connect/requests/{request_id}/deny")
        back = query(denied.json()["redirect_to"])
        assert back["error"] == "access_denied"
        assert back["state"] == flow.state
        assert back["iss"] == BASE
        assert (await http.post(f"/v1/connect/requests/{request_id}/deny")).status_code == 404
    assert (await flow.approve(setup, request_id)).status_code == 404
    async with http_client(mcp_app, None) as http:  # signed out: no access
        assert (await http.get(f"/v1/connect/requests/{request_id}")).status_code == 401


async def test_the_member_can_allow_less(mcp_app: FastAPI, setup: Setup) -> None:
    flow = await public_flow(mcp_app)
    # posts:write wasn't asked for, so it can't be granted.
    issued = await flow.tokens(setup, scopes=["posts:read", "posts:write"])
    assert issued["scope"].split() == ["workspace:read", "posts:read"]


# ---------------------------------------------------------------- step-up


async def test_a_missing_scope_is_a_403_challenge(mcp_app: FastAPI, setup: Setup) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup, scopes=["posts:read"])
    headers = {**ACCEPT, "MCP-Protocol-Version": "2025-11-25"}
    call = rpc("tools/call", {"name": "list_conversations", "arguments": {}})
    async with http_client(mcp_app, issued["access_token"]) as http:
        response = await http.post(URL, json=call, headers=headers)
        allowed = await http.post(
            URL, json=rpc("tools/call", {"name": "get_workspace", "arguments": {}}), headers=headers
        )
    assert response.status_code == 403
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith('Bearer error="insufficient_scope"')
    assert 'scope="conversations:read posts:read workspace:read"' in challenge
    assert "resource_metadata=" in challenge
    assert allowed.status_code == 200


async def test_chatgpt_gets_the_challenge_on_the_tool_result(
    mcp_app: FastAPI, setup: Setup
) -> None:
    flow = await public_flow(mcp_app, redirect_uri=CHATGPT)
    issued = await flow.tokens(setup, scopes=["posts:read"])
    async with connect(mcp_app, issued["access_token"]) as mcp:
        result = await mcp.call_tool("list_conversations", {})
    error = error_of(result)
    assert error["code"] == "forbidden"
    assert "conversations:read" in error["message"]
    assert result.meta is not None
    [challenge] = result.meta["mcp/www_authenticate"]
    assert 'error="insufficient_scope"' in challenge


async def test_an_api_key_still_gets_a_tool_error(
    mcp_app: FastAPI, setup: Setup, client: httpx.AsyncClient
) -> None:
    from tests.support.mcp import make_key

    key, _ = await make_key(client, setup, "posts:read")
    async with connect(mcp_app, key) as mcp:
        result = await mcp.call_tool("list_conversations", {})
    assert "make a new key" in error_of(result)["message"]
    assert result.meta is None


# ---------------------------------------------------------------- CIMD


def _document(**overrides: Any) -> bytes:
    import json

    doc = {
        "client_id": CIMD_URL,
        "client_name": "Example Agent",
        "redirect_uris": [LOOPBACK, "https://client.example/callback"],
        "logo_uri": "https://client.example/logo.png",
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
    }
    doc.update(overrides)
    return json.dumps(doc).encode()


class FakeFetch:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, url: str, **kwargs: Any) -> ssrf.Page:
        self.calls.append({"url": url, **kwargs})
        return ssrf.Page(url=url, content=self.content, content_type="application/json")


async def test_a_metadata_document_client_connects(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    fetch = FakeFetch(_document())
    mcp_app.state.cimd_fetch = fetch
    flow = Flow(app=mcp_app, client_id=CIMD_URL)
    request_id = await flow.request_id()
    page = (await flow.consent(setup, request_id)).json()
    assert page["client"]["name"] == "Example Agent"
    assert page["client"]["verified_host"] == "client.example"
    assert page["client"]["logo_url"] == "https://client.example/logo.png"
    # The fetch's limits: 5 seconds, 5 KB, JSON, no redirects.
    [call] = fetch.calls
    assert call["timeout_s"] == 5.0
    assert call["max_bytes"] == 5 * 1024
    assert call["max_redirects"] == 0
    assert call["types"] == frozenset({"application/json"})
    await flow.request_id()
    assert len(fetch.calls) == 1  # cached for a day
    await _sql(engine, "UPDATE oauth_clients SET metadata_fetched_at = now() - interval '2 days'")
    await flow.request_id()
    assert len(fetch.calls) == 2
    issued = await flow.tokens(setup)
    assert issued["access_token"].startswith("sho_")


class RacingFetch(FakeFetch):
    """While the first request is still fetching the document, a second request for the same new
    client fetches it, saves the client and finishes."""

    def __init__(self, content: bytes, app: FastAPI) -> None:
        super().__init__(content)
        self.app = app

    async def __call__(self, url: str, **kwargs: Any) -> ssrf.Page:
        if not self.calls:
            self.calls.append({"url": url, **kwargs})
            second = await Flow(app=self.app, client_id=CIMD_URL).authorize()
            assert second.status_code == 302, second.text
            return ssrf.Page(url=url, content=self.content, content_type="application/json")
        return await super().__call__(url, **kwargs)


async def test_two_first_uses_of_a_metadata_document_client_both_work(
    mcp_app: FastAPI, engine: AsyncEngine
) -> None:
    fetch = RacingFetch(_document(), mcp_app)
    mcp_app.state.cimd_fetch = fetch
    first = await Flow(app=mcp_app, client_id=CIMD_URL).authorize()
    assert first.status_code == 302, first.text  # not a 500 on the unique client_id
    assert len(fetch.calls) == 2
    assert len(await _rows(engine, "SELECT id FROM oauth_clients")) == 1


async def test_a_private_key_jwt_client_that_supports_none_connects_as_public(
    mcp_app: FastAPI, setup: Setup
) -> None:
    """ChatGPT's document (2026-11-01): private_key_jwt first, none supported. Our metadata
    offers no private_key_jwt, so it is a public client here; an assertion it sends anyway is
    ignored, not trusted."""
    mcp_app.state.cimd_fetch = FakeFetch(
        _document(
            token_endpoint_auth_method="private_key_jwt",
            token_endpoint_auth_methods_supported=["none", "private_key_jwt"],
            token_endpoint_auth_signing_alg="RS256",
            jwks_uri="https://client.example/jwks.json",
        )
    )
    flow = Flow(app=mcp_app, client_id=CIMD_URL)
    issued = await flow.tokens(setup)
    assert issued["access_token"].startswith("sho_")
    response = await flow.exchange(
        await flow.code(setup),
        client_assertion_type="urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        client_assertion="eyJhbGciOiJSUzI1NiJ9.e30.c2ln",
    )
    assert response.status_code == 200, response.text


async def test_a_logo_on_another_host_isnt_shown(mcp_app: FastAPI, setup: Setup) -> None:
    mcp_app.state.cimd_fetch = FakeFetch(_document(logo_uri="https://tracker.example/l.png"))
    flow = Flow(app=mcp_app, client_id=CIMD_URL)
    page = (await flow.consent(setup, await flow.request_id())).json()
    assert page["client"]["logo_url"] is None


@pytest.mark.parametrize(
    "document",
    [
        _document(client_id="https://client.example/other.json"),
        _document(token_endpoint_auth_method="client_secret_basic"),
        _document(token_endpoint_auth_method="private_key_jwt"),
        _document(
            token_endpoint_auth_method="private_key_jwt",
            token_endpoint_auth_methods_supported=["private_key_jwt"],
        ),
        _document(redirect_uris=["http://evil.example/callback"]),
        _document(redirect_uris=[]),
        _document(client_name=""),
        b"not json",
        b"[]",
    ],
)
async def test_a_bad_metadata_document_is_refused(mcp_app: FastAPI, document: bytes) -> None:
    mcp_app.state.cimd_fetch = FakeFetch(document)
    response = await Flow(app=mcp_app, client_id=CIMD_URL).authorize()
    assert response.status_code == 400
    assert "location" not in response.headers


@pytest.mark.parametrize(
    "client_id",
    [
        "https://client.example",
        "https://client.example/",
        "https://127.0.0.1/meta.json",
        "https://10.0.0.5/meta.json",
        "https://localhost/meta.json",
        "https://user:pw@client.example/meta.json",
        "https://client.example/a/../meta.json",
        "https://intranet/meta.json",
    ],
)
async def test_unsafe_client_id_urls_are_never_fetched(mcp_app: FastAPI, client_id: str) -> None:
    fetch = FakeFetch(_document(client_id=client_id))
    mcp_app.state.cimd_fetch = fetch
    response = await Flow(app=mcp_app, client_id=client_id).authorize()
    assert response.status_code == 400
    assert fetch.calls == []


async def test_a_client_id_resolving_to_a_private_address_is_refused(
    mcp_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real fetcher: a public-looking name that resolves to a private address (DNS
    rebinding, the cloud metadata address) is refused before any connection."""

    async def private(host: str, port: int) -> list[str]:
        return ["169.254.169.254"]

    monkeypatch.setattr(ssrf, "resolve_host", private)
    mcp_app.state.cimd_fetch = None
    response = await Flow(app=mcp_app, client_id=CIMD_URL).authorize()
    assert response.status_code == 400
    assert "blocked" in response.text


# ---------------------------------------------------------------- DCR


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"redirect_uris": []}, "invalid_redirect_uri"),
        ({"redirect_uris": "http://127.0.0.1/cb"}, "invalid_redirect_uri"),
        ({"redirect_uris": ["http://evil.example/cb"]}, "invalid_redirect_uri"),
        ({"redirect_uris": ["myapp://callback"]}, "invalid_redirect_uri"),
        ({"redirect_uris": ["https://a.example/cb#frag"]}, "invalid_redirect_uri"),
        ({"redirect_uris": [f"https://a.example/{i}" for i in range(11)]}, "invalid_redirect_uri"),
        ({"grant_types": ["client_credentials"]}, "invalid_client_metadata"),
        ({"grant_types": ["implicit", "authorization_code"]}, "invalid_client_metadata"),
        ({"response_types": ["token"]}, "invalid_client_metadata"),
        ({"token_endpoint_auth_method": "private_key_jwt"}, "invalid_client_metadata"),
        ({"client_name": 42}, "invalid_client_metadata"),
    ],
)
async def test_registration_input_is_validated(
    mcp_app: FastAPI, body: dict[str, Any], error: str
) -> None:
    response = await register(mcp_app, **body)
    assert response.status_code == 400, response.text
    assert response.json()["error"] == error


async def test_registration_refuses_a_non_object_and_a_huge_body(mcp_app: FastAPI) -> None:
    async with http_client(mcp_app, None) as http:
        listed = await http.post("/oauth/register", json=["x"])
        huge = await http.post(
            "/oauth/register", json={"redirect_uris": [LOOPBACK], "client_name": "x" * 20_000}
        )
    assert listed.status_code == 400
    assert huge.status_code == 400


async def test_a_confidential_client_must_send_its_secret(mcp_app: FastAPI, setup: Setup) -> None:
    response = await register(mcp_app, token_endpoint_auth_method="client_secret_post")
    body = response.json()
    assert body["client_secret"].startswith("shs_")
    flow = Flow(app=mcp_app, client_id=body["client_id"], secret="shs_wrong")
    code = await flow.code(setup)
    wrong = await flow.exchange(code)
    assert wrong.status_code == 401
    assert wrong.json()["error"] == "invalid_client"
    flow.secret = body["client_secret"]
    assert (await flow.exchange(code)).status_code == 200


async def test_registration_is_rate_limited_per_ip(
    mcp_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(LIMITS, "oauth_register", Limit("oauth_register", 2, 3600))
    statuses = [(await register(mcp_app)).status_code for _ in range(3)]
    assert statuses == [201, 201, 429]


async def test_authorize_is_rate_limited_per_ip(
    mcp_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(LIMITS, "oauth_authorize", Limit("oauth_authorize", 2, 60))
    flow = Flow(app=mcp_app, client_id="dcr_does_not_exist")
    statuses = [(await flow.authorize()).status_code for _ in range(3)]
    assert statuses == [400, 400, 429]


async def test_token_requests_are_limited_per_ip_before_the_client_is_known(
    mcp_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(LIMITS, "oauth_token_ip", Limit("oauth_token_ip", 2, 60))
    form = {"grant_type": "authorization_code", "client_id": "dcr_does_not_exist"}
    async with http_client(mcp_app, None) as http:
        responses = [await http.post("/oauth/token", data=form, headers=FORM) for _ in range(3)]
        revoke = await http.post("/oauth/revoke", data=form, headers=FORM)  # the same window
    assert [r.status_code for r in responses] == [401, 401, 429]
    assert responses[-1].json()["error"] == "slow_down"
    assert int(responses[-1].headers["retry-after"]) >= 1
    assert revoke.status_code == 429


async def _token_status(app: FastAPI, address: str, form: dict[str, str]) -> int:
    async with http_client(app, None, **{"True-Client-IP": address}) as http:
        return int((await http.post("/oauth/token", data=form, headers=FORM)).status_code)


async def test_one_caller_cant_spend_a_shared_clients_token_allowance(
    mcp_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One client id serves all of an app's users and a public client needs no secret, so the
    allowance is per client and address: junk requests from one address leave the others alone."""
    monkeypatch.setitem(LIMITS, "oauth_token", Limit("oauth_token", 2, 60))
    mcp_app.state.settings.client_ip_header = "true-client-ip"
    flow = await public_flow(mcp_app)
    junk = {
        "grant_type": "authorization_code",
        "client_id": flow.client_id,
        "code": "shc_" + "x" * 43,
    }
    statuses = [await _token_status(mcp_app, "203.0.113.7", junk) for _ in range(3)]
    assert statuses == [400, 400, 429]
    assert await _token_status(mcp_app, "203.0.113.8", junk) == 400


async def test_a_valkey_outage_lets_token_requests_through(mcp_app: FastAPI, setup: Setup) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    working = mcp_app.state.redis
    mcp_app.state.redis = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    try:
        assert (await flow.refresh(issued["refresh_token"])).status_code == 200
    finally:
        await mcp_app.state.redis.aclose()
        mcp_app.state.redis = working


# ---------------------------------------------------------------- the block list


async def test_a_blocked_client_is_refused_at_authorize_consent_token_and_mcp(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    flow = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    waiting = await flow.request_id()  # on the consent page when the block lands
    code = await flow.code(setup)  # and one not exchanged yet

    await _sql(engine, "UPDATE oauth_clients SET blocked_at = now()")
    shown = await flow.authorize()
    assert shown.status_code == 400
    assert "location" not in shown.headers
    assert (await flow.consent(setup, waiting)).status_code == 404
    exchanged = await flow.exchange(code)
    assert (exchanged.status_code, exchanged.json()["error"]) == (401, "invalid_client")
    refreshed = await flow.refresh(issued["refresh_token"])
    assert (refreshed.status_code, refreshed.json()["error"]) == (401, "invalid_client")
    assert (await flow.revoke(issued["refresh_token"])).status_code == 401
    refused = await _mcp_status(mcp_app, issued["access_token"])
    assert refused.status_code == 401
    assert "disconnected" in refused.headers["www-authenticate"]

    # The flag alone revokes nothing (the script does that): lifted, the connection works again.
    await _sql(engine, "UPDATE oauth_clients SET blocked_at = NULL")
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 200


async def test_the_block_script_blocks_revokes_and_unblocks(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = mcp_app.state.settings
    flow = await public_flow(mcp_app)
    other = await public_flow(mcp_app)
    issued = await flow.tokens(setup)
    untouched = await other.tokens(setup)

    assert await block_script.run(["block", "dcr_does_not_exist"], settings=settings) == 2
    assert "No client" in capsys.readouterr().err
    assert await block_script.run(["block", flow.client_id], settings=settings) == 0
    assert "Connections revoked: 1" in capsys.readouterr().out
    rows = await _rows(engine, "SELECT revoke_reason FROM mcp_connections ORDER BY created_at")
    assert [r["revoke_reason"] for r in rows] == ["all", None]  # only the blocked client's
    assert (await flow.authorize()).status_code == 400
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 401
    assert (await _mcp_status(mcp_app, untouched["access_token"])).status_code == 200

    # Unblocked, the app can ask again; what it had stays revoked.
    assert await block_script.run(["unblock", flow.client_id], settings=settings) == 0
    assert "Unblocked" in capsys.readouterr().out
    assert (await flow.authorize()).status_code == 302
    assert (await _mcp_status(mcp_app, issued["access_token"])).status_code == 401
    assert (await flow.refresh(issued["refresh_token"])).json()["error"] == "invalid_grant"


async def test_token_endpoint_input(mcp_app: FastAPI) -> None:
    flow = await public_flow(mcp_app)
    async with http_client(mcp_app, None) as http:
        as_json = await http.post("/oauth/token", json={"grant_type": "authorization_code"})
        unknown = await http.post(
            "/oauth/token",
            data={"grant_type": "client_credentials", "client_id": flow.client_id},
            headers=FORM,
        )
        nobody = await http.post("/oauth/token", data={"grant_type": "x"}, headers=FORM)
    assert as_json.json()["error"] == "invalid_request"
    assert unknown.json()["error"] == "unsupported_grant_type"
    assert nobody.status_code == 401
    assert nobody.json()["error"] == "invalid_client"


async def test_retention_drops_old_codes_tokens_and_unused_clients(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    from socialhood.jobs.tasks.purge import purge_expired_rows

    flow = await public_flow(mcp_app)
    await flow.tokens(setup)
    unused = await register(mcp_app)
    await _sql(engine, "UPDATE oauth_codes SET created_at = now() - interval '2 days'")
    await _sql(
        engine,
        "UPDATE oauth_clients SET created_at = now() - interval '40 days' WHERE client_id = :c",
        c=unused.json()["client_id"],
    )
    later = datetime.now(UTC) + timedelta(hours=3)
    counts = await purge_expired_rows(mcp_app.state.sessionmaker, now=later)
    assert counts["oauth_codes"] == 1
    assert counts.get("oauth_tokens", 0) == 0  # the access token ended 2 hours ago, kept a day
    assert counts["oauth_clients"] == 1  # the connected client stays
    clients = await _rows(engine, "SELECT client_id FROM oauth_clients")
    assert [c["client_id"] for c in clients] == [flow.client_id]


async def test_retention_drops_an_unused_metadata_document_client_but_never_a_blocked_one(
    mcp_app: FastAPI, setup: Setup, engine: AsyncEngine
) -> None:
    """Anyone can make us save a metadata document's client with one authorize request, so an
    unused one goes like an unused registration; a blocked client's row is the block."""
    from socialhood.jobs.tasks.purge import purge_expired_rows

    mcp_app.state.cimd_fetch = FakeFetch(_document())
    await Flow(app=mcp_app, client_id=CIMD_URL).request_id()  # saved, never connected
    held = await public_flow(mcp_app)
    await held.tokens(setup)
    blocked = await register(mcp_app)
    await _sql(engine, "UPDATE oauth_clients SET created_at = now() - interval '40 days'")
    await _sql(
        engine,
        "UPDATE oauth_clients SET blocked_at = now() WHERE client_id = :c",
        c=blocked.json()["client_id"],
    )
    counts = await purge_expired_rows(mcp_app.state.sessionmaker, now=datetime.now(UTC))
    assert counts["oauth_clients"] == 1
    clients = await _rows(engine, "SELECT client_id FROM oauth_clients")
    assert {c["client_id"] for c in clients} == {held.client_id, blocked.json()["client_id"]}
