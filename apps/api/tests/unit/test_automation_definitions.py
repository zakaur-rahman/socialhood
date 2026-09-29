"""T4.3, T4.7: activation rules (FR-AUT-02, 13, 14, 17), templates (FR-AUT-12), display status,
figures helpers. Pure: no database."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from socialhood.models.automations import Automation
from socialhood.services.automations import stats, templates, windows
from socialhood.services.automations.definitions import copy_name
from socialhood.services.automations.validation import (
    AccountInfo,
    ButtonInfo,
    Definition,
    PostTarget,
    activation_errors,
    is_https_url,
    message_bytes,
    missing_fields,
)

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
ACCOUNT = uuid.uuid4()
INSTAGRAM = AccountInfo(platform="instagram", status="active")

COMPLETE = Definition(
    social_account_id=ACCOUNT,
    account=INSTAGRAM,
    trigger="comment_keyword",
    keywords=["link"],
    post_scope="all",
    posts=[],
    action="send_message",
    message_text="Hi {first_name|there}! Here's the link.",
    message_buttons=[ButtonInfo("Open link", "https://maple.example/shop")],
    public_reply_texts=["Sent you a DM!"],
    starts_at=None,
    ends_at=None,
)


def fields(d: Definition, disclosure: str | None = None) -> list[str]:
    return missing_fields(activation_errors(d, disclosure=disclosure, now=NOW))


def test_a_complete_definition_activates() -> None:
    assert fields(COMPLETE) == []


def test_an_empty_draft_lists_account_trigger_and_action_together() -> None:
    empty = replace(
        COMPLETE,
        social_account_id=None,
        account=None,
        trigger=None,
        keywords=[],
        action=None,
        message_text=None,
        message_buttons=[],
        public_reply_texts=[],
    )
    assert fields(empty) == ["social_account_id", "trigger", "action"]


def test_every_invalid_field_is_listed_at_once() -> None:
    broken = replace(
        COMPLETE,
        trigger="comment_any",
        keywords=[],
        post_scope="all",
        message_text="   ",
        message_buttons=[ButtonInfo("Shop", "http://maple.example"), ButtonInfo("x" * 21, "ok")],
        public_reply_texts=["fine", "", "y" * 301],
        starts_at=NOW + timedelta(days=2),
        ends_at=NOW + timedelta(days=1),
    )
    assert fields(broken) == [
        "post_scope",
        "message_text",
        "message_buttons.0.url",
        "message_buttons.1.title",
        "message_buttons.1.url",
        "public_reply_texts.1",
        "public_reply_texts.2",
        "ends_at",
    ]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"keywords": []}, ["keywords"]),
        ({"trigger": "dm_keyword", "keywords": []}, ["keywords"]),
        ({"trigger": "comment_any", "keywords": []}, ["post_scope"]),
        ({"trigger": "comment_any", "keywords": [], "post_scope": "next_post"}, []),
        ({"post_scope": "selected"}, ["media_item_ids"]),
        (
            {"post_scope": "selected", "posts": [PostTarget(uuid.uuid4(), None, uuid.uuid4())]},
            ["media_item_ids"],
        ),
        ({"post_scope": "selected", "posts": [PostTarget(uuid.uuid4(), None, ACCOUNT)]}, []),
        ({"post_scope": "selected", "posts": [PostTarget(None, uuid.uuid4(), None)]}, []),
        ({"account": AccountInfo("whatsapp", "active")}, ["social_account_id"]),
        ({"account": AccountInfo("instagram", "disconnected")}, ["social_account_id"]),
        ({"account": AccountInfo("instagram", "needs_reconnect")}, []),
        ({"action": "ai_reply"}, ["action"]),
        ({"message_text": None}, ["message_text"]),
        ({"ends_at": NOW - timedelta(minutes=1)}, ["ends_at"]),
        ({"starts_at": NOW + timedelta(days=1), "ends_at": NOW + timedelta(days=3)}, []),
        # DM triggers have no posts or public replies to check.
        ({"trigger": "dm_keyword", "public_reply_texts": ["z" * 400]}, []),
        # With buttons the text is a button template: 640 characters at most.
        ({"message_text": "a" * 641}, ["message_text"]),
        ({"message_text": "a" * 641, "message_buttons": []}, []),
        # A private reply carries no image; a DM automation's message can.
        ({"has_image": True}, ["message_media_asset_id"]),
        ({"has_image": True, "trigger": "dm_keyword"}, []),
        # Public reply only needs a public reply.
        ({"surge_order": "public_only", "public_reply_texts": []}, ["public_reply_texts"]),
        ({"surge_order": "public_only"}, []),
    ],
)
def test_activation_rules(change: dict[str, Any], expected: list[str]) -> None:
    assert fields(replace(COMPLETE, **change)) == expected


def test_ai_replies_wait_for_the_knowledge_base() -> None:
    errors = activation_errors(replace(COMPLETE, action="ai_reply"), disclosure=None, now=NOW)
    assert [(e.field, e.message) for e in errors] == [
        ("action", "AI replies arrive with the knowledge base. Send a message for now.")
    ]


def test_the_byte_limit_counts_the_longest_name_and_the_disclosure_line() -> None:
    # 940 bytes of text plus {first_name} (30 bytes at its longest) fits; the disclosure doesn't.
    plain = replace(COMPLETE, message_buttons=[])  # buttons have their own 640-character limit
    text = "a" * 940 + "{first_name}"
    assert message_bytes(text, None) == 970
    assert fields(replace(plain, message_text=text)) == []
    assert message_bytes(text, "Sent automatically") == 970 + 2 + 18
    assert fields(replace(plain, message_text=text), disclosure="x" * 40) == ["message_text"]
    # Devanagari is 3 bytes a character: 334 characters are over the limit.
    assert fields(replace(plain, message_text="क" * 334)) == ["message_text"]
    assert fields(replace(plain, message_text="क" * 333)) == []


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://maple.example/shop?x=1", True),
        ("https://shop.maple.example", True),
        ("http://maple.example", False),
        ("https://", False),
        ("https://localhost", False),
        ("maple.example", False),
        ("https://maple .example", False),
        ("javascript:alert(1)", False),
        ("", False),
    ],
)
def test_link_buttons_need_https_links(url: str, ok: bool) -> None:
    assert is_https_url(url) is ok


# ---------------------------------------------------------------- templates (FR-AUT-12)


def test_the_gallery_has_the_six_r1_templates() -> None:
    items = templates.gallery().items
    assert [(t.key, t.trigger, t.action, t.requires_paid_plan) for t in items] == [
        ("send_link", "comment_keyword", "send_message", False),
        ("giveaway", "comment_any", "send_message", False),
        ("price_on_request", "comment_keyword", "ai_reply", True),
        ("catalogue_by_dm", "dm_keyword", "send_message", False),
        ("answer_faqs", "dm_keyword", "ai_reply", True),
        ("book_a_call", "dm_keyword", "send_message", False),
    ]
    assert {t.category for t in items} == {"grow", "sell", "support"}


@pytest.mark.parametrize("template", templates.TEMPLATES, ids=lambda t: t.key)
def test_each_template_needs_only_what_the_user_must_supply(
    template: templates.Template,
) -> None:
    """A template fills everything except the account, the link and the chosen post."""
    definition = Definition(
        social_account_id=ACCOUNT,
        account=INSTAGRAM,
        trigger=template.trigger,
        keywords=list(template.keywords),
        post_scope=template.post_scope,
        posts=[],
        action=template.action,
        message_text=template.message_text,
        message_buttons=[ButtonInfo(b.title, b.url) for b in template.message_buttons],
        public_reply_texts=list(template.public_reply_texts),
        starts_at=None,
        ends_at=None,
    )
    expected = [f"message_buttons.{i}.url" for i in range(len(template.message_buttons))]
    if template.post_scope == "selected":
        expected.insert(0, "media_item_ids")
    if template.action == "ai_reply":
        expected.append("action")
    assert sorted(fields(definition)) == sorted(expected)


# ---------------------------------------------------------------- run windows (FR-AUT-17)


def automation(**values: Any) -> Automation:
    base = {"status": "active", "starts_at": None, "ends_at": None}
    return cast(Automation, SimpleNamespace(**{**base, **values}))


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"status": "draft"}, "draft"),
        ({"status": "draft", "ends_at": NOW - timedelta(days=1)}, "draft"),
        ({}, "active"),
        ({"starts_at": NOW + timedelta(hours=1)}, "scheduled"),
        ({"starts_at": NOW - timedelta(hours=1), "ends_at": NOW + timedelta(hours=1)}, "active"),
        ({"ends_at": NOW}, "ended"),
        ({"status": "paused", "ends_at": NOW - timedelta(hours=1)}, "ended"),
        ({"status": "paused"}, "paused"),
        ({"status": "paused", "starts_at": NOW + timedelta(hours=1)}, "paused"),
    ],
)
def test_display_status(values: dict[str, Any], expected: str) -> None:
    assert windows.display_status(automation(**values), NOW) == expected


def test_in_window() -> None:
    assert windows.in_window(automation(), NOW)
    assert not windows.in_window(automation(starts_at=NOW + timedelta(seconds=1)), NOW)
    assert windows.in_window(automation(starts_at=NOW), NOW)
    assert not windows.in_window(automation(ends_at=NOW), NOW)


# ---------------------------------------------------------------- helpers


def test_copy_names_stay_within_80_characters() -> None:
    assert copy_name("Send the link") == "Send the link (copy)"
    long = copy_name("x" * 80)
    assert len(long) == 80
    assert long.endswith(" (copy)")


def test_queue_eta_is_the_private_reply_rate() -> None:
    assert stats.eta_minutes(0) is None
    assert stats.eta_minutes(1) == 1
    assert stats.eta_minutes(730) == 60  # the bucket's rate, so no hour exceeds 750
    assert stats.eta_minutes(2140) == 176  # "about 3 h"


def test_periods_are_the_workspaces_calendar_days() -> None:
    late = datetime(2026, 9, 29, 20, 0, tzinfo=UTC)  # already 30 September in Kolkata
    p = stats.period("Asia/Kolkata", 7, late)
    assert p.days[0] == date(2026, 9, 24)
    assert p.days[-1] == date(2026, 9, 30)
    assert p.since == datetime(2026, 9, 23, 18, 30, tzinfo=UTC)
    assert stats.period("Not/A zone'", 7, late).timezone == "UTC"
