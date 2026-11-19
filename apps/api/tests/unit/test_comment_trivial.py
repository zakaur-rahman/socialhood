"""YT4: comments read by rules instead of the AI (services/comments/trivial)."""

import pytest

from socialhood.services.comments.trivial import reading


@pytest.mark.parametrize(
    ("text", "intent", "sentiment"),
    [
        ("nice", "feedback", "positive"),
        ("Niceee 🔥🔥", "feedback", "positive"),
        ("goooood video bro", "feedback", "positive"),
        ("bahut badhiya 👏", "feedback", "positive"),
        ("Thank you so much sir 🙏🏽", "feedback", "positive"),
        ("❤️❤️", "greeting", "positive"),
        ("first!!! 🔥", "greeting", "positive"),
        ("hi", "greeting", "neutral"),
        ("@amy @raj", "other", "neutral"),
    ],
)
def test_trivial_comments_need_no_ai(text: str, intent: str, sentiment: str) -> None:
    found = reading(text)
    assert found is not None
    assert (found.intent, found.sentiment) == (intent, sentiment)


@pytest.mark.parametrize(
    "text",
    [
        "nice, how much?",  # a question
        "not good",  # a word off the lists
        "this is it",  # joining words only
        "😡",  # a negative emoji
        "nice 🙄",  # an unclear emoji
        "www.example.com nice",  # a link
        "love you 3000",  # a digit
        "check my profile",
        "great " * 7,  # too many words
        "",
        None,
    ],
)
def test_anything_else_goes_to_the_ai(text: str | None) -> None:
    assert reading(text) is None
