"""T3.2 (TR-PL-12): every Instagram payload type parses into its typed event.

One fixture per payload type (tests/fixtures/meta/README.md); each goes through ``split_payload``
first, exactly as stored webhook events do.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from socialhood.platforms.events import (
    InboundComment,
    InboundEvent,
    InboundMessage,
    MessageDeleted,
    MessageEdit,
    Reaction,
    ReadReceipt,
    Unsupported,
)
from socialhood.platforms.instagram.parse import epoch_time, graph_time, media_item, parse, thread
from socialhood.platforms.instagram.webhooks import split_payload
from tests.support.instagram import fixture

ACCOUNT = "17841400000000001"
CUSTOMER = "990000000000001"


def parsed(name: str) -> InboundEvent:
    [raw] = split_payload(fixture(name))
    return parse(raw.payload)


def message(name: str) -> InboundMessage:
    event = parsed(name)
    assert isinstance(event, InboundMessage), event
    return event


@pytest.mark.parametrize(
    ("name", "kind", "text", "attachments"),
    [
        ("webhook_message_text.json", "text", "Hi! Is the sourdough available today?", []),
        ("webhook_message_reply.json", "text", "This one please", []),
        ("webhook_message_image.json", "image", None, ["image"]),
        ("webhook_message_video.json", "video", None, ["video"]),
        ("webhook_message_audio.json", "audio", None, ["audio"]),
        ("webhook_message_file.json", "file", None, ["file"]),
        ("webhook_message_sticker.json", "sticker", None, ["sticker"]),
        ("webhook_story_mention.json", "story_mention", None, ["story"]),
        ("webhook_story_reply.json", "story_reply", "Where is this cake from?", ["story"]),
        ("webhook_share.json", "share", None, ["share"]),
        ("webhook_share_reel.json", "share", None, ["share"]),
        ("webhook_message_unsupported.json", "unsupported", None, []),
        ("webhook_postback.json", "text", "What are your opening hours?", []),
    ],
)
def test_customer_messages(name: str, kind: str, text: str | None, attachments: list[str]) -> None:
    event = message(name)
    assert (event.kind, event.text) == (kind, text)
    assert [a.kind for a in event.attachments] == attachments
    assert all(a.url and a.url.startswith("https://") for a in event.attachments)
    assert (event.account_ref, event.contact_ref, event.is_echo) == (ACCOUNT, CUSTOMER, False)
    assert event.contact_name is None
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.year == 2026  # milliseconds, not seconds


def test_a_reply_points_at_the_message_it_answers() -> None:
    assert (
        message("webhook_message_reply.json").reply_to_id
        == message("webhook_message_text.json").platform_message_id
    )


def test_an_echo_belongs_to_the_recipient() -> None:
    event = message("webhook_echo.json")
    assert event.is_echo
    assert (event.contact_ref, event.text) == (CUSTOMER, "Yes, until 6 pm!")


def test_reactions() -> None:
    react, unreact = parsed("webhook_reaction.json"), parsed("webhook_unreact.json")
    assert isinstance(react, Reaction)
    assert isinstance(unreact, Reaction)
    assert (react.contact_ref, react.emoji) == (CUSTOMER, "❤️")
    assert unreact.emoji is None
    assert react.platform_message_id == unreact.platform_message_id


def test_a_reaction_without_an_emoji_uses_its_name() -> None:
    body = fixture("webhook_reaction.json")
    del body["entry"][0]["messaging"][0]["reaction"]["emoji"]
    [raw] = split_payload(body)
    event = parse(raw.payload)
    assert isinstance(event, Reaction)
    assert event.emoji == "❤️"


def test_seen_and_edit() -> None:
    seen, edit = parsed("webhook_seen.json"), parsed("webhook_message_edit.json")
    assert isinstance(seen, ReadReceipt)
    assert seen.contact_ref == CUSTOMER
    assert seen.last_read_message_id == message("webhook_echo.json").platform_message_id
    assert isinstance(edit, MessageEdit)
    assert edit.text == "Hi! Is the rye sourdough available today?"
    assert edit.platform_message_id == message("webhook_message_text.json").platform_message_id


def test_an_unsent_message_becomes_a_deletion() -> None:
    event = parsed("webhook_message_deleted.json")
    assert isinstance(event, MessageDeleted)
    assert (
        event.platform_message_id
        == fixture("webhook_message_text.json")["entry"][0]["messaging"][0]["message"]["mid"]
    )


def test_an_unsend_has_its_own_dedupe_key() -> None:
    """It reuses the original message's mid; the same key would drop it as a re-delivery."""
    [original] = split_payload(fixture("webhook_message_text.json"))
    [unsend] = split_payload(fixture("webhook_message_deleted.json"))
    assert unsend.dedupe_key != original.dedupe_key
    assert unsend.event_type == "unsend"


def test_comments_parse_for_p6() -> None:
    for name in ("webhook_comment_changes.json", "webhook_comment_field_value.json"):
        event = parsed(name)
        assert isinstance(event, InboundComment)
        assert event.media_id == "18100000000000001"
        # Changes carry entry.time in seconds (T0.9 item 2).
        assert event.occurred_at.year == 2026


