"""GR-10: which comments a comment automation listens to (pure: no database), and the Activity
sentence for a Live that ended."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from socialhood.services.activity import reasons
from socialhood.services.automations import actions, runtime
from socialhood.services.automations.validation import Definition, activation_errors


def automation(surface: str) -> Any:
    return SimpleNamespace(comment_surface=surface)


@pytest.mark.parametrize(
    ("surface", "live", "expected"),
    [
        ("posts", False, True),
        ("posts", True, False),
        ("live", True, True),
        ("live", False, False),
        ("both", True, True),
        ("both", False, True),
    ],
)
def test_a_comment_automation_listens_where_its_surface_says(
    surface: str, live: bool, expected: bool
) -> None:
    comment: Any = SimpleNamespace(is_live=live)
    assert runtime.on_surface(automation(surface), comment) is expected


def test_the_live_window_is_short_and_the_reason_is_plain() -> None:
    assert actions.LIVE_REPLY_WINDOW.total_seconds() <= 30 * 60
    assert actions.LIVE_ENDED == ("live_ended", "The Live had ended")


def test_the_activity_page_explains_a_live_that_ended() -> None:
    reason = reasons.explain("live_ended", platform="instagram")
    assert reason.code == "live_ended"
    assert "Live" in reason.text
    assert reason.target is None


def definition(surface: str, scope: str = "all", trigger: str = "comment_any") -> Definition:
    return Definition(
        social_account_id=None,
        account=None,
        trigger=trigger,
        keywords=[],
        post_scope=scope,
        posts=[],
        action="send_message",
        message_text="Hi",
        message_buttons=[],
        public_reply_texts=[],
        starts_at=None,
        ends_at=None,
        comment_surface=surface,
    )


def test_a_live_only_automation_needs_no_posts() -> None:
    now = datetime.now(UTC)
    fields = {e.field for e in activation_errors(definition("live"), disclosure=None, now=now)}
    assert "post_scope" not in fields
    fields = {e.field for e in activation_errors(definition("posts"), disclosure=None, now=now)}
    assert "post_scope" in fields  # "any comment" on all posts still needs a choice
