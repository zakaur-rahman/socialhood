"""Message templates for sends outside the 24-hour window (FR-INB-10, TR-PL table).

Only approved templates whose variables are all in the body are offered: the template picker asks
for body variables only, and the adapter sends them as positional body parameters. Templates that
need a media header, header or button variables, or named parameters would fail at send time, so
they are left out until the picker supports them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CATEGORIES = frozenset({"marketing", "utility", "authentication"})
PLACEHOLDER = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")
PLAIN_BUTTONS = frozenset({"QUICK_REPLY", "PHONE_NUMBER", "URL"})


@dataclass(frozen=True)
class MessageTemplate:
    name: str
    language: str
    category: str  # marketing, utility or authentication
    status: str  # approved
    body: str  # with {{1}}-style placeholders
    param_count: int


def _placeholders(text: str) -> list[str]:
    return PLACEHOLDER.findall(text or "")


def _positional_count(body: str) -> int | None:
    """The number of body parameters to send, or None when the body uses named ones."""
    names = _placeholders(body)
    if not all(name.isdigit() for name in names):
        return None
    return max((int(name) for name in names), default=0)


def _fixed(component: dict[str, Any]) -> bool:
    """Whether a non-body component needs no parameters at send time."""
    kind = str(component.get("type", "")).upper()
    if kind == "FOOTER":
        return True
    if kind == "HEADER":
        return str(component.get("format", "TEXT")).upper() == "TEXT" and not _placeholders(
            str(component.get("text", ""))
        )
    if kind == "BUTTONS":
        return all(
            isinstance(button, dict)
            and str(button.get("type", "")).upper() in PLAIN_BUTTONS
            and not _placeholders(str(button.get("url", "")))
            for button in component.get("buttons") or []
        )
    return False


def parse_template(item: Any) -> MessageTemplate | None:
    """One entry of GET /{waba_id}/message_templates, or None when it can't be offered."""
    if not isinstance(item, dict) or str(item.get("status", "")).upper() != "APPROVED":
        return None
    category = str(item.get("category", "")).lower()
    if category not in CATEGORIES or not item.get("name") or not item.get("language"):
        return None
    body: str | None = None
    for component in item.get("components") or []:
        if not isinstance(component, dict):
            return None
        if str(component.get("type", "")).upper() == "BODY":
            body = str(component.get("text", ""))
        elif not _fixed(component):
            return None
    if body is None:
        return None
    count = _positional_count(body)
    if count is None:
        return None
    return MessageTemplate(
        name=str(item["name"]),
        language=str(item["language"]),
        category=category,
        status="approved",
        body=body,
        param_count=count,
    )
