"""GR-06, GR-07: which triggers a DM can start, the story a reply answers, and the story scope
(pure: no database)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest

from socialhood.models.inbox import Message
from socialhood.services.automations import runtime
from socialhood.services.automations.runtime import HEART


def message(kind: str = "text", text: str | None = "hi", **attachment: Any) -> Message:
    attachments = [{"id": "a1", "type": "story", **attachment}] if attachment else []
    return cast(
        Message,
        SimpleNamespace(
            kind=kind,
            text=text,
            attachments=attachments,
            postback_payload=None,
            quick_reply_payload=None,
        ),
    )


def automation(
    scope: str = "all", stories: tuple[str, ...] = (), trigger: str = "story_reply"
) -> Any:
    return SimpleNamespace(trigger=trigger, post_scope=scope, story_ids=list(stories))


def test_a_plain_dm_starts_dm_keyword_automations_and_the_fallbacks() -> None:
    assert runtime.dm_triggers(message()) == ("dm_keyword", "first_message", "default_reply")


def test_a_story_reply_starts_story_reply_and_dm_keyword_automations() -> None:
    assert runtime.dm_triggers(message("story_reply", "Where from?", media_id="s1")) == (
        "story_reply",
        "dm_keyword",
    )


def test_a_story_like_starts_no_story_reply_automation() -> None:
    like = message("story_reply", HEART, media_id="s1")
    assert runtime.is_story_like(like)
    assert runtime.dm_triggers(like) == ("dm_keyword",)  # no welcome or default reply on a like
    assert not runtime.is_story_like(message("story_reply", "love it", media_id="s1"))
    assert not runtime.is_story_like(message("text", HEART))  # a heart in a plain DM is a DM


def test_a_story_mention_starts_story_mention_automations_only() -> None:
    assert runtime.dm_triggers(message("story_mention", None, url="https://x")) == (
        "story_mention",
    )


def test_the_story_a_reply_answers_is_its_attachments_media_id() -> None:
    assert runtime.story_id_of(message("story_reply", "x", media_id="s1")) == "s1"
    assert runtime.story_id_of(message("story_reply", "x", url="https://x")) is None
    assert runtime.story_id_of(message()) is None


@pytest.mark.parametrize(
    ("scope", "stories", "reply_to", "expected"),
    [
        ("all", (), "s1", True),
        ("all", (), None, True),
        ("selected", ("s1", "s2"), "s2", True),
        ("selected", ("s1",), "s9", False),  # another story, or one that has expired
        ("selected", ("s1",), None, False),  # a story we could not read
    ],
)
def test_a_chosen_story_scope(
    scope: str, stories: tuple[str, ...], reply_to: str | None, expected: bool
) -> None:
    msg = message("story_reply", "x", media_id=reply_to) if reply_to else message("story_reply")
    assert runtime.in_story_scope(automation(scope, stories), msg) is expected


def test_the_story_scope_leaves_other_triggers_alone() -> None:
    other = automation("selected", (), trigger="dm_keyword")
    assert runtime.in_story_scope(other, message())


# ---------------------------------------------------------------- the sandbox injector


def injected(**values: Any) -> Any:
    """What the sandbox route stores for an injected event, parsed like a real webhook."""
    from socialhood.api.v1.accounts import _sandbox_payload
    from socialhood.platforms.instagram.parse import parse
    from socialhood.platforms.instagram.webhooks import split_payload
    from socialhood.schemas.accounts import SandboxInbound

    body = SandboxInbound.model_validate({"account_id": str(uuid.uuid4()), **values})
    [raw] = split_payload(_sandbox_payload("sandbox_acct", body))
    return parse(raw.payload)


def test_the_sandbox_injects_a_story_reply_naming_its_story() -> None:
    event = injected(kind="story_reply", text="link please", story_id="sandbox_acct_story_1")
    assert (event.kind, event.text) == ("story_reply", "link please")
    assert [(a.kind, a.media_id) for a in event.attachments] == [("story", "sandbox_acct_story_1")]


def test_the_sandbox_story_reply_defaults_to_the_first_story() -> None:
    event = injected(kind="story_reply", text="hi")
    assert [a.media_id for a in event.attachments] == ["sandbox_acct_story_0"]


def test_the_sandbox_injects_a_story_like_and_a_story_mention() -> None:
    like = injected(kind="story_like")
    assert (like.kind, like.text) == ("story_reply", HEART)
    mention = injected(kind="story_mention")
    assert (mention.kind, mention.text) == ("story_mention", None)
    assert mention.attachments[0].url is not None


def test_a_sandbox_story_reply_needs_its_text() -> None:
    from pydantic import ValidationError

    from socialhood.schemas.accounts import SandboxInbound

    with pytest.raises(ValidationError):
        SandboxInbound.model_validate({"account_id": str(uuid.uuid4()), "kind": "story_reply"})
