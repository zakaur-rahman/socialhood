"""The output filter (TR-AI-07 check 13, FR-SUG-03). Pure: no database, no clock.

A drafted reply may only mention a URL, an email address or a phone number that appears in the
texts it is allowed to quote from: knowledge and brand settings (and, for a suggestion a person
reviews, the conversation). Anything else is treated as an invented fact.

Matching is forgiving about form, not content: URLs ignore case, the scheme, ``www.`` and a
trailing slash, and a bare domain matches a deeper link on it; emails ignore case; phone numbers
compare their last 10 digits, so "+91 98765 43210" matches "9876543210". Dates are not phone
numbers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

MAX_REPLY_CHARS = 1000  # TR-AI-07 check 13

FindingKind = Literal["link", "email address", "phone number", "length"]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
_TLDS = "com|in|net|org|io|co|shop|store|app|me|ly|gl|link|site|online|info|biz|us|uk|ae|example"
URL = re.compile(
    r"(?i)(?:\bhttps?://|\bwww\.)[^\s<>\"'\]]+"
    rf"|\b(?:[a-z0-9-]+\.)+(?:{_TLDS})\b(?:/[^\s<>\"'\]]*)?"
)
PHONE = re.compile(r"(?<![\w+])\+?\d[\d ().-]{5,}\d(?!\w)")
DATE = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$|^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$")
_SCHEME = re.compile(r"(?i)\bhttps?://")
_WWW = re.compile(r"(?i)(?<![\w.-])www\.")
_TRAILING = ".,;:!?)"
PHONE_KEY_DIGITS = 10
MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15


@dataclass(frozen=True)
class Finding:
    """Why a reply was blocked: what it mentioned that its sources do not."""

    kind: FindingKind
    value: str

    def describe(self) -> str:
        if self.kind == "length":
            return f"a reply longer than {MAX_REPLY_CHARS:,} characters"
        return f"the {self.kind} {self.value}"


def _url_key(value: str) -> str:
    key = _SCHEME.sub("", value.strip().rstrip(_TRAILING)).casefold()
    key = key.removeprefix("www.")
    return key.rstrip("/")


def _normalized_source(text: str) -> str:
    return _WWW.sub("", _SCHEME.sub("", text)).casefold()


def _phone_key(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if not MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS:
        return None
    if DATE.match(value.strip()):
        return None
    return digits[-PHONE_KEY_DIGITS:]


def emails(text: str) -> list[str]:
    return [m.group(0).rstrip(_TRAILING) for m in EMAIL.finditer(text)]


def urls(text: str) -> list[str]:
    """Links in ``text``; email addresses are not links."""
    without_emails = EMAIL.sub(" ", text)
    found = []
    for match in URL.finditer(without_emails):
        value = match.group(0).rstrip(_TRAILING)
        if value:
            found.append(value)
    return found


def phones(text: str) -> list[str]:
    """Phone-like numbers (7 to 15 digits, not a date) in ``text``."""
    without = URL.sub(" ", EMAIL.sub(" ", text))
    return [m.group(0) for m in PHONE.finditer(without) if _phone_key(m.group(0)) is not None]


def candidates(text: str) -> list[tuple[FindingKind, str]]:
    """Every link, email address and phone number in ``text``, in that order."""
    found: list[tuple[FindingKind, str]] = [("link", u) for u in urls(text)]
    found += [("email address", e) for e in emails(text)]
    found += [("phone number", p) for p in phones(text)]
    return found


def _url_allowed(value: str, sources: Sequence[str]) -> bool:
    key = _url_key(value)
    if not key:
        return True
    pattern = re.compile(rf"(?<![\w-]){re.escape(key)}(?![\w-])")
    return any(pattern.search(source) for source in sources)


def _email_allowed(value: str, sources: Sequence[str]) -> bool:
    pattern = re.compile(rf"(?<![\w.+-]){re.escape(value.casefold())}(?![\w-])")
    return any(pattern.search(source) for source in sources)


def phone_keys(texts: Iterable[str]) -> set[str]:
    keys = set()
    for text in texts:
        for value in phones(text):
            key = _phone_key(value)
            if key is not None:
                keys.add(key)
    return keys


def check(
    reply: str, allowed: Sequence[str], *, max_chars: int | None = MAX_REPLY_CHARS
) -> Finding | None:
    """The first thing in ``reply`` its sources do not support, or None when it may be sent.
    ``max_chars`` None skips the length rule (a suggestion is trimmed to its platform's limit)."""
    if max_chars is not None and len(reply) > max_chars:
        return Finding("length", str(len(reply)))
    sources = [_normalized_source(text) for text in allowed if text]
    allowed_phones: set[str] | None = None
    for kind, value in candidates(reply):
        if kind == "link" and not _url_allowed(value, sources):
            return Finding(kind, value)
        if kind == "email address" and not _email_allowed(value, sources):
            return Finding(kind, value)
        if kind == "phone number":
            if allowed_phones is None:
                allowed_phones = phone_keys(allowed)
            if _phone_key(value) not in allowed_phones:
                return Finding(kind, value)
    return None
