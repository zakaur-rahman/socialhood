"""The sandbox WhatsApp number (GR-23): approved templates to send, and the webhook bodies a real
number would deliver (a message from a customer, a delivery status, a quality update), so
broadcasts, statuses, STOP replies and pauses run without Meta.

A sandbox WhatsApp account is a ``SocialAccount`` with platform ``whatsapp`` and a
``sandbox_`` phone number id (``SandboxAdapter`` serves it). Its sends are recorded in
``sandbox.outbox`` like Instagram's (a template's parameters containing ``[sandbox:fail=<code>]``
fail that send); statuses are injected with ``POST /dev/sandbox/inbound`` kind ``status``, and
quality updates with kind ``quality``. The bodies have the shapes of Meta's documented webhooks.
*Unverified against live deliveries.*
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from socialhood.models.connections import SocialAccount
from socialhood.platforms.whatsapp.templates import MessageTemplate

TEMPLATES: tuple[MessageTemplate, ...] = (
    MessageTemplate(
        name="sale_offer",
        language="en",
        category="marketing",
        status="approved",
        body="Hi {{1}}, our sale is on until {{2}}. Reply STOP to opt out.",
        param_count=2,
    ),
    MessageTemplate(
        name="welcome_offer",
        language="en",
        category="marketing",
        status="approved",
        body="Welcome to the shop! Show this message for a free gift.",
        param_count=0,
    ),
    MessageTemplate(
        name="order_shipped",
        language="en",
        category="utility",
        status="approved",
        body="Hi {{1}}, your order {{2}} has shipped.",
        param_count=2,
    ),
    MessageTemplate(
        name="login_code",
        language="en",
        category="authentication",
        status="approved",
        body="{{1}} is your verification code.",
        param_count=1,
    ),
)


def templates() -> list[MessageTemplate]:
    return list(TEMPLATES)


def waba_of(acct: SocialAccount) -> str:
    return acct.waba_id or f"{acct.platform_account_id}_waba"


def _display_number(acct: SocialAccount) -> str:
    return "91" + "".join(ch for ch in acct.platform_account_id if ch.isdigit())[:10].ljust(10, "0")


def _entry(acct: SocialAccount, field: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {"id": waba_of(acct), "changes": [{"field": field, "value": value}]},
        ],
    }


def _metadata(acct: SocialAccount) -> dict[str, str]:
    return {
        "display_phone_number": _display_number(acct),
        "phone_number_id": acct.platform_account_id,
    }


def new_wamid() -> str:
    return f"wamid.sandbox{secrets.token_hex(10)}"


def message(acct: SocialAccount, *, sender: str, name: str, text: str) -> dict[str, Any]:
    """A customer's text message to the number."""
    return _entry(
        acct,
        "messages",
        {
            "messaging_product": "whatsapp",
            "metadata": _metadata(acct),
            "contacts": [{"profile": {"name": name}, "wa_id": sender}],
            "messages": [
                {
                    "from": sender,
                    "id": new_wamid(),
                    "timestamp": str(int(time.time())),
                    "type": "text",
                    "text": {"body": text},
                }
            ],
        },
    )


def status(
    acct: SocialAccount,
    *,
    wamid: str,
    recipient: str,
    state: str,
    error_code: int | None = None,
    error_text: str | None = None,
) -> dict[str, Any]:
    """A delivery status for one of our messages (sent, delivered, read or failed)."""
    item: dict[str, Any] = {
        "id": wamid,
        "status": state,
        "timestamp": str(int(time.time())),
        "recipient_id": recipient,
    }
    if state == "failed":
        item["errors"] = [
            {
                "code": error_code or 131026,
                "title": error_text or "Message undeliverable",
                "message": error_text or "Message undeliverable",
                "error_data": {"details": error_text or "Message undeliverable"},
            }
        ]
    return _entry(
        acct,
        "messages",
        {"messaging_product": "whatsapp", "metadata": _metadata(acct), "statuses": [item]},
    )


def quality(acct: SocialAccount, *, event: str, tier: str | None) -> dict[str, Any]:
    """A ``phone_number_quality_update``: the number was flagged, recovered, or its tier changed.
    It names the WhatsApp Business Account, not the number's id."""
    value: dict[str, Any] = {"display_phone_number": _display_number(acct), "event": event}
    if tier:
        value["current_limit"] = tier
    return _entry(acct, "phone_number_quality_update", value)
