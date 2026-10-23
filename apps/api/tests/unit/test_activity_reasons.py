"""GR-05: the Activity page's plain reasons, each with at most one action, and the pure parts of
the feed and the alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from socialhood.models.notifications import PUSH_EVENT_OF_TYPE, NotificationType, PushEvent
from socialhood.services.activity import alerts, feed, reasons
from socialhood.services.sending import readable_error

# Fixed ids: they appear in the parametrized test ids, which every xdist worker must collect alike.
CONV = uuid.UUID("00000000-0000-4000-8000-00000000c0f1")
AUTO = uuid.UUID("00000000-0000-4000-8000-0000000a0701")


@pytest.mark.parametrize(
    ("code", "label", "href"),
    [
        ("account_needs_reconnect", "Reconnect Instagram", "/settings/connections"),
        ("capability_unavailable", "Reconnect Instagram", "/settings/connections"),
        ("read_only", "Upgrade", "/settings/billing"),
        ("entitlement_required", "Upgrade", "/settings/billing"),
        ("quota_exceeded", "Upgrade", "/settings/billing"),
        ("endpoint_off", "Check the endpoint", "/settings/integrations"),
        ("endpoint_error", "Check the endpoint", "/settings/integrations"),
        ("endpoint_unreachable", "Check the endpoint", "/settings/integrations"),
        ("reply_window_closed", "Open the chat", f"/inbox/{CONV}"),
        ("delivery_unknown", "Open the chat", f"/inbox/{CONV}"),
        ("platform_rejected", "Open the chat", f"/inbox/{CONV}"),
        ("nothing_to_send", "Edit the automation", f"/automations/{AUTO}"),
        ("something_new", "Open the automation", f"/automations/{AUTO}"),
    ],
)
def test_each_known_code_has_one_action_and_a_link(code: str, label: str, href: str) -> None:
    reason = reasons.explain(code, platform="instagram", has_conversation=True, has_automation=True)
    assert reason.label == label
    assert feed.href_for(reason.target, conversation_id=CONV, automation_id=AUTO) == href
    assert reason.text


@pytest.mark.parametrize("code", ["expired", "platform_rate_limited", "platform_unavailable"])
def test_a_failure_nobody_can_fix_has_no_action(code: str) -> None:
    reason = reasons.explain(code, has_conversation=True, has_automation=True)
    assert reason.label is None
    assert reason.target is None


def test_the_words_are_the_ones_a_failed_bubble_uses() -> None:
    for code in sorted(reasons.READABLE):
        assert reasons.explain(code, platform="whatsapp", username="shop").text == readable_error(
            code, "whatsapp", username="shop"
        )


def test_the_platform_names_the_reconnect_action() -> None:
    assert reasons.explain("account_needs_reconnect", platform="whatsapp").label == (
        "Reconnect WhatsApp"
    )


def test_a_platform_rejection_keeps_the_stored_reason() -> None:
    stored = "Instagram rejected this: The message is too long."
    assert reasons.explain("platform_rejected", stored=stored).text == stored


def test_an_unknown_code_uses_the_stored_reason_then_a_generic_line() -> None:
    assert reasons.explain("odd", stored="  The DM could not be sent.  ").text == (
        "The DM could not be sent."
    )
    assert reasons.explain(None).text == reasons.GENERIC
    assert reasons.explain("odd").label is None  # no automation to open


def test_an_action_without_its_target_is_left_out() -> None:
    reason = reasons.explain("reply_window_closed", has_conversation=False)
    assert (reason.label, reason.target) == (None, None)
    assert feed.href_for("conversation") is None
    assert feed.href_for("automation") is None


def test_webhook_failures_get_a_code() -> None:
    from socialhood.services.webhooks.delivery import ENDPOINT_OFF

    assert reasons.webhook_code(error=ENDPOINT_OFF, response_code=None) == "endpoint_off"
    assert reasons.webhook_code(error="The endpoint answered 500.", response_code=500) == (
        "endpoint_error"
    )
    assert reasons.webhook_code(error="Couldn't connect.", response_code=None) == (
        "endpoint_unreachable"
    )


def test_only_a_not_now_failure_is_safe_to_retry_by_message() -> None:
    assert reasons.message_retryable("platform_rate_limited")
    assert reasons.message_retryable("platform_unavailable")
    for code in ("delivery_unknown", "reply_window_closed", "account_needs_reconnect", None):
        assert not reasons.message_retryable(code)


def test_a_cursor_round_trips_and_a_bad_one_is_refused() -> None:
    at, row_id = datetime(2026, 10, 1, 12, 30, 5, 123456, tzinfo=UTC), uuid.uuid4()
    assert feed.decode_cursor(feed.encode_cursor(at, row_id)) == (at, row_id)
    from socialhood.errors import ApiError

    with pytest.raises(ApiError) as caught:
        feed.decode_cursor("not-a-cursor")
    assert caught.value.code == "bad_request"


def test_an_alert_is_one_per_automation_per_six_hours() -> None:
    at = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)  # inside the 06:00 to 12:00 bucket
    same = alerts.dedupe_key(AUTO, at + timedelta(hours=4))
    later = alerts.dedupe_key(AUTO, at + timedelta(hours=6))
    assert alerts.dedupe_key(AUTO, at) == same != later
    assert alerts.dedupe_key(uuid.uuid4(), at) != same


def test_the_failing_alert_pushes_under_needs_you() -> None:
    assert PUSH_EVENT_OF_TYPE[NotificationType.AUTOMATION_FAILING] == PushEvent.NEEDS_YOU
    assert alerts.FAILING_RUNS == 5
    assert timedelta(hours=1) == alerts.WINDOW
