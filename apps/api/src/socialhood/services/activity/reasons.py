"""Plain-language reasons for the Activity page (GR-05): one sentence and at most one action per
failure.

The words are the ones the rest of the product already uses: ``sending.readable_error`` is the
copy of a Failed bubble and of a run's stored reason, so a code it knows is explained with it
(with the account's name and platform); the run, webhook and plan reasons that have no bubble
are written here. An unknown code falls back to the reason stored with the failure, then to a
generic line. Nothing here reads a raw payload or a platform's raw response.

An action is a target the feed turns into a link (``feed.href_for``): reconnect the account,
upgrade the plan, check the endpoint, open the chat or the automation. A failure nobody can fix
(Instagram's 7-day limit, a closed reply window) still points at where to look, or at nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.services.sending import platform_name, readable_error
from socialhood.services.webhooks.delivery import ENDPOINT_OFF as OFF_TEXT

Target = Literal["connections", "billing", "integrations", "conversation", "automation"]

# Codes sending.readable_error words itself (everything it knows except platform_rejected, whose
# stored reason already carries the platform's message).
READABLE = frozenset(
    {
        "reply_window_closed",
        "account_needs_reconnect",
        "capability_unavailable",
        "recipient_unavailable",
        "platform_rate_limited",
        "platform_unavailable",
        DELIVERY_UNKNOWN,
    }
)

# Webhook delivery failures have no code of their own; the feed derives one (webhook_code).
ENDPOINT_OFF = "endpoint_off"
ENDPOINT_ERROR = "endpoint_error"
ENDPOINT_UNREACHABLE = "endpoint_unreachable"

# Run codes that are not API error codes (services/automations: runtime, results, queue).
EXPIRED = "expired"
READ_ONLY = "read_only"
NOTHING_SENT = "nothing_sent"
NOTHING_TO_SEND = "nothing_to_send"

PLAN_CODES = frozenset({READ_ONLY, "entitlement_required", "quota_exceeded"})
RECONNECT_CODES = frozenset({"account_needs_reconnect", "capability_unavailable"})
ENDPOINT_CODES = frozenset({ENDPOINT_OFF, ENDPOINT_ERROR, ENDPOINT_UNREACHABLE})

# A failed message can be sent again safely when the platform only said "not now": the send
# pipeline keeps one row and one client id, so a retry never doubles it (sending.retry). Not
# delivery_unknown: it may have arrived, so the member checks the chat first.
RETRYABLE_MESSAGE_CODES = frozenset({"platform_rate_limited", "platform_unavailable"})

GENERIC = "Something went wrong on our side. Try again in a few minutes."


@dataclass(frozen=True)
class Reason:
    text: str
    code: str | None
    label: str | None = None  # the one action's words ("Reconnect Instagram")
    target: Target | None = None


def explain(
    code: str | None,
    *,
    stored: str | None = None,
    platform: str | None = None,
    username: str | None = None,
    has_conversation: bool = False,
    has_automation: bool = False,
) -> Reason:
    """The sentence and the action for a failure with this code. ``stored`` is the reason saved
    with the failure (a message's or run's error_message)."""
    platform = platform or "instagram"
    name = platform_name(platform)
    stored = (stored or "").strip() or None

    if code in RECONNECT_CODES:
        return Reason(_readable(code, platform, username), code, f"Reconnect {name}", "connections")
    if code in PLAN_CODES:
        text = stored or "Your plan doesn't include this."
        return Reason(text, code, "Upgrade", "billing")
    if code == EXPIRED:
        return Reason(
            f"{name} only lets an account reply privately to a comment within 7 days.", code
        )
    if code == "reply_window_closed":
        return Reason(
            _readable(code, platform, username),
            code,
            "Open the chat" if has_conversation else None,
            "conversation" if has_conversation else None,
        )
    if code in (DELIVERY_UNKNOWN, "recipient_unavailable", "platform_rejected"):
        text = (
            stored
            if code == "platform_rejected" and stored
            else _readable(code, platform, username)
        )
        return Reason(
            text,
            code,
            "Open the chat" if has_conversation else None,
            "conversation" if has_conversation else None,
        )
    if code in ("platform_rate_limited", "platform_unavailable"):
        return Reason(_readable(code, platform, username), code)
    if code in (NOTHING_SENT, NOTHING_TO_SEND):
        return Reason(
            stored or "The automation has no message to send.",
            code,
            "Edit the automation" if has_automation else None,
            "automation" if has_automation else None,
        )
    if code == ENDPOINT_OFF:
        return Reason(
            "The endpoint was turned off before this was sent.",
            code,
            "Check the endpoint",
            "integrations",
        )
    if code == ENDPOINT_ERROR:
        return Reason(
            stored or "Your endpoint answered with an error.",
            code,
            "Check the endpoint",
            "integrations",
        )
    if code == ENDPOINT_UNREACHABLE:
        return Reason(
            stored or "Your endpoint couldn't be reached.",
            code,
            "Check the endpoint",
            "integrations",
        )
    return Reason(
        stored or GENERIC,
        code,
        "Open the automation" if has_automation else None,
        "automation" if has_automation else None,
    )


def _readable(code: str, platform: str, username: str | None) -> str:
    return readable_error(code, platform, username=username)


def webhook_code(*, error: str | None, response_code: int | None) -> str:
    """The reason code of a failed outbound webhook delivery (delivery.py stores text only)."""
    if error == OFF_TEXT:
        return ENDPOINT_OFF
    return ENDPOINT_ERROR if response_code is not None else ENDPOINT_UNREACHABLE


def message_retryable(code: str | None) -> bool:
    return code in RETRYABLE_MESSAGE_CODES
