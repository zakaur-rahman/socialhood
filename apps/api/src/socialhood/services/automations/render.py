"""Personal fields in automation messages and public replies (FR-AUT-13, FR-AUT-14).

``{first_name}`` and ``{username}`` take the contact's values; each can name its own fallback as
``{first_name|there}``. Without one, ``{first_name}`` falls back to "there" and ``{username}`` to
"" (the literal field is never sent). The disclosure line (FR-AUT-11) is appended on its own line
and counts toward the platform's limit.
"""

from __future__ import annotations

import re

FIELD = re.compile(r"\{(first_name|username)(?:\|([^{}]{0,40}))?\}")
DEFAULT_FALLBACK = {"first_name": "there", "username": ""}
FIELDS = ("first_name", "username")


def first_name_of(display_name: str | None) -> str | None:
    """The first word of a display name, or None."""
    if not display_name:
        return None
    first = display_name.strip().split()
    return first[0] if first else None


def render(text: str, *, first_name: str | None, username: str | None) -> str:
    values = {"first_name": first_name, "username": username}

    def fill(match: re.Match[str]) -> str:
        field, fallback = match.group(1), match.group(2)
        value = values[field]
        if value:
            return value
        return fallback if fallback is not None else DEFAULT_FALLBACK[field]

    return FIELD.sub(fill, text)


def with_disclosure(text: str, disclosure: str | None) -> str:
    return f"{text}\n\n{disclosure}" if disclosure else text


def utf8_bytes(text: str) -> int:
    return len(text.encode())


SAMPLE = "x" * 30


def longest_render(text: str) -> str:
    """The text with each field at its longest, for the byte counter's worst case: a 30-character
    sample (Instagram usernames are at most 30 characters, and names are rarely longer), or the
    field's fallback when that is longer. The web counter (lib/automations/render.ts) agrees."""

    def fill(match: re.Match[str]) -> str:
        field, fallback = match.group(1), match.group(2)
        alternative = fallback if fallback is not None else DEFAULT_FALLBACK[field]
        return alternative if utf8_bytes(alternative) > len(SAMPLE) else SAMPLE

    return FIELD.sub(fill, text)
