"""GR-16: the templates that carry a flow create a draft saved as a flow (version 1) that can be
activated once the link is filled in, on the Free plan too (PD-5, pending)."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.ingest import rows

# key: (trigger, steps, the fields still to fill: links and the [price] / [code] placeholders)
EXPECTED = {
    "story_giveaway": ("story_mention", 2, []),
    "lead_magnet": ("comment_keyword", 2, ["flow.steps.1.buttons.0.url"]),
    "price_by_option": (
        "comment_keyword",
        4,
        ["flow.steps.1.text", "flow.steps.2.text", "flow.steps.3.text"],
    ),
    "call_request": ("dm_keyword", 2, []),
    "entry_link_coupon": (
        "entry_link",
        1,
        ["flow.steps.0.text", "flow.steps.0.buttons.0.url"],
    ),
}


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


@pytest.mark.parametrize("key", list(EXPECTED))
async def test_a_flow_template_creates_a_draft_saved_as_a_flow(
    ws: Ws, engine: AsyncEngine, key: str
) -> None:
    trigger, steps, missing = EXPECTED[key]
    created = await ws.ok(
        "POST",
        "/automations",
        201,
        json={"template_key": key, "social_account_id": ws.account_id},
    )
    assert (created["template_key"], created["trigger"], created["status"]) == (
        key,
        trigger,
        "draft",
    )
    assert created["flow_source"] == "flow"
    assert created["missing_for_activation"] == missing
    stored = await rows(
        engine,
        "SELECT version, jsonb_array_length(definition->'steps') AS steps FROM automation_flows"
        " WHERE automation_id = :i",
        i=created["id"],
    )
    assert [(r["version"], r["steps"]) for r in stored] == [(1, steps)]
    flow = await ws.ok("GET", f"/automations/{created['id']}/flow")
    assert (flow["source"], flow["version"]) == ("flow", 1)
    assert len(flow["definition"]["steps"]) == steps


@pytest.mark.parametrize("plan", ["free", "pro"])
@pytest.mark.parametrize("key", list(EXPECTED))
async def test_a_flow_template_activates_once_filled(
    ws: Ws, engine: AsyncEngine, key: str, plan: str
) -> None:
    await set_plan(engine, ws.wid, plan)
    created = await ws.ok(
        "POST",
        "/automations",
        201,
        json={"template_key": key, "social_account_id": ws.account_id},
    )
    refused = await ws.call("POST", f"/automations/{created['id']}/activate")
    if created["missing_for_activation"]:
        assert refused.status_code == 422
    else:
        assert refused.status_code == 200

    flow = await ws.ok("GET", f"/automations/{created['id']}/flow")
    definition = flow["definition"]
    for step in definition["steps"]:
        for button in step.get("buttons", []):
            button["url"] = "https://example.com/offer"
        if "text" in step:
            step["text"] = step["text"].replace("[price]", "499").replace("[code]", "WELCOME10")
    saved = await ws.ok("PUT", f"/automations/{created['id']}/flow", json=definition)
    assert saved["missing_for_activation"] == []
    assert saved["source"] == "flow"
    active = await ws.ok("POST", f"/automations/{created['id']}/activate")
    assert active["status"] == "active"


# ---------------------------------------------------------------- placeholders (C-105)


async def test_activation_refuses_a_flow_that_still_says_price(ws: Ws) -> None:
    created = await ws.ok(
        "POST",
        "/automations",
        201,
        json={"template_key": "price_by_option", "social_account_id": ws.account_id},
    )
    refused = await ws.call("POST", f"/automations/{created['id']}/activate")
    assert refused.status_code == 422
    errors = [(e["field"], e["message"]) for e in refused.json()["errors"]]
    assert errors == [
        (f"flow.steps.{i}.text", "Replace [price] with your price.") for i in (1, 2, 3)
    ]

    # Filling one is not enough: the others stay refused, each on its own step.
    flow = await ws.ok("GET", f"/automations/{created['id']}/flow")
    definition = flow["definition"]
    definition["steps"][1]["text"] = "The small one is 299 [incl. GST]. Reply here to order."
    saved = await ws.ok("PUT", f"/automations/{created['id']}/flow", json=definition)
    assert saved["missing_for_activation"] == ["flow.steps.2.text", "flow.steps.3.text"]
    again = await ws.call("POST", f"/automations/{created['id']}/activate")
    assert [e["field"] for e in again.json()["errors"]] == [
        "flow.steps.2.text",
        "flow.steps.3.text",
    ]

    for step in definition["steps"][2:]:
        step["text"] = step["text"].replace("[price]", "499")
    await ws.ok("PUT", f"/automations/{created['id']}/flow", json=definition)
    active = await ws.ok("POST", f"/automations/{created['id']}/activate")
    assert active["status"] == "active"


async def test_the_coupon_template_needs_its_code(ws: Ws) -> None:
    created = await ws.ok(
        "POST",
        "/automations",
        201,
        json={"template_key": "entry_link_coupon", "social_account_id": ws.account_id},
    )
    flow = await ws.ok("GET", f"/automations/{created['id']}/flow")
    definition = flow["definition"]
    definition["steps"][0]["buttons"][0]["url"] = "https://example.com/offer"
    saved = await ws.ok("PUT", f"/automations/{created['id']}/flow", json=definition)
    assert saved["missing_for_activation"] == ["flow.steps.0.text"]
    refused = await ws.call("POST", f"/automations/{created['id']}/activate")
    assert refused.status_code == 422
    assert refused.json()["errors"][0]["message"] == "Replace [code] with your code."


async def test_a_message_on_the_settings_with_a_placeholder_is_refused(ws: Ws) -> None:
    draft = await ws.draft(message_text="Hi {first_name}! It is [price].")
    refused = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert refused.status_code == 422
    assert [(e["field"], e["message"]) for e in refused.json()["errors"]] == [
        ("message_text", "Replace [price] with your price.")
    ]
    fixed = await ws.ok(
        "PUT",
        f"/automations/{draft['id']}",
        json=ws.definition(message_text="Hi {first_name}! It is 499 [incl. GST]."),
    )
    assert fixed["missing_for_activation"] == []
    active = await ws.ok("POST", f"/automations/{draft['id']}/activate")
    assert active["status"] == "active"
