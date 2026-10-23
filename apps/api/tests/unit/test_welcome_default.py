"""GR-12: which messages the welcome and default reply may answer, and where they sit in the
runtime order (pure: no database)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest

from socialhood.models.inbox import Message
from socialhood.services.automations import runtime
from socialhood.services.automations.matching import Candidate, matches, normalize, runtime_order

T0 = datetime(2026, 9, 1, tzinfo=UTC)
FALLBACKS = ("dm_keyword", "first_message", "default_reply")


def message(
    kind: str = "text", postback: str | None = None, quick_reply: str | None = None
) -> Message:
    return cast(
        Message,
        SimpleNamespace(
            kind=kind,
            text="hi",
            attachments=[],
            postback_payload=postback,
            quick_reply_payload=quick_reply,
        ),
    )


def candidate(*keywords: str, trigger: str = "dm_keyword", priority: int = 100) -> Candidate:
    return Candidate(
        id=uuid.uuid4(),
        trigger=trigger,  # type: ignore[arg-type]
        match_mode="word",
        keywords=tuple(normalize(k) for k in keywords),
        priority=priority,
        created_at=T0 - timedelta(days=1),
    )


@pytest.mark.parametrize("kind", ["text", "image", "audio", "share", "sticker"])
def test_an_ordinary_dm_can_start_the_fallbacks(kind: str) -> None:
    assert runtime.dm_triggers(message(kind)) == FALLBACKS


@pytest.mark.parametrize(
    "msg",
    [
        message("story_reply"),
        message("story_mention"),
        message(postback="ICE_BREAKER_1"),  # an ice breaker or button tap
        message(quick_reply="OPENING"),  # a quick reply tap
    ],
    ids=["story_reply", "story_mention", "postback", "quick_reply"],
)
def test_taps_and_stories_never_start_the_fallbacks(msg: Message) -> None:
    assert not set(runtime.dm_triggers(msg)) & {"first_message", "default_reply"}


def test_the_fallbacks_run_after_every_other_automation() -> None:
    welcome = candidate(trigger="first_message", priority=1)
    default = candidate(trigger="default_reply", priority=1)
    anything = candidate(trigger="story_reply", priority=90)
    keyword = candidate("price", priority=99)
    order = runtime_order([default, welcome, anything, keyword])
    assert [c.id for c in order] == [keyword.id, anything.id, welcome.id, default.id]


def test_a_welcome_and_a_default_reply_match_any_text() -> None:
    welcome = candidate(trigger="first_message")
    default = candidate(trigger="default_reply")
    found = matches("anything at all", [default, welcome])
    assert [(m.automation_id, m.keyword) for m in found] == [(welcome.id, ""), (default.id, "")]
