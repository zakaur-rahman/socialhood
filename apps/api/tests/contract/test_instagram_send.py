"""Instagram Send API shapes (T3.6, T3.7; TR-PL-03, TR-PL-04, TR-JOB-05). Shapes follow Meta's
documentation for the Instagram API with Instagram Login; T0.9 confirms them on a real account."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import OutboundAttachment, OutboundMessage, OutboundTemplate
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
)
SEND = f"{GRAPH}/{SETTINGS.ig_graph_version}/me/messages"
TOKEN = "IGQVJsend-token"
IGSID = "1234567890123456"


@pytest.fixture
async def adapter() -> AsyncIterator[tuple[InstagramAdapter, SocialAccount]]:
    cipher = TokenCipher([new_key()])
    async with httpx.AsyncClient() as http:
        acct = SocialAccount(
            platform="instagram",
            platform_account_id="17841400000000001",
            access_token_enc=cipher.encrypt(TOKEN),
            scopes=[],
        )
        yield InstagramAdapter(PlatformDeps(http, cipher, SETTINGS)), acct


def sent(route: respx.Route) -> dict[str, object]:
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert "access_token" not in str(request.url)
    body: dict[str, object] = json.loads(request.content)
    return body


@respx.mock
async def test_text(adapter: tuple[InstagramAdapter, SocialAccount]) -> None:
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID, "message_id": "mid.1"})
    result = await ig.send_message(acct, IGSID, OutboundMessage(text="Hello"))
    assert result.platform_message_id == "mid.1"
    assert sent(route) == {"recipient": {"id": IGSID}, "message": {"text": "Hello"}}


@respx.mock
async def test_an_image_with_the_human_agent_tag(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID, "message_id": "mid.2"})
    image = OutboundAttachment(type="image", url="https://res.cloudinary.com/x/image/upload/a.jpg")
    await ig.send_message(acct, IGSID, OutboundMessage(attachment=image, human_agent=True))
    assert sent(route) == {
        "recipient": {"id": IGSID},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": "https://res.cloudinary.com/x/image/upload/a.jpg"},
            }
        },
        "messaging_type": "MESSAGE_TAG",
        "tag": "HUMAN_AGENT",
    }


@respx.mock
async def test_the_heart_sticker(adapter: tuple[InstagramAdapter, SocialAccount]) -> None:
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID, "message_id": "mid.3"})
    await ig.send_message(acct, IGSID, OutboundMessage(sticker="like_heart"))
    assert sent(route) == {
        "recipient": {"id": IGSID},
        "message": {"attachment": {"type": "like_heart"}},
    }


@pytest.mark.parametrize("kind", ["file", "audio", "video"])
@respx.mock
async def test_files_audio_and_video_by_url(
    adapter: tuple[InstagramAdapter, SocialAccount], kind: str
) -> None:
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID, "message_id": "mid.4"})
    item = OutboundAttachment(type=kind, url="https://res.cloudinary.com/x/raw/upload/a.pdf")  # type: ignore[arg-type]
    await ig.send_message(acct, IGSID, OutboundMessage(attachment=item))
    assert sent(route)["message"] == {
        "attachment": {
            "type": kind,
            "payload": {"url": "https://res.cloudinary.com/x/raw/upload/a.pdf"},
        }
    }


@respx.mock
async def test_only_the_heart_sticker_exists_on_instagram(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    route = respx.post(SEND)
    webp = OutboundAttachment(type="sticker", url="https://s/1.webp")
    with pytest.raises(PlatformError) as caught:
        await ig.send_message(acct, IGSID, OutboundMessage(attachment=webp))
    assert caught.value.code == "platform_rejected"
    assert not route.called


@respx.mock
async def test_mark_seen(adapter: tuple[InstagramAdapter, SocialAccount]) -> None:
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID})
    await ig.mark_read(acct, IGSID)
    assert sent(route) == {"recipient": {"id": IGSID}, "sender_action": "mark_seen"}


async def test_templates_are_not_sent_on_instagram(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    with pytest.raises(PlatformError) as raised:
        await ig.send_message(
            acct, IGSID, OutboundMessage(template=OutboundTemplate(name="x", language="en"))
        )
    assert raised.value.code == "platform_rejected"


@pytest.mark.parametrize(
    ("status", "error", "code", "retryable"),
    [
        (400, {"code": 10, "error_subcode": 2534022}, "reply_window_closed", False),
        (400, {"code": 551}, "recipient_unavailable", False),
        (400, {"code": 190}, "account_needs_reconnect", False),
        (400, {"code": 4}, "platform_rate_limited", True),
        (500, {"code": 2}, "platform_unavailable", True),
        (400, {"code": 100, "message": "Invalid parameter"}, "platform_rejected", False),
    ],
)
@respx.mock
async def test_send_errors_map_to_codes(
    adapter: tuple[InstagramAdapter, SocialAccount],
    status: int,
    error: dict[str, object],
    code: str,
    retryable: bool,
) -> None:
    ig, acct = adapter
    respx.post(SEND).respond(status, json={"error": {"message": "m", **error}})
    with pytest.raises(PlatformError) as raised:
        await ig.send_message(acct, IGSID, OutboundMessage(text="Hi"))
    assert raised.value.code == code
    assert raised.value.retryable is retryable


@pytest.mark.parametrize(
    ("failure", "code", "retryable"),
    [
        (httpx.ReadTimeout("read"), "delivery_unknown", False),
        (httpx.RemoteProtocolError("disconnected"), "delivery_unknown", False),
        (httpx.ConnectTimeout("connect"), "platform_unavailable", True),
        (httpx.ConnectError("refused"), "platform_unavailable", True),
    ],
)
@respx.mock
async def test_a_failure_after_the_request_went_out_is_delivery_unknown(
    adapter: tuple[InstagramAdapter, SocialAccount],
    failure: Exception,
    code: str,
    retryable: bool,
) -> None:
    ig, acct = adapter
    respx.post(SEND).mock(side_effect=failure)
    with pytest.raises(PlatformError) as raised:
        await ig.send_message(acct, IGSID, OutboundMessage(text="Hi"))
    assert raised.value.code == code
    assert raised.value.retryable is retryable
