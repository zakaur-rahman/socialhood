"""A template's variables, mapped to what each person gets (GR-23). Pure.

A template body has positional placeholders, ``{{1}}``, ``{{2}}``... Each is mapped to either a
contact field (``first_name``, ``name``, ``username``, ``email``, ``phone`` or the key of a
custom field) with a fallback to write when the person has no value, or a fixed text. A field
with neither a value nor a fallback leaves that person out (skipped as "missing value") rather than
sending a message with a hole in it. ``first_name`` falls back to "there" when no fallback is
given, as everywhere else in the product.

WhatsApp does not accept a newline, a tab or four spaces in a row inside a template parameter, and
limits a parameter's length; both are cleaned here. *Unverified against Meta's current rules.*
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

BUILTIN_FIELDS = ("first_name", "name", "username", "email", "phone")
PLACEHOLDER = re.compile(r"\{\{\s*(\d+)\s*\}\}")
MAX_PARAM = 1024
_WHITESPACE_RUNS = re.compile(r"[\r\n\t]+| {4,}")
DEFAULT_FALLBACK = {"first_name": "there"}


def clean_param(text: str) -> str:
    """A value as a template parameter: line breaks and tabs become a space, long runs of spaces
    shrink, and the length is capped."""
    return _WHITESPACE_RUNS.sub(" ", text).strip()[:MAX_PARAM]


def resolve(
    variables: Sequence[Mapping[str, Any]], values: Mapping[str, str | None]
) -> list[str] | None:
    """The body parameters for one person, or None when a field has no value and no fallback."""
    params: list[str] = []
    for spec in variables:
        if spec.get("source") == "fixed":
            text = str(spec.get("value") or "")
        else:
            field = str(spec.get("field") or "")
            text = (values.get(field) or "").strip()
            if not text:
                fallback = spec.get("fallback")
                text = (
                    str(fallback) if fallback not in (None, "") else DEFAULT_FALLBACK.get(field, "")
                )
        text = clean_param(text)
        if not text:
            return None
        params.append(text)
    return params


def render_body(body: str, params: Sequence[str]) -> str:
    """The template's body with ``{{n}}`` replaced by the parameters (a missing one stays empty)."""

    def fill(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        return params[index] if 0 <= index < len(params) else ""

    return PLACEHOLDER.sub(fill, body)


def problems(
    variables: Sequence[Mapping[str, Any]], *, param_count: int, field_keys: set[str]
) -> list[tuple[int, str]]:
    """What is wrong with the mapping, as (variable number, plain sentence); empty when it fits the
    template. ``field_keys`` are the workspace's custom field keys."""
    found: list[tuple[int, str]] = []
    if len(variables) != param_count:
        found.append(
            (
                0,
                f"This template has {param_count} variable{'' if param_count == 1 else 's'}; "
                f"{len(variables)} {'was' if len(variables) == 1 else 'were'} filled in.",
            )
        )
        return found
    allowed = set(BUILTIN_FIELDS) | field_keys
    for number, spec in enumerate(variables, start=1):
        if spec.get("source") == "fixed":
            if not str(spec.get("value") or "").strip():
                found.append((number, f"Write the text for variable {number}."))
        elif str(spec.get("field") or "") not in allowed:
            found.append((number, f"Choose a contact field for variable {number}."))
    return found
