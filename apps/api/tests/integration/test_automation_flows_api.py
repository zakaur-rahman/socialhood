"""GR-03: an automation's flow over the API. Compiled from the message settings until it's saved
as a flow; saved versions; what activation needs; going back to the settings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk
from tests.support.automation_api import LINK, Ws, make_run, set_plan, workspace
from tests.support.ingest import rows


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


def fields_of(response: httpx.Response) -> list[str]:
    return [e["field"] for e in response.json().get("errors", [])]


def two_branch(**first: Any) -> dict[str, Any]:
    """Ask for their email, then a quick reply picks one of two messages."""
    return {
        "start": "hello",
        "steps": [
            {
                "type": "send",
                "id": "hello",
                "text": "Hi {first_name|there}! Want the catalogue or the price list?",
                "quick_replies": [
                    {"title": "Catalogue", "next": "email"},
                    {"title": "Prices", "next": "prices"},
                ],
                "on_text": "email",
                **first,
            },
            {
                "type": "ask",
                "id": "email",
                "text": "What's your email?",
                "expect": "email",
                "next": "catalogue",
            },
            {
                "type": "send",
                "id": "catalogue",
                "text": "Here it is.",
                "buttons": [{"title": "Catalogue", "url": LINK}],
            },
            {"type": "send", "id": "prices", "text": "Our prices start at 499."},
        ],
    }


async def test_a_new_automation_shows_its_settings_as_a_flow(ws: Ws) -> None:
    draft = await ws.draft(
        trigger="comment_keyword", confirm_first=True, opening_text="Tap!", opening_button="Send it"
    )
    assert draft["flow_source"] == "legacy"
    flow = await ws.ok("GET", f"/automations/{draft['id']}/flow")
    assert (flow["version"], flow["source"]) == (0, "legacy")
    assert [s["id"] for s in flow["definition"]["steps"]] == ["opening", "message"]
    opening = flow["definition"]["steps"][0]
    assert opening["quick_replies"] == [{"title": "Send it", "next": "message"}]
    assert flow["missing_for_activation"] == []


async def test_saving_a_flow_versions_it(ws: Ws, engine: AsyncEngine) -> None:
    draft = await ws.draft()
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=two_branch())
    assert (saved["version"], saved["source"]) == (1, "flow")
    assert saved["missing_for_activation"] == []
    assert (await ws.ok("GET", f"/automations/{draft['id']}"))["flow_source"] == "flow"

    # No run has used version 1, so a save changes it in place.
    edited = two_branch(text="Catalogue or prices?")
    assert (await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=edited))["version"] == 1
    # Once a run follows version 1, the next save makes version 2 and keeps 1 for that run.
    await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=draft["id"],
        created_at=datetime.now(UTC),
        trigger_message_id=None,
        trigger_comment_id=await comment_id(engine, ws),
        flow_version=1,
    )
    again = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=two_branch())
    assert again["version"] == 2
    versions = await rows(engine, "SELECT version FROM automation_flows ORDER BY version")
    assert [v["version"] for v in versions] == [1, 2]


async def comment_id(engine: AsyncEngine, ws: Ws) -> uuid.UUID:
    from tests.support.automations import make_comment, make_media_item

    post = await make_media_item(engine, workspace_id=ws.wid, account_id=ws.account_id)
    return await make_comment(
        engine, workspace_id=ws.wid, account_id=ws.account_id, media_item_id=post
    )


async def test_a_broken_flow_is_refused(ws: Ws) -> None:
    draft = await ws.draft()
    broken = two_branch()
    broken["steps"][1]["next"] = "nowhere"
    response = await ws.call("PUT", f"/automations/{draft['id']}/flow", json=broken)
    assert response.status_code == 422
    assert fields_of(response) == ["flow.steps.1"]
    looping = two_branch()
    looping["steps"][2]["next"] = "hello"
    assert fields_of(await ws.call("PUT", f"/automations/{draft['id']}/flow", json=looping)) == [
        "flow.steps.2"
    ]
    image = two_branch()
    image["steps"][3]["image_asset_id"] = str(uuid.uuid4())
    assert fields_of(await ws.call("PUT", f"/automations/{draft['id']}/flow", json=image)) == [
        "flow.steps.3.image_asset_id"
    ]
    unknown = await ws.call(
        "PUT", f"/automations/{draft['id']}/flow", json={"start": "a", "steps": [{"type": "x"}]}
    )
    assert unknown.status_code == 422


async def test_activation_checks_the_flow(ws: Ws) -> None:
    draft = await ws.draft()
    empty = two_branch(text="")
    saved = await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=empty)
    assert saved["missing_for_activation"] == ["flow.steps.0.text"]
    refused = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert refused.status_code == 422
    assert fields_of(refused) == ["flow.steps.0.text"]

    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=two_branch())
    active = await ws.ok("POST", f"/automations/{draft['id']}/activate")
    assert active["status"] == "active"
    # An active automation stays complete: a broken message or a trigger the flow can't serve
    # is refused.
    kept = await ws.call("PUT", f"/automations/{draft['id']}/flow", json=empty)
    assert (kept.status_code, fields_of(kept)) == (422, ["flow.steps.0.text"])
    linear = {
        "start": "a",
        "steps": [
            {"type": "send", "id": "a", "text": "One", "next": "b"},
            {"type": "send", "id": "b", "text": "Two"},
        ],
    }
    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=linear)
    to_comments = ws.definition(trigger="comment_keyword", message_text=None, message_buttons=[])
    moved = await ws.call("PUT", f"/automations/{draft['id']}", json=to_comments)
    assert (moved.status_code, fields_of(moved)) == (422, ["flow.steps.1"])


async def test_the_message_settings_no_longer_count_once_it_is_a_flow(ws: Ws) -> None:
    draft = await ws.draft()
    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=two_branch())
    # The editor's autosave may send an empty message; the flow is what runs.
    after = await ws.ok(
        "PUT", f"/automations/{draft['id']}", json=ws.definition(message_text=None, action=None)
    )
    assert after["missing_for_activation"] == []
    assert after["action"] == "send_message"
    await ws.ok("POST", f"/automations/{draft['id']}/activate")


async def test_an_ai_reply_needs_the_plan(ws: Ws) -> None:
    draft = await ws.draft()
    ai = {"start": "r", "steps": [{"type": "ai_reply", "id": "r", "instructions": "Answer it."}]}
    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=ai)
    assert (await ws.ok("GET", f"/automations/{draft['id']}"))["action"] == "ai_reply"
    refused = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert refused.status_code == 402
    assert refused.json()["entitlement"] == "ai_reply_automations"


async def test_going_back_to_the_settings(ws: Ws) -> None:
    draft = await ws.draft()
    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=two_branch())
    back = await ws.ok("DELETE", f"/automations/{draft['id']}/flow")
    assert (back["source"], back["version"]) == ("legacy", 0)
    assert [s["id"] for s in back["definition"]["steps"]] == ["message"]

    # An active flow automation whose settings are incomplete can't go back.
    other = await ws.draft(message_text=None)
    await ws.ok("PUT", f"/automations/{other['id']}/flow", json=two_branch())
    await ws.ok("POST", f"/automations/{other['id']}/activate")
    refused = await ws.call("DELETE", f"/automations/{other['id']}/flow")
    assert (refused.status_code, fields_of(refused)) == (422, ["message_text"])


async def test_a_copy_takes_the_flow(ws: Ws) -> None:
    draft = await ws.draft()
    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=two_branch())
    copy = await ws.ok("POST", f"/automations/{draft['id']}/duplicate", 201)
    flow = await ws.ok("GET", f"/automations/{copy['id']}/flow")
    assert (flow["source"], flow["version"]) == ("flow", 1)
    assert (
        flow["definition"] == (await ws.ok("GET", f"/automations/{draft['id']}/flow"))["definition"]
    )


async def test_another_workspaces_automation_has_no_flow(ws: Ws) -> None:
    missing = await ws.call("GET", f"/automations/{uuid.uuid4()}/flow")
    assert missing.status_code == 404


# ---------------------------------------------------------------- the flow editor (GR-13)


def linear(count: int) -> dict[str, Any]:
    """A flow of ``count`` messages, one after the other."""
    steps = [
        {"type": "send", "id": f"s{i}", "text": f"Message {i}", "next": f"s{i + 1}"}
        for i in range(count - 1)
    ]
    steps.append({"type": "send", "id": f"s{count - 1}", "text": "The last one"})
    return {"start": "s0", "steps": steps}


async def test_the_free_plan_caps_a_flow_at_five_steps(ws: Ws, engine: AsyncEngine) -> None:
    """PD-5 (pending): every plan can branch; Free is capped, with a plain 402."""
    draft = await ws.draft()
    path = f"/automations/{draft['id']}/flow"
    await ws.ok("PUT", path, json=linear(5))
    refused = await ws.call("PUT", path, json=linear(6))
    assert refused.status_code == 402
    body = refused.json()
    assert (body["code"], body["entitlement"], body["limit"]) == ("quota_exceeded", "flow_steps", 5)
    assert "5 steps in a flow" in body["detail"]
    # The stored flow is untouched by the refusal.
    assert len((await ws.ok("GET", path))["definition"]["steps"]) == 5

    await set_plan(engine, ws.wid, "pro")
    assert (await ws.ok("PUT", path, json=linear(6)))["source"] == "flow"


async def test_a_flow_over_the_plan_cap_does_not_activate(ws: Ws, engine: AsyncEngine) -> None:
    """A flow saved on Pro, then a downgrade: activation says so rather than running it."""
    draft = await ws.draft()
    await set_plan(engine, ws.wid, "pro")
    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=linear(7))
    await set_plan(engine, ws.wid, "free")
    refused = await ws.call("POST", f"/automations/{draft['id']}/activate")
    assert refused.status_code == 402
    assert refused.json()["entitlement"] == "flow_steps"


async def test_the_test_walks_a_flow_dry(ws: Ws) -> None:
    draft = await ws.draft()
    await ws.ok("PUT", f"/automations/{draft['id']}/flow", json=two_branch())
    path = f"/automations/{draft['id']}/test"
    first = await ws.ok("POST", path, json={"kind": "dm", "text": "link please"})
    assert [s["step_id"] for s in first["flow_path"]] == ["hello", "email", "catalogue"]
    hello = first["flow_path"][0]
    assert hello["quick_replies"] == ["Catalogue", "Prices"]
    assert hello["exits"] == ["Taps Catalogue", "Taps Prices", "Types an answer"]
    assert hello["picked"] == 0
    assert hello["text"].startswith("Hi Priya!")

    prices = await ws.ok("POST", path, json={"kind": "dm", "text": "link", "choices": [1]})
    assert [(s["step_id"], s["picked"]) for s in prices["flow_path"]] == [
        ("hello", 1),
        ("prices", None),
    ]

    # A settings automation has no flow path: its message is the whole test.
    plain = await ws.draft()
    result = await ws.ok(
        "POST", f"/automations/{plain['id']}/test", json={"kind": "dm", "text": "link"}
    )
    assert result["flow_path"] == []
