"""Instagram OAuth and adapter calls against recorded-shape fixtures (TR-TEST-01 contract layer)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import oauth
from socialhood.platforms.instagram.adapter import SUBSCRIBED_FIELDS, InstagramAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH, TOKEN_URL, fixture

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
    ig_app_id="1234567890",
    ig_app_secret="app-secret",
    ig_redirect_uri="https://api.example.com/v1/oauth/instagram/callback",
)
ME = f"{GRAPH}/{SETTINGS.ig_graph_version}/me"


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def cipher() -> TokenCipher:
    return TokenCipher([new_key()])


LONG_TOKEN = "IGQVJlong-lived-token"


def account(cipher: TokenCipher, token: str = LONG_TOKEN) -> SocialAccount:
    return SocialAccount(
        platform="instagram",
        platform_account_id="17841400000000001",
        access_token_enc=cipher.encrypt(token),
        scopes=list(oauth.BASE_SCOPES),
    )


def test_the_authorize_url_asks_for_the_business_scopes() -> None:
    url = oauth.authorize_url(SETTINGS, "st4te")
    assert url.startswith("https://www.instagram.com/oauth/authorize?")
    assert "client_id=1234567890" in url
    assert "state=st4te" in url
    assert "instagram_business_manage_messages" in url
    assert oauth.INSIGHTS_SCOPE not in url
    with_insights = SETTINGS.model_copy(update={"ig_request_insights_scope": True})
    assert oauth.INSIGHTS_SCOPE in oauth.authorize_url(with_insights, "s")


@pytest.mark.parametrize("name", ["oauth_access_token.json", "oauth_access_token_flat.json"])
@respx.mock
async def test_code_exchange_accepts_both_response_shapes(
    http: httpx.AsyncClient, name: str
) -> None:
    route = respx.post(TOKEN_URL).respond(200, json=fixture(name))
    short = await oauth.exchange_code(PlatformHttp(http, "instagram"), SETTINGS, "the-code")
    assert short.access_token == "IGQVJshort-lived-token"
    assert short.user_id == "17841400000000001"
    assert "instagram_business_basic" in short.permissions
    sent = dict(httpx.QueryParams(route.calls.last.request.content.decode()))
    assert sent["grant_type"] == "authorization_code"
    assert sent["code"] == "the-code"
    assert sent["redirect_uri"] == SETTINGS.ig_redirect_uri


@respx.mock
async def test_long_lived_token_and_profile(http: httpx.AsyncClient) -> None:
    respx.get(f"{GRAPH}/access_token").respond(200, json=fixture("long_lived_token.json"))
    me = respx.get(ME).respond(200, json=fixture("me_business.json"))
    platform_http = PlatformHttp(http, "instagram")

    long = await oauth.long_lived(platform_http, SETTINGS, "short")
    profile = await oauth.me(platform_http, SETTINGS, long.access_token)

    assert long.expires_at is not None
    assert profile.user_id == "17841400000000001"
    assert profile.app_scoped_id == "26000000000000001"
    assert profile.is_professional
    request = me.calls.last.request
    assert request.headers["authorization"] == "Bearer IGQVJlong-lived-token"
    assert "access_token" not in str(request.url)  # the token travels in the header only


@respx.mock
async def test_a_personal_account_is_not_professional(http: httpx.AsyncClient) -> None:
    respx.get(ME).respond(200, json=fixture("me_personal.json"))
    profile = await oauth.me(PlatformHttp(http, "instagram"), SETTINGS, "t")
    assert not profile.is_professional


@respx.mock
async def test_subscribe_sends_every_field(http: httpx.AsyncClient, cipher: TokenCipher) -> None:
    route = respx.post(f"{ME}/subscribed_apps").respond(
        200, json=fixture("subscribed_apps_success.json")
    )
    adapter = InstagramAdapter(PlatformDeps(http, cipher, SETTINGS))
    await adapter.subscribe_webhooks(account(cipher))
    assert route.calls.last.request.url.params["subscribed_fields"] == SUBSCRIBED_FIELDS


@respx.mock
async def test_an_unconfirmed_subscription_is_an_error(
    http: httpx.AsyncClient, cipher: TokenCipher
) -> None:
    respx.post(f"{ME}/subscribed_apps").respond(200, json={"success": False})
    adapter = InstagramAdapter(PlatformDeps(http, cipher, SETTINGS))
    with pytest.raises(PlatformError) as caught:
        await adapter.subscribe_webhooks(account(cipher))
    assert caught.value.code == "platform_rejected"


@respx.mock
async def test_an_expired_token_asks_for_reconnect(
    http: httpx.AsyncClient, cipher: TokenCipher
) -> None:
    respx.post(f"{ME}/subscribed_apps").respond(400, json=fixture("error_190_expired.json"))
    adapter = InstagramAdapter(PlatformDeps(http, cipher, SETTINGS))
    with pytest.raises(PlatformError) as caught:
        await adapter.subscribe_webhooks(account(cipher))
    assert caught.value.code == "account_needs_reconnect"
    assert not caught.value.retryable


@respx.mock
async def test_refresh_returns_a_new_expiry(http: httpx.AsyncClient, cipher: TokenCipher) -> None:
    route = respx.get(f"{GRAPH}/refresh_access_token").respond(
        200, json=fixture("refresh_access_token.json")
    )
    adapter = InstagramAdapter(PlatformDeps(http, cipher, SETTINGS))
    grant = await adapter.refresh_token(account(cipher, "old-token"))
    assert grant.access_token == "IGQVJrefreshed-token"
    assert grant.expires_at is not None
    assert route.calls.last.request.url.params["grant_type"] == "ig_refresh_token"


@respx.mock
async def test_contact_profile(http: httpx.AsyncClient, cipher: TokenCipher) -> None:
    respx.get(f"{GRAPH}/{SETTINGS.ig_graph_version}/990000000000001").respond(
        200, json=fixture("user_profile.json")
    )
    adapter = InstagramAdapter(PlatformDeps(http, cipher, SETTINGS))
    profile = await adapter.fetch_contact_profile(account(cipher), "990000000000001")
    assert profile is not None
    assert (profile.name, profile.username) == ("Priya Shah", "priya.shah")


async def test_no_stored_token_asks_for_reconnect(
    http: httpx.AsyncClient, cipher: TokenCipher
) -> None:
    adapter = InstagramAdapter(PlatformDeps(http, cipher, SETTINGS))
    acct = account(cipher)
    acct.access_token_enc = None
    with pytest.raises(PlatformError) as caught:
        await adapter.subscribe_webhooks(acct)
    assert caught.value.code == "account_needs_reconnect"


@pytest.mark.parametrize("side_effect", [httpx.ReadTimeout("slow"), httpx.ConnectError("down")])
@respx.mock
async def test_network_failures_are_retryable(http: httpx.AsyncClient, side_effect: Any) -> None:
    respx.get(ME).mock(side_effect=side_effect)
    with pytest.raises(PlatformError) as caught:
        await oauth.me(PlatformHttp(http, "instagram"), SETTINGS, "t")
    assert caught.value.code == "platform_unavailable"
    assert caught.value.retryable
