"""TR-PL-12 for WhatsApp: each stored event parses into one typed inbound event (F-06, F-07)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from socialhood.platforms.events import (
    InboundEvent,
    InboundMediaRef,
    InboundMessage,
    Reaction,
    Unsupported,
)
from socialhood.platforms.whatsapp.parse import WhatsAppDeliveryStatus, parse_event
from socialhood.platforms.whatsapp.webhooks import split_payload
from tests.support.instagram import fixture
from tests.support.whatsapp import CUSTOMER, PHONE_NUMBER_ID


def parsed(name: str) -> list[InboundEvent]:
    return [parse_event(e.payload) for e in split_payload(fixture(name))]


def by_id(events: list[InboundEvent], suffix: str) -> InboundEvent:
    return next(
        e for e in events if getattr(e, "platform_message_id", "").startswith(f"wamid.{suffix}")
    )


def test_a_text_message() -> None:
    [event] = parsed("whatsapp_webhook_text.json")
    assert event == InboundMessage(
        account_ref=PHONE_NUMBER_ID,
        occurred_at=datetime(2025, 9, 28, 8, 0, tzinfo=UTC),
        contact_ref=CUSTOMER,
        contact_name="Priya Shah",
        platform_message_id="wamid.HBgMOTE5ODEyMzQ1Njc4FQIAEhggM0E0QTY1OTlBRUUwMzgxMDE0NEYA",
        kind="text",
        text="Do you ship to Pune?",
    )


@pytest.mark.parametrize(
    ("suffix", "kind", "attachment", "media_id", "text"),
    [
        ("IMAGE", "image", "image", "1003383421387256", "This one in blue?"),
        ("VIDEO", "video", "video", "1003383421387257", None),
        ("AUDIO", "audio", "audio", "1003383421387258", None),
        ("DOCUMENT", "file", "file", "1003383421387259", "My order"),
        ("STICKER", "sticker", "sticker", "1003383421387260", None),
    ],
)
def test_media_messages_carry_the_media_id(
    suffix: str, kind: str, attachment: Any, media_id: str, text: str | None
) -> None:
    event = by_id(parsed("whatsapp_webhook_media.json"), suffix)
    assert isinstance(event, InboundMessage)
    assert (event.kind, event.text) == (kind, text)
    [ref] = event.attachments
    assert (ref.kind, ref.media_id, ref.url) == (attachment, media_id, None)
    assert ref.mime_type
    assert event.contact_name == "Priya Shah"


def test_a_document_keeps_its_file_name() -> None:
    event = by_id(parsed("whatsapp_webhook_media.json"), "DOCUMENT")
    assert isinstance(event, InboundMessage)
    [ref] = event.attachments
    assert isinstance(ref, InboundMediaRef)
    assert ref.filename == "order-1042.pdf"


def test_a_location_becomes_readable_text() -> None:
    event = by_id(parsed("whatsapp_webhook_other.json"), "LOCATION")
    assert isinstance(event, InboundMessage)
    assert event.kind == "location"
    assert (
        event.text == "Maple Bakery\n12 FC Road, Pune\nhttps://maps.google.com/?q=18.5204,73.8567"
    )


def test_a_template_button_reply_is_text_replying_to_our_template() -> None:
    event = by_id(parsed("whatsapp_webhook_other.json"), "BUTTON")
    assert isinstance(event, InboundMessage)
    assert (event.kind, event.text) == ("text", "Yes, confirm")
    assert event.reply_to_id == "wamid.TEMPLATESENT0000000000000000000000000000001"
    assert (event.contact_ref, event.contact_name) == ("919811111111", "Arjun Rao")


def test_an_interactive_reply_is_its_title() -> None:
    event = by_id(parsed("whatsapp_webhook_other.json"), "INTERACTIVE")
    assert isinstance(event, InboundMessage)
    assert (event.kind, event.text) == ("text", "Tomorrow 10am")


def test_reactions_and_their_removal() -> None:
    reactions = [e for e in parsed("whatsapp_webhook_other.json") if isinstance(e, Reaction)]
    assert [(r.platform_message_id, r.emoji) for r in reactions] == [
        ("wamid.OUTBOUND000000000000000000000000000000001", "❤️"),
        ("wamid.OUTBOUND000000000000000000000000000000001", None),
    ]
    assert {r.contact_ref for r in reactions} == {CUSTOMER}


@pytest.mark.parametrize("suffix", ["UNSUPPORTED", "CONTACTS"])
def test_types_we_cannot_show_are_unsupported_bubbles(suffix: str) -> None:
    event = by_id(parsed("whatsapp_webhook_other.json"), suffix)
    assert isinstance(event, InboundMessage)
    assert (event.kind, event.text, event.attachments) == ("unsupported", None, ())


def test_system_messages_are_not_messages() -> None:
    events = parsed("whatsapp_webhook_other.json")
    [system] = [e for e in events if isinstance(e, Unsupported)]
    assert system.reason == "system message"


def test_delivery_statuses() -> None:
    events = parsed("whatsapp_webhook_statuses.json")
    assert all(isinstance(e, WhatsAppDeliveryStatus) for e in events)
    statuses = [e for e in events if isinstance(e, WhatsAppDeliveryStatus)]
    assert [s.status for s in statuses] == ["sent", "delivered", "read", "failed"]
    assert statuses[0].occurred_at == datetime.fromtimestamp(1759046500, UTC)
    assert statuses[0].error_code is None
    failed = statuses[3]
    assert failed.platform_message_id == "wamid.OUTBOUND000000000000000000000000000000002"
    assert (failed.error_code, failed.platform_code) == ("reply_window_closed", "131047")
    assert failed.error_message is not None
    assert failed.error_message.startswith("Message failed to send because more than 24 hours")


@pytest.mark.parametrize(
    ("errors", "code", "platform_code"),
    [
        ([{"code": 131026, "title": "Message Undeliverable"}], "recipient_unavailable", "131026"),
        ([{"code": 131056, "title": "Pair rate limit"}], "platform_rate_limited", "131056"),
        ([{"code": 131049, "title": "Not delivered"}], "platform_rejected", "131049"),
        (None, "platform_rejected", None),
    ],
)
def test_failure_codes_map_to_ours(errors: Any, code: str, platform_code: str | None) -> None:
    body = fixture("whatsapp_webhook_statuses.json")
    status = body["entry"][0]["changes"][0]["value"]["statuses"][3]
    if errors is None:
        del status["errors"]
    else:
        status["errors"] = errors
    event = parse_event(split_payload(body)[3].payload)
    assert isinstance(event, WhatsAppDeliveryStatus)
    assert (event.error_code, event.platform_code) == (code, platform_code)


def test_statuses_we_do_not_track_are_unsupported() -> None:
    body = fixture("whatsapp_webhook_statuses.json")
    body["entry"][0]["changes"][0]["value"]["statuses"][0]["status"] = "deleted"
    event = parse_event(split_payload(body)[0].payload)
    assert isinstance(event, Unsupported)
    assert event.reason == "deleted status"


def test_malformed_shapes_are_unsupported_not_errors() -> None:
    body = fixture("whatsapp_webhook_text.json")
    del body["entry"][0]["changes"][0]["value"]["messages"][0]["timestamp"]
    [missing_time] = [parse_event(e.payload) for e in split_payload(body)]
    assert isinstance(missing_time, Unsupported)
    [other] = parsed("whatsapp_webhook_template_status.json")
    assert isinstance(other, Unsupported)
    assert other.reason == "message_template_status_update events are not used"
