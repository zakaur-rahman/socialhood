"""The Instagram calls automations make (T4.4, T4.8; FR-AUT-08, FR-AUT-13, FR-AUT-14,
FR-AUT-21, FR-AUT-22, F-12): link buttons as the button template, quick replies, private replies
addressed by comment, public comment replies, one post by id, and the profile's follow status.
Shapes follow Meta's docs (checked 2026-09-29); T0.9 items 4 and 10 confirm them on a real
account."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    OutboundAttachment,
    OutboundButton,
    OutboundMessage,
    OutboundQuickReply,
)
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
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
BASE = f"{GRAPH}/{SETTINGS.ig_graph_version}"
SEND = f"{BASE}/me/messages"
TOKEN = "IGQVJsend-token"
IGSID = "1234567890123456"
COMMENT = "18000000000000001"
BUTTONS = (
    OutboundButton(title="Shop now", url="https://maple.example/shop"),
    OutboundButton(title="Sizes", url="https://maple.example/sizes"),
)


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


def body(route: respx.Route) -> dict[str, object]:
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert "access_token" not in str(request.url)
    sent: dict[str, object] = json.loads(request.content)
    return sent


BUTTON_TEMPLATE = {
    "attachment": {
        "type": "template",
        "payload": {
            "template_type": "button",
            "text": "Here's the link",
            "buttons": [
                {"type": "web_url", "url": "https://maple.example/shop", "title": "Shop now"},
                {"type": "web_url", "url": "https://maple.example/sizes", "title": "Sizes"},
            ],
        },
    }
}


@respx.mock
async def test_text_with_buttons_is_the_button_template(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID, "message_id": "mid.1"})
    result = await ig.send_message(
        acct, IGSID, OutboundMessage(text="Here's the link", buttons=BUTTONS)
    )
    assert result.platform_message_id == "mid.1"
    assert body(route) == {"recipient": {"id": IGSID}, "message": BUTTON_TEMPLATE}


async def test_button_limits(adapter: tuple[InstagramAdapter, SocialAccount]) -> None:
    ig, acct = adapter
    four = (*BUTTONS, *BUTTONS)
    for message in (
        OutboundMessage(text="x" * 641, buttons=BUTTONS),  # 640 characters with buttons
        OutboundMessage(text="Hi", buttons=four),
        OutboundMessage(buttons=BUTTONS),
    ):
        with pytest.raises(PlatformError) as raised:
            await ig.send_message(acct, IGSID, message)
        assert raised.value.code == "platform_rejected"


@respx.mock
async def test_a_private_reply_is_addressed_by_the_comment(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID, "message_id": "mid.2"})
    result = await ig.private_reply(acct, COMMENT, OutboundMessage(text="Here's the link"))
    assert result.platform_message_id == "mid.2"
    assert body(route) == {
        "recipient": {"comment_id": COMMENT},
        "message": {"text": "Here's the link"},
    }

    await ig.private_reply(acct, COMMENT, OutboundMessage(text="Here's the link", buttons=BUTTONS))
    assert body(route) == {"recipient": {"comment_id": COMMENT}, "message": BUTTON_TEMPLATE}


QUICK_REPLY = OutboundQuickReply(title="Send me the link", payload="shr:run-1")


@respx.mock
async def test_quick_replies_go_with_the_text(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    """T4.8 (FR-AUT-21): Meta's quick_replies, content_type text, on a DM and on a private
    reply (Meta's private-reply docs show text only: the runtime falls back when refused)."""
    ig, acct = adapter
    route = respx.post(SEND).respond(200, json={"recipient_id": IGSID, "message_id": "mid.3"})
    opening = OutboundMessage(text="Hi there! Tap below", quick_replies=(QUICK_REPLY,))
    quick = {
        "text": "Hi there! Tap below",
        "quick_replies": [
            {"content_type": "text", "title": "Send me the link", "payload": "shr:run-1"}
        ],
    }

    await ig.private_reply(acct, COMMENT, opening)
    assert body(route) == {"recipient": {"comment_id": COMMENT}, "message": quick}
    await ig.send_message(acct, IGSID, opening)
    assert body(route) == {"recipient": {"id": IGSID}, "message": quick}


async def test_quick_reply_limits(adapter: tuple[InstagramAdapter, SocialAccount]) -> None:
    ig, acct = adapter
    for message in (
        OutboundMessage(text="Hi", quick_replies=(QUICK_REPLY,), buttons=BUTTONS),
        OutboundMessage(text="Hi", quick_replies=(QUICK_REPLY,) * 14),
        OutboundMessage(quick_replies=(QUICK_REPLY,)),
    ):
        with pytest.raises(PlatformError) as raised:
            await ig.send_message(acct, IGSID, message)
        assert raised.value.code == "platform_rejected"


@respx.mock
async def test_the_profile_asks_whether_they_follow_the_account(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    """T4.8 (FR-AUT-22): is_user_follow_business, True, False or absent (unknown)."""
    ig, acct = adapter
    route = respx.get(f"{BASE}/{IGSID}")
    route.respond(200, json=fixture("user_profile.json"))
    profile = await ig.fetch_contact_profile(acct, IGSID)
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert request.url.params["fields"] == "name,username,profile_pic,is_user_follow_business"
    assert profile is not None
    assert (profile.name, profile.follows_business) == ("Priya Shah", True)

    route.respond(200, json={**fixture("user_profile.json"), "is_user_follow_business": False})
    profile = await ig.fetch_contact_profile(acct, IGSID)
    assert profile is not None
    assert profile.follows_business is False

    route.respond(200, json={"name": "Priya Shah", "username": "priya.shah"})
    profile = await ig.fetch_contact_profile(acct, IGSID)
    assert profile is not None
    assert profile.follows_business is None


async def test_a_private_reply_carries_no_attachment(
    adapter: tuple[InstagramAdapter, SocialAccount],
) -> None:
    ig, acct = adapter
    image = OutboundAttachment(type="image", url="https://res.cloudinary.com/x/a.jpg")
    for message in (OutboundMessage(attachment=image), OutboundMessage(sticker="like_heart")):
        with pytest.raises(PlatformError) as raised:
            await ig.private_reply(acct, COMMENT, message)
        assert raised.value.code == "platform_rejected"
    with pytest.raises(PlatformError):
        await ig.private_reply(acct, "../me/messages", OutboundMessage(text="Hi"))


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (httpx.ReadTimeout("read"), "delivery_unknown"),
        (httpx.ConnectError("x"), "platform_unavailable"),
    ],
)
@respx.mock
async def test_a_private_reply_that_may_have_gone_out_is_never_retried(
    adapter: tuple[InstagramAdapter, SocialAccount], failure: Exception, code: str
) -> None:
    ig, acct = adapter
    respx.post(SEND).mock(side_effect=failure)
    with pytest.raises(PlatformError) as raised:
        await ig.private_reply(acct, COMMENT, OutboundMessage(text="Hi"))
    assert raised.value.code == code


