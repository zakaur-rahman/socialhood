"""GR-26: the Zapier trigger names map onto GR-04's event catalogue, and the REST hook routes are in
the public API's document with the webhooks:subscribe scope."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from socialhood.api.public_openapi import public_openapi
from socialhood.main import create_app
from socialhood.schemas.api_keys import MCP_ONLY_SCOPES, SCOPE_DESCRIPTIONS
from socialhood.schemas.public_hooks import HookSubscribe
from socialhood.services import api_hooks
from socialhood.services.webhooks import events


def test_every_zapier_trigger_maps_to_an_event_that_is_raised() -> None:
    raised = {e.name for e in events.EVENTS if e.emitted}
    assert set(api_hooks.TRIGGER_EVENTS.values()) <= raised
    assert set(api_hooks.TRIGGER_EVENTS) == {
        "new_contact",
        "lead_captured",
        "tag_added",
        "new_message",
        "run_completed",
    }
    assert api_hooks.EVENT_TRIGGERS["contact.tagged"] == "tag_added"


def test_a_trigger_must_be_one_zapier_knows() -> None:
    assert HookSubscribe(trigger="new_contact", target_url="https://hooks.zapier.com/x").trigger
    with pytest.raises(ValidationError):
        HookSubscribe(trigger="contact.created", target_url="https://hooks.zapier.com/x")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        HookSubscribe(trigger="new_contact", target_url="x" * 2001)


def test_the_hook_routes_need_the_subscribe_scope(api_settings: Any) -> None:
    document = public_openapi(create_app(api_settings))
    hooks = document["paths"]["/public/v1/hooks"]
    assert hooks["post"]["x-required-scope"] == "webhooks:subscribe"
    assert hooks["get"]["x-required-scope"] == "webhooks:subscribe"
    assert (
        document["paths"]["/public/v1/hooks/{hook_id}"]["delete"]["x-required-scope"]
        == "webhooks:subscribe"
    )
    # The subscribe response carries the signing secret once, like GR-04's create response.
    schemas = document["components"]["schemas"]
    assert "signing_secret" in schemas["HookSubscribed"]["properties"]
    assert "signing_secret" not in schemas["Hook"]["properties"]
    # Every scope a key can carry now opens something here, or (C-165) on the MCP server.
    used = {
        op["x-required-scope"]
        for ops in document["paths"].values()
        for op in ops.values()
        if "x-required-scope" in op
    }
    assert used == set(SCOPE_DESCRIPTIONS) - set(MCP_ONLY_SCOPES)
