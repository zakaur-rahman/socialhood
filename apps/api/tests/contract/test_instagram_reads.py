"""T3.3, T3.14: the Instagram adapter's media download, post list and conversation backfill
against fixture-shaped responses (TR-TEST-01 contract layer)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.instagram import oauth, reads
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH, fixture

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
)
V = f"{GRAPH}/{SETTINGS.ig_graph_version}"
CDN = "https://lookaside.fbsbx.com/ig_messaging_cdn/"
THREAD_ID = fixture("conversations_list.json")["data"][0]["id"]


@pytest.fixture
async def adapter() -> AsyncIterator[InstagramAdapter]:
    async with httpx.AsyncClient() as http:
        yield InstagramAdapter(PlatformDeps(http, TokenCipher([new_key()]), SETTINGS))


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reads, "CONVERSATIONS_PACE_S", 0)


def account(adapter: InstagramAdapter) -> SocialAccount:
    return SocialAccount(
        platform="instagram",
        platform_account_id="17841400000000001",
        app_scoped_id="26000000000000001",
        username="maple.bakery",
        access_token_enc=adapter.deps.cipher.encrypt("IGQVJlong"),
        scopes=list(oauth.BASE_SCOPES),
    )


@respx.mock
async def test_list_media_asks_for_the_recent_posts(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/me/media").respond(200, json=fixture("media_list.json"))
    posts = await adapter.list_media(account(adapter), limit=25)
    assert [p.platform_media_id for p in posts] == [
        "18100000000000003",
        "18100000000000002",
        "18100000000000001",
    ]
    request = route.calls.last.request
    assert request.url.params["limit"] == "25"
    assert "comments_count" in request.url.params["fields"]
    assert request.headers["authorization"] == "Bearer IGQVJlong"


@respx.mock
async def test_list_threads_reads_each_conversation(adapter: InstagramAdapter) -> None:
    listing = respx.get(f"{V}/me/conversations").respond(
        200, json=fixture("conversations_list.json")
    )
    respx.get(f"{V}/{THREAD_ID}").respond(200, json=fixture("conversation_messages.json"))
    [thread] = await adapter.list_threads(account(adapter))
    assert listing.calls.last.request.url.params["platform"] == "instagram"
    assert thread.platform_conversation_id == THREAD_ID
    assert [m.is_echo for m in thread.messages] == [False, True, False]
    assert {m.account_ref for m in thread.messages} == {"17841400000000001"}


@respx.mock
async def test_a_refused_thread_is_skipped_but_an_outage_fails_the_call(
    adapter: InstagramAdapter,
) -> None:
    respx.get(f"{V}/me/conversations").respond(200, json=fixture("conversations_list.json"))
    thread_route = respx.get(f"{V}/{THREAD_ID}")
    thread_route.respond(400, json={"error": {"code": 100, "message": "Unsupported get request"}})
    assert await adapter.list_threads(account(adapter)) == []
    thread_route.respond(500, json={"error": {"code": 2, "message": "Service unavailable"}})
    with pytest.raises(PlatformError) as caught:
        await adapter.list_threads(account(adapter))
    assert caught.value.retryable


@respx.mock
async def test_download_returns_the_bytes_without_sending_the_token(
    adapter: InstagramAdapter,
) -> None:
    route = respx.get(url__startswith=CDN).respond(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
    )
    got = await adapter.download_media(
        account(adapter), InboundMediaRef(kind="image", url=f"{CDN}?asset_id=1")
    )
    assert (got.content, got.mime_type) == (b"\xff\xd8jpeg", "image/jpeg")
    assert "authorization" not in route.calls.last.request.headers


@pytest.mark.parametrize(
    ("response", "code", "retryable"),
    [
        (httpx.Response(404), "platform_rejected", False),
        (httpx.Response(503), "platform_unavailable", True),
        (httpx.Response(200, content=b"x" * (8 * 1024 * 1024 + 1)), "unsupported_media", False),
        (
            httpx.Response(200, headers={"content-length": str(9 * 1024 * 1024)}, content=b"x"),
            "unsupported_media",
            False,
        ),
    ],
    ids=["expired", "outage", "too-large", "declared-too-large"],
)
@respx.mock
async def test_download_failures(
    adapter: InstagramAdapter, response: httpx.Response, code: str, retryable: bool
) -> None:
    respx.get(url__startswith=CDN).mock(return_value=response)
    with pytest.raises(PlatformError) as caught:
        await adapter.download_media(
            account(adapter), InboundMediaRef(kind="image", url=f"{CDN}?asset_id=2")
        )
    assert (caught.value.code, caught.value.retryable) == (code, retryable)


@respx.mock
async def test_a_download_timeout_is_retryable(adapter: InstagramAdapter) -> None:
    respx.get(url__startswith=CDN).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(PlatformError) as caught:
        await adapter.download_media(
            account(adapter), InboundMediaRef(kind="video", url=f"{CDN}?asset_id=3")
        )
    assert caught.value.retryable


async def test_only_https_media_urls_are_fetched(adapter: InstagramAdapter) -> None:
    for url in (None, "http://example.com/a.jpg", "file:///etc/passwd"):
        with pytest.raises(PlatformError):
            await adapter.download_media(account(adapter), InboundMediaRef(kind="image", url=url))
