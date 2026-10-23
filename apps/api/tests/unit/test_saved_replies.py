"""GR-21: saved replies. Filling a body for a contact (fallbacks, empty fields, no braces left),
the shortcut rules, and a flow's send step that names a saved reply (pure: no database)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest

from socialhood.errors import ApiError
from socialhood.models.inbox import Contact
from socialhood.schemas.flows import FlowDefinition
from socialhood.services import saved_replies as sr
from socialhood.services.automations import flows

REPLY = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
MISSING = uuid.UUID("00000000-0000-4000-8000-0000000000a2")


def contact(**values: object) -> Contact:
    base: dict[str, object] = {
        "display_name": "Asha Rao",
        "username": "asha.rao",
        "email": "asha@example.com",
        "phone": "+919876543210",
        "fields": {"city": "Pune", "visits": 3.0, "vip": True},
    }
    return cast(Contact, SimpleNamespace(**{**base, **values}))


def filled(body: str, **values: object) -> str:
    return sr.fill(body, sr.contact_values(contact(**values)))


def test_the_contacts_own_details_fill_in() -> None:
    assert filled("Hi {first_name}! See you, {name} (@{username}).") == (
        "Hi Asha! See you, Asha Rao (@asha.rao)."
    )
    assert filled("{email} / {phone}") == "asha@example.com / +919876543210"


def test_custom_fields_fill_in_by_key() -> None:
    assert filled("Is {city} close to you? {visits} visits so far.") == (
        "Is Pune close to you? 3 visits so far."
    )


def test_an_unknown_field_is_empty_and_no_braces_are_left() -> None:
    out = filled("Hello {first_name}, your {order_id} is ready, {nope|friend}.")
    assert out == "Hello Asha, your  is ready, friend."
    assert "{" not in out
    assert "}" not in out


def test_a_missing_value_uses_its_fallback_or_nothing() -> None:
    assert filled("Hi {first_name|friend}", display_name=None) == "Hi friend"
    assert filled("Hi {first_name}", display_name=None) == "Hi there"  # as in automations
    assert filled("Mail {email}!", email=None) == "Mail !"
    assert filled("City: {city|your city}", fields={}) == "City: your city"


def test_a_value_that_is_not_text_is_empty() -> None:
    assert filled("VIP: {vip}.") == "VIP: ."


def test_no_contact_still_fills_without_leaving_braces() -> None:
    assert sr.fill("Hi {first_name}, {city}.", sr.contact_values(None)) == "Hi there, ."


def test_a_custom_field_cannot_change_a_built_in_one() -> None:
    assert filled("{first_name}", fields={"first_name": "Mallory"}) == "Asha"


def test_braces_that_are_not_fields_are_left_alone() -> None:
    assert (
        filled("Use {Uppercase} and { spaced } and {1}") == "Use {Uppercase} and { spaced } and {1}"
    )


@pytest.mark.parametrize(
    ("typed", "stored"),
    [("price", "price"), ("/Price", "price"), ("  /faq-2 ", "faq-2"), ("a_b", "a_b")],
)
def test_a_shortcut_is_stored_lower_case_without_the_slash(typed: str, stored: str) -> None:
    assert sr.normalize_shortcut(typed) == stored


@pytest.mark.parametrize("typed", ["", "/", "has space", "-start", "a" * 31, "pr!ce", "é"])
def test_a_bad_shortcut_is_a_validation_error(typed: str) -> None:
    with pytest.raises(ApiError) as raised:
        sr.normalize_shortcut(typed)
    assert raised.value.code == "validation_error"
    assert [e.field for e in raised.value.errors] == ["shortcut"]


# ---------------------------------------------------------------- the flow step


def step_flow(**send: object) -> FlowDefinition:
    return FlowDefinition.model_validate(
        {"start": "reply", "steps": [{"type": "send", "id": "reply", **send}]}
    )


def ctx(
    trigger: str = "dm_keyword", body: str = "Our prices start at {first_name}."
) -> flows.Context:
    return flows.Context(trigger=trigger, disclosure=None, saved_replies={REPLY: body})


def errors(definition: FlowDefinition, context: flows.Context) -> dict[str, str]:
    return {e.field: e.message for e in flows.activation_errors(definition, context)}


def test_a_step_that_sends_a_saved_reply_needs_no_text_of_its_own() -> None:
    assert errors(step_flow(saved_reply_id=str(REPLY)), ctx()) == {}


def test_a_step_naming_a_deleted_reply_cannot_be_activated() -> None:
    assert errors(step_flow(saved_reply_id=str(MISSING)), ctx()) == {
        "flow.steps.0.saved_reply_id": flows.COPY["saved_reply_missing"]
    }


def test_a_saved_reply_goes_alone() -> None:
    found = errors(
        step_flow(
            saved_reply_id=str(REPLY), buttons=[{"title": "Shop", "url": "https://shop.example"}]
        ),
        ctx(),
    )
    assert found == {"flow.steps.0.saved_reply_id": flows.COPY["saved_reply_alone"]}


def test_a_saved_reply_too_long_for_a_dm_is_flagged() -> None:
    found = errors(step_flow(saved_reply_id=str(REPLY)), ctx(body="é" * 600))
    assert list(found) == ["flow.steps.0.saved_reply_id"]


def test_a_comment_flow_cannot_open_with_a_saved_reply() -> None:
    found = errors(step_flow(saved_reply_id=str(REPLY)), ctx(trigger="comment_keyword"))
    assert found == {"flow.start": flows.COPY["comment_saved_reply"]}


def test_a_comment_flow_may_use_one_after_its_first_message() -> None:
    definition = FlowDefinition.model_validate(
        {
            "start": "opening",
            "steps": [
                {
                    "type": "send",
                    "id": "opening",
                    "text": "Want the prices?",
                    "quick_replies": [{"title": "Yes", "next": "reply"}],
                },
                {"type": "send", "id": "reply", "saved_reply_id": str(REPLY)},
            ],
        }
    )
    assert errors(definition, ctx(trigger="comment_keyword")) == {}


def test_a_flow_is_described_with_its_saved_reply() -> None:
    assert flows.describe(step_flow(saved_reply_id=str(REPLY))) == ["reply: send a saved reply"]
