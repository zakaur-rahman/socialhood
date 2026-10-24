"""GR-29: automations on a Facebook Page, without a database. The triggers and steps Messenger
allows activate; the ones it doesn't are refused in plain words, with the Facebook limits and
names. Instagram keeps its own rules."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from socialhood.schemas.flows import FlowDefinition
from socialhood.services.automations import flows, validation
from socialhood.services.automations.validation import (
    AccountInfo,
    ButtonInfo,
    Definition,
    activation_errors,
    missing_fields,
)

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
FACEBOOK = AccountInfo(platform="facebook", status="active")
INSTAGRAM = AccountInfo(platform="instagram", status="active")

COMMENT = Definition(
    social_account_id=uuid.uuid4(),
    account=FACEBOOK,
    trigger="comment_keyword",
    keywords=["link"],
    post_scope="all",
    posts=[],
    action="send_message",
    message_text="Hi {first_name|there}! Here's the link.",
    message_buttons=[ButtonInfo("Open link", "https://maple.example/shop")],
    public_reply_texts=["Sent you a message!"],
    starts_at=None,
    ends_at=None,
)


def problems(d: Definition, disclosure: str | None = None) -> dict[str, str]:
    return {e.field: e.message for e in activation_errors(d, disclosure=disclosure, now=NOW)}


def test_a_complete_comment_automation_activates_on_a_page() -> None:
    assert problems(COMMENT) == {}


@pytest.mark.parametrize(
    "trigger",
    ["dm_keyword", "comment_any", "entry_link", "ad_click"],
)
def test_the_triggers_messenger_has_activate(trigger: str) -> None:
    d = replace(
        COMMENT,
        trigger=trigger,
        keywords=["hi"] if trigger == "dm_keyword" else [],
        post_scope="all" if trigger != "comment_any" else "selected",
        public_reply_texts=[],
    )
    found = problems(d)
    assert "trigger" not in found
    assert "social_account_id" not in found


@pytest.mark.parametrize("trigger", ["story_reply", "story_mention"])
def test_story_triggers_are_refused_on_a_page(trigger: str) -> None:
    d = replace(COMMENT, trigger=trigger, keywords=[], public_reply_texts=[])
    assert problems(d) == {"trigger": validation.COPY["facebook_stories"]}


@pytest.mark.parametrize("surface", ["live", "both"])
def test_live_comments_are_refused_on_a_page(surface: str) -> None:
    found = problems(replace(COMMENT, comment_surface=surface))
    assert found == {"comment_surface": validation.COPY["facebook_live"]}


def test_the_follow_line_is_refused_because_messenger_cannot_say() -> None:
    d = replace(
        COMMENT,
        trigger="dm_keyword",
        keywords=["hi"],
        public_reply_texts=[],
        follow_nudge=True,
        follow_nudge_text="Follow us",
    )
    assert problems(d) == {"follow_nudge": validation.COPY["facebook_follow"]}
    assert problems(replace(d, account=INSTAGRAM)) == {}


def test_a_message_may_be_2000_characters_on_a_page_but_1000_bytes_on_instagram() -> None:
    long = "x" * 1500
    d = replace(COMMENT, message_text=long, message_buttons=[], public_reply_texts=["ok"])
    assert problems(d) == {}
    assert list(problems(replace(d, account=INSTAGRAM))) == ["message_text"]
    over = problems(replace(d, message_text="y" * 2001))
    assert over["message_text"].startswith("Facebook allows 2,000 characters.")
    assert over["message_text"].endswith("this message is 2,001. Shorten it.")


def test_the_longest_rendering_with_the_disclosure_counts() -> None:
    d = replace(COMMENT, message_text="y" * 1995, message_buttons=[], public_reply_texts=["ok"])
    assert problems(d) == {}
    found = problems(d, disclosure="Sent automatically by Maple")
    assert "and the disclosure line" in found["message_text"]


def test_link_buttons_keep_the_640_character_text_limit_with_facebook_words() -> None:
    d = replace(COMMENT, message_text="z" * 641)
    found = problems(d)
    assert found == {
        "message_text": "With link buttons Facebook allows 640 characters. Shorten the message."
    }
    ig = problems(replace(d, account=INSTAGRAM))
    assert "With link buttons Instagram allows 640 characters." in ig["message_text"]


def test_a_comment_dm_cannot_carry_an_image_and_says_facebook() -> None:
    found = problems(replace(COMMENT, has_image=True))
    assert found["message_media_asset_id"].startswith("Facebook's replies to comments")


def test_other_platforms_still_cannot_run_automations() -> None:
    d = replace(COMMENT, account=AccountInfo(platform="whatsapp", status="active"))
    assert missing_fields(activation_errors(d, disclosure=None, now=NOW)) == ["social_account_id"]
    assert "Instagram and Facebook" in problems(d)["social_account_id"]


# ---------------------------------------------------------------- flows


def flow(*steps: dict[str, Any]) -> FlowDefinition:
    return FlowDefinition.model_validate({"start": steps[0]["id"], "steps": list(steps)})


def send(id: str, text: str = "Hi", **kw: Any) -> dict[str, Any]:
    return {"type": "send", "id": id, "text": text, **kw}


def ctx(platform: str, trigger: str = "dm_keyword") -> flows.Context:
    return flows.Context(
        trigger=trigger,
        disclosure=None,
        fields={"city": flows.FieldSpec("text")},
        tag_ids=frozenset(),
        platform=platform,
    )


def found(definition: FlowDefinition, context: flows.Context) -> dict[str, str]:
    return {e.field: e.message for e in flows.activation_errors(definition, context)}


def test_a_flow_with_quick_replies_buttons_and_a_branch_runs_on_a_page() -> None:
    definition = flow(
        send(
            "a",
            "Pick one",
            quick_replies=[{"title": "Prices", "next": "b"}, {"title": "Hours", "next": "c"}],
            on_text="b",
        ),
        send("b", "Prices are here", buttons=[{"title": "Shop", "url": "https://maple.example"}]),
        {"type": "ask", "id": "c", "text": "Your city?", "field_key": "city"},
    )
    assert found(definition, ctx("facebook")) == {}


def test_a_flow_message_is_limited_to_2000_characters_on_a_page() -> None:
    definition = flow(send("a", "x" * 1500))
    assert found(definition, ctx("facebook")) == {}
    assert list(found(definition, ctx("instagram"))) == ["flow.steps.0.text"]
    too_long = found(flow(send("a", "x" * 2001)), ctx("facebook"))
    assert too_long["flow.steps.0.text"].startswith("Facebook allows 2,000 characters.")


def test_following_the_page_cannot_be_branched_on() -> None:
    definition = flow(
        send("a", "Hi", next="b"),
        {
            "type": "branch",
            "id": "b",
            "rules": [{"when": {"kind": "follows_business", "follows": False}, "next": "c"}],
        },
        send("c", "Please follow us"),
    )
    on_page = found(definition, ctx("facebook"))
    assert on_page == {"flow.steps.1.rules.0.when": flows.COPY["facebook_follows"]}
    assert found(definition, ctx("instagram")) == {}


def test_the_profile_button_is_refused_on_a_page() -> None:
    definition = flow(send("a", "Hi", buttons=[{"title": "View profile", "profile": True}]))
    assert found(definition, ctx("facebook")) == {
        "flow.steps.0.buttons.0": flows.COPY["facebook_profile_button"]
    }
    assert found(definition, ctx("instagram")) == {}


def test_a_consent_question_is_refused_on_a_page() -> None:
    definition = flow(
        {
            "type": "ask",
            "id": "a",
            "text": "Your email?",
            "expect": "email",
            "consent": True,
        }
    )
    assert found(definition, ctx("facebook")) == {
        "flow.steps.0.consent": flows.COPY["facebook_consent"]
    }
    assert found(definition, ctx("instagram")) == {}


def test_a_comment_flow_says_facebook_when_it_waits_for_an_answer() -> None:
    definition = flow(send("a", "Thanks!", next="b"), send("b", "More"))
    on_page = found(definition, ctx("facebook", "comment_keyword"))
    assert on_page == {
        "flow.steps.1": flows.COPY["after_private_reply"].replace("Instagram", "Facebook")
    }
    assert "Facebook allows one reply to a comment" in on_page["flow.steps.1"]
    assert (
        "Instagram allows one reply"
        in found(definition, ctx("instagram", "comment_keyword"))["flow.steps.1"]
    )


def test_localize_only_changes_the_words_for_a_page() -> None:
    assert validation.localize("Instagram allows it", "facebook") == "Facebook allows it"
    assert validation.localize("Instagram allows it", "instagram") == "Instagram allows it"
    assert validation.localize("Instagram allows it", None) == "Instagram allows it"
