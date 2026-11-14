"""C-195: the YouTube platform - Google's error mapping, the adapter's capabilities and token
handling, the authorize URL and the feature switch."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import SecretStr

from socialhood.models.connections import SocialAccount
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.youtube.adapter import NEXT_STEP, YouTubeAdapter
from socialhood.platforms.youtube.client import UPLOAD_LIMIT, map_google_error
from socialhood.platforms.youtube.fake import FakeYouTube
from socialhood.platforms.youtube.oauth import SCOPE, HttpYouTubeOAuth
from socialhood.platforms.youtube.switch import features_for, youtube_enabled
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.services.connections import refresh_due

KEY = new_key()


def google_error(status: int, reason: str) -> dict[str, Any]:
    return {"error": {"code": status, "errors": [{"reason": reason}], "message": reason}}


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (403, google_error(403, "quotaExceeded"), "platform_rate_limited"),
        (403, google_error(403, "rateLimitExceeded"), "platform_rate_limited"),
        (403, google_error(403, "userRateLimitExceeded"), "platform_rate_limited"),
        (429, None, "platform_rate_limited"),
        (400, google_error(400, "uploadLimitExceeded"), "platform_rejected"),
        (401, google_error(401, "authError"), "account_needs_reconnect"),
        (400, {"error": "invalid_grant", "error_description": "Bad"}, "account_needs_reconnect"),
        (503, google_error(503, "backendError"), "platform_unavailable"),
        (500, None, "platform_unavailable"),
        (403, google_error(403, "forbidden"), "platform_rejected"),
        (400, {"error": "invalid_request"}, "platform_rejected"),
    ],
)
def test_google_errors_map_to_our_codes(status: int, body: Any, code: str) -> None:
    assert map_google_error(status, body).code == code


def test_the_upload_limit_says_what_to_do_and_quota_is_retryable() -> None:
    upload = map_google_error(400, google_error(400, "uploadLimitExceeded"))
    assert (upload.message, upload.platform_code, upload.retryable) == (
        UPLOAD_LIMIT,
        "uploadLimitExceeded",
        False,
    )
    assert map_google_error(403, google_error(403, "quotaExceeded")).retryable is True


def settings(**values: Any) -> Any:
    base = {
        "youtube_client_id": "client-1.apps.googleusercontent.com",
        "youtube_client_secret": SecretStr("s"),
        "youtube_redirect_uri": "https://api.test/v1/oauth/youtube/callback",
        "youtube_workspaces": "",
        "sandbox_platform_enabled": False,
    }
    return SimpleNamespace(**(base | values))


def deps(**values: Any) -> PlatformDeps:
    return PlatformDeps(http=MagicMock(), cipher=TokenCipher([KEY]), settings=settings(**values))


def test_the_authorize_url_asks_for_force_ssl_only_offline_with_consent() -> None:
    url = HttpYouTubeOAuth(deps()).authorize_url("st-1")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert query["scope"] == SCOPE == "https://www.googleapis.com/auth/youtube.force-ssl"
    assert (query["access_type"], query["prompt"], query["include_granted_scopes"]) == (
        "offline",
        "consent",
        "false",
    )
    assert (query["state"], query["response_type"]) == ("st-1", "code")
    assert query["redirect_uri"] == "https://api.test/v1/oauth/youtube/callback"


def channel(scopes: list[str] | None = None, token: str | None = "fake-yt-refresh:1") -> Any:  # noqa: S107 (a fake test token)
    return SocialAccount(
        id=uuid.uuid4(),
        platform="youtube",
        platform_account_id="UCabc",
        status="active",
        scopes=[SCOPE] if scopes is None else scopes,
        access_token_enc=TokenCipher([KEY]).encrypt(token) if token else None,
        token_expires_at=None,
    )


def test_capabilities_need_the_force_ssl_scope() -> None:
    adapter = YouTubeAdapter(deps())
    assert adapter.capabilities_for(channel()) == {Capability.PUBLISH, Capability.POST_INSIGHTS}
    assert adapter.capabilities_for(channel(scopes=[])) == frozenset()


def test_the_registry_routes_youtube_to_its_adapter() -> None:
    assert isinstance(adapter_for(channel(), deps()), YouTubeAdapter)


async def test_messages_and_comments_are_unavailable_and_publishing_waits() -> None:
    adapter = YouTubeAdapter(deps())
    with pytest.raises(PlatformError) as dm:
        await adapter.send_message(channel(), "x", MagicMock())
    assert dm.value.code == "capability_unavailable"
    with pytest.raises(PlatformError) as comment:
        await adapter.reply_to_comment(channel(), "c", "hi")
    assert comment.value.code == "capability_unavailable"
    with pytest.raises(PlatformError) as publish:
        await adapter.publish_container(channel(), "v")
    assert (publish.value.code, publish.value.message) == ("capability_unavailable", NEXT_STEP)
    assert await adapter.list_media(channel()) == []
    assert await adapter.get_media_counts(channel(), "v") is None
    await adapter.subscribe_webhooks(channel())  # nothing to subscribe


async def test_refresh_returns_the_stored_grant_and_the_job_skips_youtube() -> None:
    grant = await YouTubeAdapter(deps()).refresh_token(channel())
    assert (grant.access_token, grant.expires_at) == ("fake-yt-refresh:1", None)
    acct = channel()
    acct.token_expires_at = None
    assert refresh_due(acct, MagicMock()) is False


async def test_an_access_token_is_minted_per_use_and_invalid_grant_needs_reconnect(
    fake_youtube: FakeYouTube,
) -> None:
    adapter = YouTubeAdapter(deps())
    assert await adapter.access_token(channel()) == "fake-yt-access:fake-yt-refresh:1"
    fake_youtube.revoke_access("fake-yt-refresh:1")
    with pytest.raises(PlatformError) as error:
        await adapter.access_token(channel())
    assert (error.value.code, error.value.platform_code) == (
        "account_needs_reconnect",
        "invalid_grant",
    )


@pytest.mark.parametrize(
    ("switch", "on"),
    [("", False), ("*", True), ("maple", True), ("other, maple ", True), ("other", False)],
)
def test_the_feature_switch(switch: str, on: bool) -> None:
    wid = uuid.uuid4()
    s: Any = settings(youtube_workspaces=switch)
    assert youtube_enabled(s, wid, "maple") is on
    assert features_for(s, wid, "maple") == (["youtube"] if on else [])
    by_id: Any = settings(youtube_workspaces=str(wid))
    assert youtube_enabled(by_id, wid, "maple") is True
