"""Email templates (T8.5, T8.7): every template renders a subject, accessible HTML and a text
part; user-supplied words are escaped; links are absolute into the workspace; the digest reads
its numbers, says "No data" rather than a made-up 0%, and carries the unsubscribe link."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pytest

from socialhood.models.notifications import EMAIL_TYPES, EmailTemplate
from socialhood.notify.templates import render
from socialhood.notify.templates.digest import DASH, duration, period_label

WEB = "https://app.socialhood.test"


def notification_data(**values: Any) -> dict[str, Any]:
    return {
        "title": "Reconnect @maple.bakery",
        "body": "@maple.bakery needs reconnecting to keep receiving messages.",
        "link": "/settings/connections",
        "workspace_name": "Maple Bakery",
        "workspace_slug": "maple",
        **values,
    }


def digest_stats(**values: Any) -> dict[str, Any]:
    return {
        "since": "2026-09-21",
        "until": "2026-09-27",
        "messages_received": 142,
        "conversations": 43,
        "conversations_replied": 38,
        "reply_rate": 88.4,
        "handled_by_ai": 24,
        "handled_by_ai_rate": 63.2,
        "first_responses": 52,
        "median_first_response_s": 754,
        "top_intents": [
            {"intent": "pricing", "count": 32},
            {"intent": "shipping", "count": 18},
            {"intent": "order_status", "count": 11},
        ],
        "comments_received": 64,
        "top_posts": [
            {
                "post_id": "0f5d7a52-5a8e-4c45-9e57-5d7c5c2b9b1e",
                "caption": "New autumn cakes are here! Order by Friday",
                "permalink": "https://www.instagram.com/p/abc/",
                "media_type": "IMAGE",
                "posted_at": "2026-09-23T10:00:00+00:00",
                "comments": 24,
            }
        ],
        "needs_you": 3,
        "open_questions": 4,
        "top_questions": [
            {"topic": "Do you ship to Dubai?", "asked": 5},
            {"topic": "Eggless options", "asked": 2},
        ],
        **values,
    }


def assert_accessible(html: str) -> None:
    assert html.startswith("<!doctype html>")
    assert '<html lang="en">' in html
    assert re.search(r"<title>[^<]+</title>", html)
    assert html.count("<h1") == 1
    assert "<img" not in html  # nothing depends on images loading
    assert 'role="presentation"' in html


@pytest.mark.parametrize("template", sorted(EMAIL_TYPES))
def test_every_notification_email_renders(template: str) -> None:
    email = render(template, notification_data(), web_base_url=WEB)
    assert email.subject == "Reconnect @maple.bakery"
    assert_accessible(email.html)
    assert "@maple.bakery needs reconnecting to keep receiving messages." in email.html
    assert f'href="{WEB}/w/maple/settings/connections"' in email.html
    assert f"{WEB}/w/maple/settings/notifications" in email.html
    assert "Maple Bakery" in email.html
    # The text part says the same, with the link written out.
    assert email.text.startswith("Social Hood\n")
    assert "@maple.bakery needs reconnecting to keep receiving messages." in email.text
    assert f"{WEB}/w/maple/settings/connections" in email.text


def test_the_button_says_what_it_does() -> None:
    reconnect = render("account_needs_reconnect", notification_data(), web_base_url=WEB)
    assert ">Reconnect the account</a>" in reconnect.html
    failed = render(
        "post_failed",
        notification_data(
            title="Post didn't publish",
            body='"New autumn cakes" didn\'t publish. @maple.bakery: the image is too large',
            link="/schedule/9b0c",
        ),
        web_base_url=WEB,
    )
    assert ">Open the post</a>" in failed.html
    assert f'href="{WEB}/w/maple/schedule/9b0c"' in failed.html
    assert "Open the post: https://app.socialhood.test/w/maple/schedule/9b0c" in failed.text


def test_a_notification_without_a_link_uses_the_templates_page() -> None:
    email = render("payment_problem", notification_data(link=None), web_base_url=WEB)
    assert f'href="{WEB}/w/maple/settings/billing"' in email.html


def test_words_from_customers_and_members_are_escaped() -> None:
    email = render(
        "account_needs_reconnect",
        notification_data(
            title='Reconnect <script>alert("x")</script>',
            body='<img src=x onerror="steal()"> & more',
            workspace_name="<b>Maple</b>",
        ),
        web_base_url=WEB,
    )
    assert "<script>" not in email.html
    assert "<img" not in email.html
    assert "&lt;script&gt;" in email.html
    assert "&lt;img src=x onerror=&quot;steal()&quot;&gt; &amp; more" in email.html
    assert "&lt;b&gt;Maple&lt;/b&gt;" in email.html


def test_the_digest_reads_the_weeks_numbers() -> None:
    data = {
        "workspace_name": "Maple Bakery",
        "workspace_slug": "maple",
        "stats": digest_stats(),
        "unsubscribe_url": f"{WEB}/unsubscribe?token=abc123",
    }
    email = render(EmailTemplate.WEEKLY_DIGEST, data, web_base_url=WEB)
    assert email.subject == f"Your week at Maple Bakery: 21{DASH}27 Sep"
    assert_accessible(email.html)
    for expected in (
        "142",
        "88%",
        "Replied in 38 of 43 conversations",
        "13 min",
        "63%",
        "24 of 38 replied conversations",
        "3 conversations",
        "Prices",
        "32 messages",
        "Shipping",
        "Order status",
        "Do you ship to Dubai?",
        "Asked 5 times",
        "New autumn cakes are here! Order by Friday",
        "24 comments",
    ):
        assert expected in email.html, expected
        assert expected in email.text, expected
    assert f'href="{WEB}/unsubscribe?token=abc123"' in email.html
    assert f"Unsubscribe: {WEB}/unsubscribe?token=abc123" in email.text
    assert f"{WEB}/w/maple/comments/0f5d7a52-5a8e-4c45-9e57-5d7c5c2b9b1e" in email.text
    assert '<th scope="row"' in email.html


def test_a_quiet_week_says_no_data_instead_of_zero_percent() -> None:
    stats = digest_stats(
        messages_received=0,
        conversations=0,
        conversations_replied=0,
        reply_rate=None,
        handled_by_ai=0,
        handled_by_ai_rate=None,
        first_responses=0,
        median_first_response_s=None,
        top_intents=[],
        top_posts=[],
        top_questions=[],
        needs_you=2,
    )
    data = {"workspace_name": "Maple Bakery", "workspace_slug": "maple", "stats": stats}
    email = render("weekly_digest", data, web_base_url=WEB)
    assert f"No messages came in 21{DASH}27 Sep." in email.text
    assert "Reply rate: No data" in email.text
    assert "Median first response: No data" in email.text
    assert "0%" not in email.text
    assert "Questions the AI couldn't answer" not in email.html
    assert "2 conversations" in email.text


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (None, "No data"),
        (0, "0 s"),
        (45, "45 s"),
        (90, "2 min"),
        (754, "13 min"),
        (3600, "1 h"),
        (12_000, "3 h 20 min"),
        (86_400, "1 d"),
        (187_200, "2 d 4 h"),
    ],
)
def test_durations_read_naturally(seconds: int | None, text: str) -> None:
    assert duration(seconds) == text


@pytest.mark.parametrize(
    ("since", "until", "label"),
    [
        (date(2026, 9, 21), date(2026, 9, 27), f"21{DASH}27 Sep"),
        (date(2026, 9, 28), date(2026, 10, 4), f"28 Sep {DASH} 4 Oct"),
        (date(2025, 12, 29), date(2026, 1, 4), f"29 Dec 2025 {DASH} 4 Jan 2026"),
    ],
)
def test_periods_are_labelled_by_their_days(since: date, until: date, label: str) -> None:
    assert period_label(since, until) == label


def test_an_unknown_template_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown email template"):
        render("sms_blast", notification_data(), web_base_url=WEB)
