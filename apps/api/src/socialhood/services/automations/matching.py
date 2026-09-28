"""The matching engine (T4.2; FR-AUT-05, FR-AUT-06, FR-AUT-15). Pure: no database, no clock.

Text and keywords are normalised the same way (Unicode NFKC, case-folded, whitespace collapsed).
Whole word: the keyword appears with a non-word character (or the text's edge) on each side, where
letters, combining marks and digits of any script count as word characters, so "price" matches
"What's the PRICE?" but not "priceless", and a Hindi keyword does not match inside a longer word.
Exact: the whole message equals a keyword, ignoring punctuation and spaces around it. Contains: a
plain substring.

Candidates are tried in runtime order: keyword automations before any-comment ones, then the
lowest priority number, then the oldest. The first automation with a matching keyword wins; the
runtime then applies cooldowns, post scopes and run windows, which are not this module's concern.
"""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

MatchModeName = Literal["word", "exact", "contains"]
TriggerName = Literal["dm_keyword", "comment_keyword", "comment_any"]

_WORD_CATEGORIES = ("L", "M", "N")


def normalize(text: str) -> str:
    """NFKC, case-folded, whitespace collapsed to single spaces, trimmed."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(folded.split())


def _is_word_char(char: str) -> bool:
    return char == "_" or unicodedata.category(char)[0] in _WORD_CATEGORIES


def _strip_edges(text: str) -> str:
    """Drop punctuation, symbols and spaces around a message, for exact matching."""
    start, end = 0, len(text)
    while start < end and not _is_word_char(text[start]) and not _is_emoji(text[start]):
        start += 1
    while end > start and not _is_word_char(text[end - 1]) and not _is_emoji(text[end - 1]):
        end -= 1
    return text[start:end]


def _is_emoji(char: str) -> bool:
    # Symbols such as emoji carry meaning in a message ("🔥"); punctuation does not.
    return unicodedata.category(char) == "So"


def keyword_matches(text: str, keyword: str, mode: MatchModeName) -> bool:
    """Both arguments already normalised."""
    if not keyword:
        return False
    if mode == "contains":
        return keyword in text
    if mode == "exact":
        return _strip_edges(text) == _strip_edges(keyword) != ""
    start = text.find(keyword)
    while start != -1:
        end = start + len(keyword)
        before_ok = (
            start == 0 or not _is_word_char(text[start - 1]) or not _is_word_char(keyword[0])
        )
        after_ok = (
            end == len(text) or not _is_word_char(text[end]) or not _is_word_char(keyword[-1])
        )
        if before_ok and after_ok:
            return True
        start = text.find(keyword, start + 1)
    return False


@dataclass(frozen=True)
class Candidate:
    """One active automation of the account that received the event."""

    id: uuid.UUID
    trigger: TriggerName
    match_mode: MatchModeName
    keywords: tuple[str, ...]  # normalised
    priority: int
    created_at: datetime


@dataclass(frozen=True)
class Match:
    automation_id: uuid.UUID
    keyword: str  # the normalised keyword that matched; "" for any-comment triggers


def runtime_order(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Keyword automations first, then priority (lower wins), then the oldest (FR-AUT-15)."""
    return sorted(
        candidates,
        key=lambda c: (c.trigger == "comment_any", c.priority, c.created_at, str(c.id)),
    )


def matching_keyword(text: str, candidate: Candidate) -> str | None:
    """The first of the candidate's keywords the (normalised) text matches, or None; "" for an
    any-comment automation, which matches every comment."""
    if candidate.trigger == "comment_any":
        return ""
    for keyword in candidate.keywords:
        if keyword_matches(text, keyword, candidate.match_mode):
            return keyword
    return None


def matches(text: str, candidates: Sequence[Candidate]) -> list[Match]:
    """Every automation the text matches, in runtime order. The runtime acts on the first one
    that passes its checks (cooldown, post scope, run window, already ran)."""
    normalised = normalize(text)
    found: list[Match] = []
    for candidate in runtime_order(candidates):
        keyword = matching_keyword(normalised, candidate)
        if keyword is not None:
            found.append(Match(candidate.id, keyword))
    return found


def first_match(text: str, candidates: Sequence[Candidate]) -> Match | None:
    found = matches(text, candidates)
    return found[0] if found else None


@dataclass(frozen=True)
class Overlap:
    keyword: str
    other_id: uuid.UUID
    this_runs_first: bool


def overlaps(this: Candidate, others: Sequence[Candidate]) -> list[Overlap]:
    """FR-AUT-15: keywords this automation shares (after normalisation) with other active
    automations of the same account and trigger type, and which one runs first."""
    mine = set(this.keywords)
    order = runtime_order([this, *others])
    rank = {c.id: i for i, c in enumerate(order)}
    found: list[Overlap] = []
    for other in others:
        if other.id == this.id or other.trigger != this.trigger:
            continue
        for keyword in sorted(mine & set(other.keywords)):
            found.append(Overlap(keyword, other.id, rank[this.id] < rank[other.id]))
    return found