@respx.mock
async def test_a_public_reply(adapter: tuple[InstagramAdapter, SocialAccount]) -> None:
    ig, acct = adapter
    route = respx.post(f"{BASE}/{COMMENT}/replies").respond(200, json={"id": "17900000000000009"})
    reply_id = await ig.reply_to_comment(acct, COMMENT, "Check your DMs, @curious.cat!")
    assert reply_id == "17900000000000009"
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert request.url.params["message"] == "Check your DMs, @curious.cat!"

    respx.post(f"{BASE}/{COMMENT}/replies").respond(400, json={"error": {"code": 100}})
    with pytest.raises(PlatformError) as raised:
        await ig.reply_to_comment(acct, COMMENT, "Again")
    assert raised.value.code == "platform_rejected"


@respx.mock
async def test_one_post_by_id(adapter: tuple[InstagramAdapter, SocialAccount]) -> None:
    ig, acct = adapter
    raw = fixture("media_list.json")["data"][0]
    route = respx.get(f"{BASE}/{raw['id']}").respond(200, json=raw)
    media = await ig.get_media(acct, str(raw["id"]))
    assert media is not None
    assert media.platform_media_id == raw["id"]
    assert "timestamp" in route.calls.last.request.url.params["fields"]
    with pytest.raises(PlatformError):
        await ig.get_media(acct, "1/../me")
