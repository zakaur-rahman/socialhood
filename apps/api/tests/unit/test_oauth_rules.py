"""C-165 phase C: the authorization server's pure rules (no database): redirect URIs, client id
URLs, metadata documents, PKCE, scopes and resources."""

from __future__ import annotations

import base64
import hashlib
import json

import pytest

from socialhood.oauth import clients, scopes, service
from socialhood.oauth.clients import ClientError
from socialhood.settings import AppEnv, Settings


@pytest.mark.parametrize(
    ("uri", "ok"),
    [
        ("https://claude.ai/api/mcp/auth_callback", True),
        ("https://chatgpt.com/connector_platform_oauth_redirect", True),
        ("http://localhost:6274/oauth/callback", True),
        ("http://127.0.0.1/callback", True),
        ("http://[::1]:9000/callback", True),
        ("http://example.com/callback", False),
        ("myapp://callback", False),
        ("https://a.example/cb#x", False),
        ("https://user@a.example/cb", False),
        ("https://a.example:99999/cb", False),
        (" https://a.example/cb", False),
        ("https:///cb", False),
        ("", False),
        (42, False),
    ],
)
def test_redirect_uri_rules(uri: object, ok: bool) -> None:
    assert clients.valid_redirect_uri(uri) is ok


def test_loopback_matches_on_any_port_and_nothing_else_loosens() -> None:
    registered = ["http://127.0.0.1:3000/callback", "https://claude.ai/api/mcp/auth_callback"]
    assert clients.redirect_matches(registered, "http://127.0.0.1:51123/callback")
    assert clients.redirect_matches(registered, "http://127.0.0.1/callback")
    assert not clients.redirect_matches(registered, "http://localhost:3000/callback")
    assert not clients.redirect_matches(registered, "http://127.0.0.1:3000/callback/")
    assert not clients.redirect_matches(registered, "https://claude.ai/api/mcp/auth_callback/")
    assert not clients.redirect_matches(registered, "https://claude.ai:444/api/mcp/auth_callback")


@pytest.mark.parametrize(
    "client_id",
    [
        "http://client.example/meta.json",
        "https://client.example",
        "https://192.168.1.4/meta.json",
        "https://[::1]/meta.json",
        "https://box.localhost/meta.json",
        "https://client.example/meta.json#frag",
        "https://client.example/./meta.json",
    ],
)
def test_client_id_urls_that_are_refused(client_id: str) -> None:
    with pytest.raises(ClientError):
        clients.check_cimd_url(client_id)


def test_a_metadata_document_is_checked() -> None:
    url = "https://client.example/meta.json"
    doc = {
        "client_id": url,
        "client_name": "  Example\n Agent ",
        "redirect_uris": ["https://client.example/cb", "https://client.example/cb"],
        "logo_uri": "http://client.example/logo.png",
    }
    parsed = clients.parse_cimd(url, json.dumps(doc).encode())
    assert parsed["client_name"] == "Example Agent"
    assert parsed["redirect_uris"] == ["https://client.example/cb"]
    assert parsed["logo_uri"] is None  # not https: dropped
    with pytest.raises(ClientError):
        clients.parse_cimd(url.upper(), json.dumps(doc).encode())


async def test_the_fetch_is_bounded() -> None:
    seen: dict[str, object] = {}

    async def fetch(url: str, **kwargs: object) -> object:
        seen.update(kwargs)
        from socialhood.security.ssrf import FetchError

        raise FetchError("too_large", "too large")

    with pytest.raises(ClientError, match="too_large"):
        await clients.fetch_cimd("https://client.example/meta.json", fetch=fetch)  # type: ignore[arg-type]
    assert seen["max_bytes"] == 5 * 1024
    assert seen["timeout_s"] == 5.0
    assert seen["max_redirects"] == 0


def test_pkce_s256() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert service.pkce_ok(verifier, challenge.rstrip(b"=").decode())
    assert not service.pkce_ok(verifier[:-1] + "x", challenge.rstrip(b"=").decode())
    assert not service.pkce_ok("short", challenge.rstrip(b"=").decode())


def test_scopes_drop_what_we_dont_grant() -> None:
    assert scopes.requested("openid email profile offline_access posts:write messages:send") == [
        "workspace:read",
        "posts:write",
    ]
    assert scopes.requested(None)[0] == "workspace:read"
    assert "posts:write" in scopes.requested(None)  # the PRM's default set
    assert "offline_access" in scopes.AS_SCOPES_SUPPORTED
    assert "messages:send" not in scopes.GRANTABLE


def test_resource_normalisation() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        database_url="postgresql+asyncpg://x/y",
        database_url_direct="postgresql://x/y",
        api_base_url="https://api.amplychat.com",
    )
    assert service.issuer(settings) == "https://api.amplychat.com"
    ours = "https://api.amplychat.com/mcp"
    assert service.check_resource(None, settings) == ours
    assert service.check_resource("HTTPS://API.AMPLYCHAT.COM/mcp/", settings) == ours
    with pytest.raises(service.OAuthError):
        service.check_resource("https://api.amplychat.com/other", settings)
    with pytest.raises(service.OAuthError):
        service.check_resource("https://api.amplychat.com", settings)
