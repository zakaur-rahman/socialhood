"""WhatsApp Cloud API error codes on top of the shared Graph mapping (TR-PL-03).

The same codes reach us two ways: in the error body of a failed call, and in ``statuses[].errors``
of a ``failed`` delivery status (most window and delivery failures arrive only that way, after
Meta accepted the send). Both map through ``code_for``. T0.9 item 15 confirms the codes.
"""

from __future__ import annotations

from typing import Any

from socialhood.platforms.errors import PlatformError

REENGAGEMENT = 131047  # more than 24 hours since the customer's last message
UNDELIVERABLE = 131026  # not on WhatsApp, old app version, or blocked the business
RATE_LIMITED = frozenset(
    {
        130429,  # Cloud API throughput reached
        131056,  # too many messages to one recipient (pair rate limit)
        80007,  # the WhatsApp Business Account's rate limit
    }
)


def code_for(platform_code: int | None) -> str | None:
    """Our code for a WhatsApp-specific error, or None to keep the Graph mapping."""
    if platform_code == REENGAGEMENT:
        return "reply_window_closed"
    if platform_code == UNDELIVERABLE:
        return "recipient_unavailable"
    if platform_code in RATE_LIMITED:
        return "platform_rate_limited"
    return None


def _leading_code(platform_code: str | None) -> int | None:
    """``"131047"`` or ``"131047/2494010"`` (code/subcode, as PlatformError keeps it) -> 131047."""
    head = (platform_code or "").split("/", 1)[0]
    return int(head) if head.isdigit() else None


def remap(error: PlatformError) -> PlatformError:
    """Apply WhatsApp's codes to an error the shared Graph mapping produced."""
    ours = code_for(_leading_code(error.platform_code))
    if ours is None or ours == error.code:
        return error
    return PlatformError(
        ours,
        platform_code=error.platform_code,
        message=error.message,
        retry_after_s=error.retry_after_s,
    )


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def status_failure(errors: Any) -> tuple[str, str | None, str | None]:
    """(our code, WhatsApp's reason, platform code) for a ``failed`` status's ``errors``."""
    first = errors[0] if isinstance(errors, list) and errors else {}
    if not isinstance(first, dict):
        first = {}
    number = _as_int(first.get("code"))
    data = first["error_data"] if isinstance(first.get("error_data"), dict) else {}
    reason = data.get("details") or first.get("message") or first.get("title")
    return (
        code_for(number) or "platform_rejected",
        str(reason) if reason else None,
        str(number) if number is not None else None,
    )
