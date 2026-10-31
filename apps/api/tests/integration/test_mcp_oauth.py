"""C-165 phase C: the OAuth authorization server and OAuth tokens on /mcp.

The whole flow end to end (register, authorize, consent as the signed-in Clerk test user, token,
a tool call), then the security properties one by one: PKCE, exact redirect URIs, single-use
codes, refresh rotation and reuse detection, audience binding, expiry, revocation, workspace
binding, the scope step-up (HTTP 403 and ChatGPT's tool-result form), CIMD fetch safety and
DCR input validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import httpx2
import pytest
from fastapi import FastAPI
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
    flow = await public_flow(mcp_app)
    for overrides in (
        {"code_challenge": None},
        {"code_challenge_method": "plain"},
        {"code_challenge_method": None},
        {"code_challenge": "short"},
    ):
        response = await flow.authorize(**overrides)
        assert response.status_code == 302
        back = query(response.headers["location"])
        assert back["error"] == "invalid_request"
        assert back["state"] == flow.state
        assert back["iss"] == BASE

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
    assert query(elsewhere.headers["location"])["error"] == "invalid_target"
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
