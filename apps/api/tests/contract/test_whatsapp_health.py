"""GR-23: a number's quality and tier, and the sandbox WhatsApp bodies, through the real parsers.

*Unverified against live deliveries:* the field names come from Meta's documentation (read
2026-10-24); the sandbox bodies are built to the same shapes.
"""

from __future__ import annotations

import pytest

from socialhood.models.connections import SocialAccount
from socialhood.platforms.sandbox import whatsapp as sandbox
from socialhood.platforms.whatsapp.health import (
    NumberHealth,
    parse_health,
    parse_quality_event,
)
from socialhood.platforms.whatsapp.parse import WhatsAppDeliveryStatus, parse_event
from socialhood.platforms.whatsapp.webhooks import split_payload


def account() -> SocialAccount:
    return SocialAccount(
        platform="whatsapp", platform_account_id="sandbox_abc123", waba_id="sandbox_waba_abc123"
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            {"quality_rating": "GREEN", "messaging_limit_tier": "TIER_1K"},
            NumberHealth("green", "TIER_1K"),
        ),
        (
            {"quality_rating": "RED", "messaging_limit_tier": "TIER_250"},
            NumberHealth("red", "TIER_250"),
        ),
        ({"quality_rating": "YELLOW"}, NumberHealth("yellow", None)),
        ({"quality_rating": "NA"}, NumberHealth("unknown", None)),
        ({}, NumberHealth("unknown", None)),
        (None, NumberHealth("unknown", None)),
    ],
    ids=["green", "red", "yellow-no-tier", "na", "empty", "not-a-dict"],
)
def test_the_apis_answer_becomes_a_rating_and_a_tier(body: object, expected: NumberHealth) -> None:
    assert parse_health(body) == expected


@pytest.mark.parametrize(
    ("event", "rating"),
    [
        ("FLAGGED", "red"),
        ("UNFLAGGED", "yellow"),
        ("UPGRADE", None),
        ("DOWNGRADE", None),
        ("ONBOARDING", None),
    ],
)
def test_a_quality_update_event(event: str, rating: str | None) -> None:
    parsed = parse_quality_event(
        {"display_phone_number": "919800000000", "event": event, "current_limit": "TIER_250"}
    )
    assert parsed is not None
    assert (parsed.event, parsed.quality_rating, parsed.messaging_tier) == (
        event,
        rating,
        "TIER_250",
    )


def test_something_that_is_not_a_quality_update_is_none() -> None:
    assert parse_quality_event({"foo": "bar"}) is None
    assert parse_quality_event(None) is None


def test_a_sandbox_quality_update_is_stored_under_the_business_account() -> None:
    [event] = split_payload(sandbox.quality(account(), event="FLAGGED", tier="TIER_250"))
    assert event.event_type == "phone_number_quality_update"
    assert event.account_ref == "sandbox_waba_abc123"  # routed by waba_id, not the number
    assert parse_quality_event(event.payload["item"]) is not None


def test_a_sandbox_message_parses_as_a_customer_text() -> None:
    [event] = split_payload(
        sandbox.message(account(), sender="919812345678", name="Asha Rao", text="STOP")
    )
    parsed = parse_event(dict(event.payload))
    assert parsed.__class__.__name__ == "InboundMessage"
    assert (parsed.contact_ref, parsed.text, parsed.account_ref) == (  # type: ignore[attr-defined]
        "919812345678",
        "STOP",
        "sandbox_abc123",
    )


@pytest.mark.parametrize("state", ["sent", "delivered", "read"])
def test_a_sandbox_status_parses_as_a_delivery_status(state: str) -> None:
    [event] = split_payload(
        sandbox.status(account(), wamid="wamid.x1", recipient="919812345678", state=state)
    )
    parsed = parse_event(dict(event.payload))
    assert isinstance(parsed, WhatsAppDeliveryStatus)
    assert (parsed.platform_message_id, parsed.status) == ("wamid.x1", state)


def test_a_sandbox_failed_status_carries_the_reason() -> None:
    [event] = split_payload(
        sandbox.status(
            account(),
            wamid="wamid.x2",
            recipient="919812345678",
            state="failed",
            error_code=131026,
            error_text="Message undeliverable",
        )
    )
    parsed = parse_event(dict(event.payload))
    assert isinstance(parsed, WhatsAppDeliveryStatus)
    assert parsed.status == "failed"
    assert (parsed.error_code, parsed.error_message) == (
        "recipient_unavailable",
        "Message undeliverable",
    )


def test_the_sandbox_lists_templates_the_picker_and_broadcasts_can_send() -> None:
    names = {t.name: t for t in sandbox.templates()}
    assert names["sale_offer"].param_count == 2
    assert names["welcome_offer"].param_count == 0
    assert names["login_code"].category == "authentication"
    assert all(t.status == "approved" for t in names.values())
