"""T4.2: the matching engine (FR-AUT-05, FR-AUT-06, FR-AUT-15) and personal fields (FR-AUT-13)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from socialhood.services.automations.matching import (
    Candidate,
    first_match,
    keyword_matches,
    matches,
    normalize,
    overlaps,
)
from socialhood.services.automations.render import (
    first_name_of,
    render,
    utf8_bytes,
    with_disclosure,
)

T0 = datetime(2026, 9, 1, tzinfo=UTC)


def candidate(
    *keywords: str,
    mode: str = "word",
    trigger: str = "dm_keyword",
    priority: int = 100,
    age_days: int = 0,
) -> Candidate:
    return Candidate(
        id=uuid.uuid4(),
        trigger=trigger,  # type: ignore[arg-type]
        match_mode=mode,  # type: ignore[arg-type]
        keywords=tuple(normalize(k) for k in keywords),
        priority=priority,
        created_at=T0 - timedelta(days=age_days),
    )


def test_normalisation() -> None:
    assert normalize("  What's   the\tPRICE?\n") == "what's the price?"
    assert normalize("Ｐｒｉｃｅ") == "price"  # noqa: RUF001 - full-width letters (NFKC)
    assert normalize("STRASSE") == normalize("straße")  # case folding, not lower()


@pytest.mark.parametrize(
    ("text", "keyword", "mode", "expected"),
    [
        # the spec's own examples
        ("What's the PRICE?", "price", "word", True),
        ("priceless", "price", "word", False),
        ("price!", "price", "word", True),
        ("PRICE", "price", "exact", True),
        ("  price?! ", "price", "exact", True),
        ("the price", "price", "exact", False),
        ("priceless", "price", "contains", True),
        # v1 checked whether the message was inside the keyword; never again
        ("price", "price list", "word", False),
        ("price", "price list", "contains", False),
        ("send the price list please", "price list", "word", True),
        # Hindi: matras are part of the word, so a keyword never matches inside a longer word
        ("इसकी कीमत क्या है?", "कीमत", "word", True),
        ("कीमतें बताओ", "कीमत", "word", False),
        # Hinglish
        ("bhai price kya hai", "price", "word", True),
        ("Kitne ka hai ye?", "kitne", "word", True),
        # emoji keywords and emoji around words
        ("🔥🔥 love it", "🔥", "word", True),
        ("link🔗", "link", "word", True),
        ("#giveaway entry", "#giveaway", "word", True),
        ("LINK", "link", "exact", True),
        ("🔥", "🔥", "exact", True),
        ("", "price", "contains", False),
    ],
)
def test_keyword_matching(text: str, keyword: str, mode: str, expected: bool) -> None:
    assert keyword_matches(normalize(text), normalize(keyword), mode) is expected  # type: ignore[arg-type]


def test_the_lowest_priority_number_wins_then_the_oldest() -> None:
    newer = candidate("price", priority=10, age_days=1)
    older = candidate("price", priority=10, age_days=5)
    first = candidate("price", priority=1)
    assert first_match("price?", [newer, older, first]) == first_match("price?", [first])
    assert [m.automation_id for m in matches("price?", [newer, older])] == [older.id, newer.id]


def test_keyword_automations_run_before_any_comment_ones() -> None:
    anything = candidate(trigger="comment_any", priority=1)
    keyword = candidate("link", trigger="comment_keyword", priority=50)
    assert [m.automation_id for m in matches("LINK please", [anything, keyword])] == [
        keyword.id,
        anything.id,
    ]
    only_any = first_match("nice post", [anything, keyword])
    assert only_any is not None
    assert (only_any.automation_id, only_any.keyword) == (anything.id, "")


def test_no_match_returns_none() -> None:
    assert first_match("hello", [candidate("price")]) is None
    assert first_match("hello", []) is None


def test_overlaps_name_which_runs_first() -> None:
    this = candidate("price", "Link", priority=5)
    other = candidate("LINK", "shipping", priority=1)
    different_trigger = candidate("link", trigger="comment_keyword", priority=1)
    [found] = overlaps(this, [other, different_trigger])
    assert (found.keyword, found.other_id, found.this_runs_first) == ("link", other.id, False)


@pytest.mark.parametrize(
    ("text", "first", "user", "expected"),
    [
        ("Hi {first_name}! Here's the link", "Priya", "priya.s", "Hi Priya! Here's the link"),
        ("Hi {first_name}!", None, "priya.s", "Hi there!"),
        ("Hi {first_name|friend}!", None, None, "Hi friend!"),
        ("Thanks @{username}", None, "priya.s", "Thanks @priya.s"),
        ("Thanks {username}", None, None, "Thanks "),
        ("{nothing} stays", "Priya", None, "{nothing} stays"),
    ],
)
def test_personal_fields_never_leak(
    text: str, first: str | None, user: str | None, expected: str
) -> None:
    assert render(text, first_name=first, username=user) == expected


def test_first_names_and_the_disclosure_line() -> None:
    assert first_name_of("Priya Shah") == "Priya"
    assert first_name_of("  ") is None
    assert first_name_of(None) is None
    sent = with_disclosure("Here you go", "Sent automatically")
    assert sent == "Here you go\n\nSent automatically"
    assert utf8_bytes(sent) == len(sent)  # ASCII
    assert utf8_bytes("कीमत") == 12  # Devanagari is 3 bytes per code point
