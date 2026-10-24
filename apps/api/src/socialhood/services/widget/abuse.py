"""Spam and abuse rules for what a visitor types in the widget (GR-28). Pure functions.

The widget is open to anyone who loads the page, so the rules are the cheap ones that stop the
usual noise before it costs an AI credit or fills the inbox: a length cap, no control characters,
at most ``MAX_LINKS`` links, no long runs of one character and no fourth identical message in a
row. The limits by IP and by visitor are in security/ratelimit.py; the daily cap on new chats is
by plan (billing/plans.py ``widget_conversations_daily``). A message that fails here is refused
with a sentence the widget shows; nothing is stored.
"""

from __future__ import annotations

import re

MAX_MESSAGE_CHARS = 1000
MAX_LINKS = 2
MAX_REPEAT_RUN = 30
MAX_IDENTICAL_IN_A_ROW = 3

_LINK = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RUN = re.compile(r"(.)\1{" + str(MAX_REPEAT_RUN) + r",}", re.DOTALL)


def clean_text(text: str) -> str:
    """The message as stored: line endings made plain and the ends trimmed."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def check_message(text: str, recent_texts: list[str]) -> str | None:
    """The reason to refuse ``text`` (a sentence for the visitor), or None when it is fine.
    ``recent_texts`` are the visitor's latest messages, newest first."""
    if not text:
        return "Write a message first."
    if len(text) > MAX_MESSAGE_CHARS:
        return f"Messages can be up to {MAX_MESSAGE_CHARS:,} characters."
    if _CONTROL.search(text):
        return "That message has characters we can't send."
    if len(_LINK.findall(text)) > MAX_LINKS:
        return "That message has too many links."
    if _RUN.search(text):
        return "That message looks like a mistake. Try writing it again."
    same = 0
    for earlier in recent_texts[:MAX_IDENTICAL_IN_A_ROW]:
        if earlier.strip().lower() != text.strip().lower():
            break
        same += 1
    if same >= MAX_IDENTICAL_IN_A_ROW:
        return "You already sent that. We'll reply as soon as we can."
    return None
