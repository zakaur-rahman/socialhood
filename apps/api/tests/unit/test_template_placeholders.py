"""C-105: activation refuses a send text that still holds a template placeholder ([price], [code]),
with a plain error on the step. Only the listed tokens count, so a user's own brackets are fine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from socialhood.schemas.flows import AskStep, FlowButton, FlowDefinition, SendStep
from socialhood.services.automations import flows, templates, validation
from socialhood.services.automations.validation import AccountInfo, Definition

NOW = datetime(2026, 10, 24, tzinfo=UTC)


def test_the_list_is_the_one_the_templates_use() -> None:
    assert templates.PLACEHOLDERS == {"[price]": "your price", "[code]": "your code"}


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("The small one is [price]. Reply to order.", ["[price]"]),
        ("Your code is [code]. Price: [price]", ["[code]", "[price]"]),
        ("[PRICE] and [Price] and [price]", ["[price]"]),  # case doesn't hide it, once each
        ("Cost: [price]. Code: [price]", ["[price]"]),
        ("", []),
    ],
)
def test_the_tokens_still_in_a_text(text: str, found: list[str]) -> None:
    assert templates.unfilled(text) == found


@pytest.mark.parametrize(
    "text",
    [
        "Free shipping [on orders over 999]",
        "See [1] and [2]",
        "Use the code SAVE10 or [Shop link]",
        "Price: [price tag]",
        "[prices]",
        "price []",
        "{price}",
        "Hi {first_name|there}!",
    ],
)
def test_ordinary_brackets_are_left_alone(text: str) -> None:
    assert templates.unfilled(text) == []


def test_the_error_says_what_to_replace() -> None:
    assert templates.unfilled_copy("[price]") == "Replace [price] with your price."
    assert templates.unfilled_copy("[code]") == "Replace [code] with your code."


# ---------------------------------------------------------------- flows


def ctx() -> flows.Context:
    return flows.Context(trigger="dm_keyword", disclosure=None)


def flow(*steps: SendStep | AskStep) -> FlowDefinition:
    return FlowDefinition(start=steps[0].id, steps=list(steps))


def errors_of(definition: FlowDefinition) -> list[tuple[str, str]]:
    return [(e.field, e.message) for e in flows.activation_errors(definition, ctx())]


def test_a_send_step_with_a_placeholder_gets_the_error_on_its_text() -> None:
    definition = flow(
        SendStep(id="a", text="Hi!", next="b"),
        SendStep(id="b", text="That one is [price]. Reply to order."),
    )
    assert errors_of(definition) == [("flow.steps.1.text", "Replace [price] with your price.")]


def test_two_tokens_in_one_step_give_two_errors() -> None:
    definition = flow(SendStep(id="a", text="Your code [code] is half off, was [price]."))
    assert errors_of(definition) == [
        ("flow.steps.0.text", "Replace [code] with your code."),
        ("flow.steps.0.text", "Replace [price] with your price."),
    ]


def test_a_question_and_its_extra_lines_are_checked_too() -> None:
    definition = flow(
        AskStep(
            id="q",
            text="Your email for the [code] offer?",
            expect="email",
            retry_text="Send the email for [code] again.",
            confirm_text="Thanks! Your code is [code].",
        )
    )
    assert errors_of(definition) == [
        ("flow.steps.0.text", "Replace [code] with your code."),
        ("flow.steps.0.retry_text", "Replace [code] with your code."),
        ("flow.steps.0.confirm_text", "Replace [code] with your code."),
    ]


def test_filled_text_and_a_users_own_brackets_activate() -> None:
    definition = flow(
        SendStep(
            id="a",
            text="The small one is 499 [incl. GST]. Code: SAVE10",
            buttons=[FlowButton(title="Shop", url="https://example.com/shop")],
        )
    )
    assert errors_of(definition) == []


def test_a_placeholder_in_a_button_title_is_not_a_send_text() -> None:
    definition = flow(
        SendStep(
            id="a",
            text="Hello!",
            buttons=[FlowButton(title="[price]", url="https://example.com/shop")],
        )
    )
    assert errors_of(definition) == []


# ---------------------------------------------------------------- message settings


def settings(**values: object) -> Definition:
    base: dict[str, object] = {
        "social_account_id": uuid.uuid4(),
        "account": AccountInfo(platform="instagram", status="active"),
        "trigger": "dm_keyword",
        "keywords": ["price"],
        "post_scope": "all",
        "posts": [],
        "action": "send_message",
        "message_text": "Hi {first_name|there}! It is 499.",
        "message_buttons": [],
        "public_reply_texts": [],
        "starts_at": None,
        "ends_at": None,
    }
    return Definition(**{**base, **values})  # type: ignore[arg-type]


def fields(d: Definition) -> list[tuple[str, str]]:
    return [(e.field, e.message) for e in validation.activation_errors(d, disclosure=None, now=NOW)]


def test_a_message_with_a_placeholder_is_refused_on_message_text() -> None:
    d = settings(message_text="Hi! It costs [price].")
    assert fields(d) == [("message_text", "Replace [price] with your price.")]


def test_a_filled_message_activates() -> None:
    assert fields(settings()) == []
    assert fields(settings(message_text="Free delivery [over 999] for you")) == []


def test_the_opening_and_the_follow_line_are_checked() -> None:
    d = settings(
        trigger="comment_keyword",
        confirm_first=True,
        opening_text="Tap for your [code]",
        opening_button="Send it",
        follow_nudge=True,
        follow_nudge_text="Follow us to get [code]",
    )
    assert fields(d) == [
        ("opening_text", "Replace [code] with your code."),
        ("follow_nudge_text", "Replace [code] with your code."),
    ]


def test_an_ai_reply_has_no_send_text_to_check() -> None:
    d = settings(action="ai_reply", message_text=None, ai_instructions="Offer [price] list")
    assert fields(d) == []