def _messaging(item: dict[str, Any]) -> InboundEvent:
    body = {
        "object": "instagram",
        "entry": [{"id": ACCOUNT, "time": 1790000000, "messaging": [item]}],
    }
    [raw] = split_payload(body)
    return parse(raw.payload)


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        ({"sender": {"id": CUSTOMER}, "referral": {"ref": "ad"}}, "referral events"),
        ({"sender": {"id": CUSTOMER}, "something": "new"}, "unknown messaging event"),
        ({"sender": {"id": CUSTOMER}, "message": {"text": "no id"}}, "message without an id"),
        (
            {"sender": {"id": ACCOUNT}, "reaction": {"mid": "m1", "action": "react"}},
            "reaction by the account",
        ),
        ({"sender": {"id": ACCOUNT}, "read": {"mid": "m1"}}, "read by the account"),
        ({"sender": {"id": CUSTOMER}, "message_edit": {"mid": "m1"}}, "unreadable edit"),
    ],
)
def test_what_is_not_acted_on_says_why(item: dict[str, Any], reason: str) -> None:
    event = _messaging(item)
    assert isinstance(event, Unsupported)
    assert event.reason == reason


def test_an_unknown_attachment_alone_is_unsupported() -> None:
    event = _messaging(
        {
            "sender": {"id": CUSTOMER},
            "recipient": {"id": ACCOUNT},
            "message": {"mid": "m2", "attachments": [{"type": "hologram", "payload": {}}]},
        }
    )
    assert isinstance(event, InboundMessage)
    assert (event.kind, event.attachments) == ("unsupported", ())


def test_a_message_from_the_account_is_an_echo_even_without_the_flag() -> None:
    event = _messaging(
        {
            "sender": {"id": ACCOUNT},
            "recipient": {"id": CUSTOMER},
            "message": {"mid": "m3", "text": "Hi"},
        }
    )
    assert isinstance(event, InboundMessage)
    assert (event.is_echo, event.contact_ref) == (True, CUSTOMER)


def test_an_unreadable_stored_event() -> None:
    assert isinstance(parse({"entry_id": ACCOUNT, "kind": "messaging", "item": None}), Unsupported)
    other = parse(
        {"entry_id": ACCOUNT, "time": 1790000000, "kind": "change", "field": "mentions", "item": {}}
    )
    assert isinstance(other, Unsupported)
    assert other.reason == "mentions changes"


def test_timestamps() -> None:
    assert (
        epoch_time(1790000000)
        == epoch_time(1790000000000)
        == datetime.fromtimestamp(1790000000, UTC)
    )
    assert epoch_time(None, datetime(2026, 1, 1, tzinfo=UTC)).year == 2026
    assert graph_time("2026-09-27T09:12:00+0000") == datetime(2026, 9, 27, 9, 12, tzinfo=UTC)
    assert graph_time("2026-09-27T09:12:00") == datetime(2026, 9, 27, 9, 12, tzinfo=UTC)
    assert graph_time("yesterday") is None


def test_media_items() -> None:
    items = [media_item(i) for i in fixture("media_list.json")["data"]]
    assert [(m.media_type, m.like_count) for m in items if m] == [
        ("image", 57),
        ("carousel", None),
        ("reel", 212),
    ]
    assert media_item({"id": "1"}) is None  # no timestamp


def test_a_thread_orders_messages_and_knows_who_sent_them() -> None:
    conversation = fixture("conversations_list.json")["data"][0]
    messages = fixture("conversation_messages.json")["messages"]["data"]
    result = thread(
        conversation,
        messages,
        account_ref=ACCOUNT,
        own_ids=frozenset({ACCOUNT}),
        own_username="maple.bakery",
    )
    assert result is not None
    assert (result.contact_ref, result.contact_username) == (CUSTOMER, "priya.shah")
    assert [(m.is_echo, m.kind, m.text) for m in result.messages] == [
        (False, "text", "Do you deliver to Koregaon Park?"),
        (True, "text", "We do! Delivery is free above 500."),
        (False, "image", None),
    ]
    assert result.messages[2].attachments[0].url is not None


def test_a_thread_without_participants_finds_the_contact_from_messages() -> None:
    messages = fixture("conversation_messages.json")["messages"]["data"]
    result = thread(
        {"id": "t1"},
        messages,
        account_ref=ACCOUNT,
        own_ids=frozenset(),
        own_username="maple.bakery",
    )
    assert result is not None
    assert result.contact_ref == CUSTOMER
    assert (
        thread({"id": "t2"}, [], account_ref=ACCOUNT, own_ids=frozenset(), own_username=None)
        is None
    )


def test_a_heart_sticker_arrives_as_its_emoji() -> None:
    event = parsed("webhook_message_heart.json")
    assert isinstance(event, InboundMessage)
    assert (event.kind, event.text, event.attachments) == ("sticker", "❤️", ())
