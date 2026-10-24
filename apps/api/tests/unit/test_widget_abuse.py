"""GR-28: the cheap spam rules on what a visitor types in the widget."""

from __future__ import annotations

from socialhood.services.widget import abuse


def check(text: str, recent: list[str] | None = None) -> str | None:
    return abuse.check_message(abuse.clean_text(text), recent or [])


def test_an_ordinary_message_passes() -> None:
    assert check("Hi, do you ship to Pune? https://example.com/page") is None


def test_empty_and_long_messages_are_refused() -> None:
    assert check("   \n ") == "Write a message first."
    assert check("word " * 300) == "Messages can be up to 1,000 characters."
    assert check("word " * 190) is None


def test_control_characters_are_refused() -> None:
    assert check("hello\x00world") is not None
    assert check("line one\nline two\ttabbed") is None  # newlines and tabs are fine


def test_too_many_links_are_refused() -> None:
    assert check("see http://a.co and www.b.co") is None
    assert check("http://a.co http://b.co http://c.co") == "That message has too many links."


def test_a_long_run_of_one_character_is_refused() -> None:
    assert check("a" * 31) is not None
    assert check("wow" + "!" * 10) is None


def test_a_fourth_identical_message_in_a_row_is_refused() -> None:
    assert check("Buy now", ["buy now", "Buy now"]) is None
    assert check("Buy now", ["buy now ", "BUY NOW", "Buy now"]) is not None
    assert check("Buy now", ["buy now", "something else", "buy now"]) is None


def test_line_endings_are_made_plain() -> None:
    assert abuse.clean_text("  a\r\nb\rc  ") == "a\nb\nc"
