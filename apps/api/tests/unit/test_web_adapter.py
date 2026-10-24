"""GR-28: the website chat as a platform. Sending stores nothing outside our database, the reply
window never closes, and the adapter refuses everything a platform with posts would do."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import OutboundAttachment, OutboundMessage
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.web.adapter import WebAdapter
from socialhood.services.reply_window import may_send, reply_window
from socialhood.services.sending import platform_name, text_limit_error


def account() -> SocialAccount:
    return SocialAccount(
        id=uuid.uuid4(), platform="web", platform_account_id="wgt_abcdefghijklmnop", status="active"
    )


def adapter() -> WebAdapter:
    return WebAdapter(MagicMock())


async def test_a_send_returns_an_id_and_asks_nothing_of_a_platform() -> None:
    first = await adapter().send_message(account(), "v_1", OutboundMessage(text="Hello"))
    second = await adapter().send_message(account(), "v_1", OutboundMessage(text="Hello"))
    assert first.platform_message_id
    assert first.platform_message_id.startswith("web_")
    assert first.platform_message_id != second.platform_message_id


@pytest.mark.parametrize(
    "message",
    [
        OutboundMessage(),
        OutboundMessage(attachment=OutboundAttachment(type="image", url="https://x/y.jpg")),
        OutboundMessage(sticker="like_heart"),
    ],
)
async def test_only_text_is_sent(message: OutboundMessage) -> None:
    with pytest.raises(PlatformError) as error:
        await adapter().send_message(account(), "v_1", message)
    assert error.value.code == "platform_rejected"


def test_it_sends_text_and_nothing_else() -> None:
    assert adapter().capabilities_for(account()) == frozenset({Capability.DM_SEND})


async def test_what_a_website_has_none_of_is_unavailable() -> None:
    web, acct = adapter(), account()
    calls: list[Any] = [
        web.refresh_token(acct),
        web.download_media(acct, MagicMock()),
        web.set_ice_breakers(acct, []),
        web.private_reply(acct, "c", OutboundMessage(text="x")),
        web.reply_to_comment(acct, "c", "x"),
        web.list_comments(acct, "m"),
        web.hide_comment(acct, "c"),
        web.get_media_counts(acct, "m"),
        web.get_account_insights(acct, date(2026, 10, 1)),
        web.get_publishing_quota(acct),
        web.publish_container(acct, "c"),
        web.post_comment(acct, "m", "x"),
    ]
    for call in calls:
        with pytest.raises(PlatformError) as error:
            await call
        assert error.value.code == "capability_unavailable"
    assert await web.list_threads(acct) == []
    assert await web.list_media(acct) == []
    assert await web.fetch_contact_profile(acct, "v_1") is None
    assert await web.mark_read(acct, "v_1") is None


def test_the_registry_picks_the_web_adapter() -> None:
    assert isinstance(adapter_for(account(), MagicMock()), WebAdapter)


def test_the_window_never_closes() -> None:
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    for last in (None, now, now - timedelta(days=40)):
        window = reply_window("web", last, human_agent=False, now=now)
        assert window.state == "open"
        assert may_send(window, "ai_auto")
        assert may_send(window, "human")


def test_web_replies_are_capped_and_named_for_people() -> None:
    assert platform_name("web") == "Website"
    assert text_limit_error("web", "x" * 2000) is None
    assert text_limit_error("web", "x" * 2001) is not None
