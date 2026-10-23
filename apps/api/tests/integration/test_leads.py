"""GR-18: leads. Done when a lead's stage can be moved by hand with a note, the history shows who
and why, the contacts list filters by stage, the summary counts stages and conversions, the cold
setting is an admin's, and a move is a lead.stage_changed event."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.test_contact_segments import as_agent, person
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def move(ws: Ws, contact: uuid.UUID, stage: str, note: str | None = None) -> Any:
    body = {"stage": stage, **({"note": note} if note else {})}
    return await ws.ok("POST", f"/contacts/{contact}/lead-stage", json=body)


async def history(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT * FROM lead_stage_changes ORDER BY created_at, id"))
        return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------- moving a stage


async def test_a_new_contact_is_a_new_lead_and_a_member_moves_it(
    engine: AsyncEngine, ws: Ws
) -> None:
    contact = await person(engine, ws, "asha", "Asha")
    record = await ws.ok("GET", f"/contacts/{contact}")
    assert (record["lead_stage"], record["lead_stage_at"], record["lead_cold"]) == (
        "new",
        None,
        False,
    )

    moved = await move(ws, contact, "qualified", "Asked for a quote")
    assert moved["lead_stage"] == "qualified"
    assert moved["lead_stage_reason"] == "Asked for a quote"
    assert moved["lead_stage_at"] is not None
    assert moved["conversation_id"] is not None  # one click to the conversation

    [change] = await history(engine)
    assert (change["from_stage"], change["to_stage"], change["actor_kind"]) == (
        "new",
        "qualified",
        "member",
    )
    assert str(change["actor_user_id"]) == ws.user_id
    assert (change["rule"], change["reason"]) == (None, "Asked for a quote")


async def test_the_same_stage_again_records_nothing(engine: AsyncEngine, ws: Ws) -> None:
    contact = await person(engine, ws, "asha", "Asha")
    await move(ws, contact, "won")
    await move(ws, contact, "won", "Paid in full")
    [change] = await history(engine)
    assert change["to_stage"] == "won"
    assert (await ws.ok("GET", f"/contacts/{contact}"))["lead_stage_reason"] is None


async def test_a_lead_can_go_back_and_every_move_is_kept(engine: AsyncEngine, ws: Ws) -> None:
    contact = await person(engine, ws, "asha", "Asha")
    for stage in ("lost", "follow_up", "won"):
        await move(ws, contact, stage)
    assert [(c["from_stage"], c["to_stage"]) for c in await history(engine)] == [
        ("new", "lost"),
        ("lost", "follow_up"),
        ("follow_up", "won"),
    ]


async def test_a_bad_stage_or_note_is_refused_and_a_missing_contact_is_404(
    engine: AsyncEngine, ws: Ws
) -> None:
    contact = await person(engine, ws, "asha", "Asha")
    bad = await ws.call("POST", f"/contacts/{contact}/lead-stage", json={"stage": "hot"})
    assert bad.status_code == 422
    long_note = {"stage": "won", "note": "x" * 301}
    assert (
        await ws.call("POST", f"/contacts/{contact}/lead-stage", json=long_note)
    ).status_code == 422
    missing = await ws.call("POST", f"/contacts/{uuid.uuid4()}/lead-stage", json={"stage": "won"})
    assert missing.status_code == 404
    assert await history(engine) == []


async def test_an_agent_works_leads_but_does_not_set_the_cold_days(
    engine: AsyncEngine, ws: Ws, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    agent = await as_agent(ws, engine, client, clerk)
    contact = await person(engine, ws, "asha", "Asha")
    assert (await move(agent, contact, "qualified"))["lead_stage"] == "qualified"
    assert (await agent.ok("GET", "/leads/summary"))["cold_after_days"] == 7
    assert (await agent.ok("GET", "/leads/settings")) == {"cold_after_days": 7}
    denied = await agent.call("PATCH", "/leads/settings", json={"cold_after_days": 14})
    assert denied.status_code == 403


# ---------------------------------------------------------------- history in the timeline


async def test_the_timeline_shows_each_move_with_who_and_why(engine: AsyncEngine, ws: Ws) -> None:
    contact = await person(engine, ws, "asha", "Asha")
    await move(ws, contact, "qualified", "Asked for a quote.")
    async with engine.begin() as conn:  # a rule moved her on, as the gone-cold job would
        await conn.execute(
            text(
                "INSERT INTO lead_stage_changes (workspace_id, contact_id, from_stage, to_stage,"
                " actor_kind, rule, reason, created_at) VALUES (:w, :c, 'qualified', 'follow_up',"
                " 'rule', 'gone_cold', 'No reply for 7 days.', now() + interval '1 minute')"
            ),
            {"w": ws.wid, "c": contact},
        )
    page = await ws.ok("GET", f"/contacts/{contact}/timeline")
    moves = [i for i in page["items"] if i["kind"] == "lead_stage"]
    assert [m["title"] for m in moves] == ["Lead stage: Follow up", "Lead stage: Qualified"]
    assert moves[0]["detail"] == "From Qualified. Automatically. No reply for 7 days."
    assert moves[1]["detail"].startswith("From New. By ")
    assert moves[1]["detail"].endswith(". Asked for a quote.")


# ---------------------------------------------------------------- the list, count and segments


async def test_the_contacts_list_filters_by_stage(engine: AsyncEngine, ws: Ws) -> None:
    ids = {n: await person(engine, ws, n, n.title()) for n in ("asha", "bina", "chetan", "divya")}
    await move(ws, ids["asha"], "qualified")
    await move(ws, ids["bina"], "follow_up")
    await move(ws, ids["chetan"], "won")

    def names(page: dict[str, Any]) -> list[str]:
        return sorted(c["name"] for c in page["items"])

    one = await ws.ok("GET", "/contacts", params={"stage": "qualified"})
    assert names(one) == ["Asha"]
    assert one["items"][0]["lead_stage"] == "qualified"
    warm = await ws.ok("GET", "/contacts", params={"stage": ["qualified", "follow_up"]})
    assert names(warm) == ["Asha", "Bina"]
    new = await ws.ok("GET", "/contacts", params={"stage": "new"})
    assert names(new) == ["Divya"]
    assert (await ws.ok("GET", "/contacts/count", params={"stage": ["won", "new"]})) == {"count": 2}
    assert (await ws.call("GET", "/contacts", params={"stage": "hot"})).status_code == 422
    with_email = await ws.ok("GET", "/contacts", params={"stage": "new", "has_email": "true"})
    assert with_email["items"] == []  # the stage combines with the other filters


async def test_a_saved_segment_can_be_a_stage(engine: AsyncEngine, ws: Ws) -> None:
    asha = await person(engine, ws, "asha", "Asha")
    await person(engine, ws, "bina", "Bina")
    made = await ws.ok(
        "POST",
        "/contact-segments",
        201,
        json={"name": "Warm", "filter": {"stages": ["qualified", "follow_up"]}},
    )
    assert made["filter"]["stages"] == ["qualified", "follow_up"]
    params = {"stage": made["filter"]["stages"]}
    assert (await ws.ok("GET", "/contacts/count", params=params)) == {"count": 0}
    await move(ws, asha, "follow_up")
    assert (await ws.ok("GET", "/contacts/count", params=params)) == {"count": 1}


# ---------------------------------------------------------------- summary and settings


async def test_the_summary_counts_stages_cold_leads_and_the_weeks(
    engine: AsyncEngine, ws: Ws
) -> None:
    asha = await person(engine, ws, "asha", "Asha")
    bina = await person(engine, ws, "bina", "Bina")
    await person(engine, ws, "chetan", "Chetan")
    await move(ws, asha, "qualified")
    await move(ws, bina, "qualified")
    await move(ws, bina, "won")
    async with engine.begin() as conn:  # Asha went cold after her last message
        await conn.execute(
            text("UPDATE contacts SET lead_cold_at = now() WHERE id = :c"), {"c": asha}
        )

    summary = await ws.ok("GET", "/leads/summary")
    assert [(s["stage"], s["count"]) for s in summary["stages"]] == [
        ("new", 1),
        ("qualified", 1),
        ("follow_up", 0),
        ("won", 1),
        ("lost", 0),
    ]
    assert (summary["cold"], summary["cold_after_days"]) == (1, 7)
    assert len(summary["weeks"]) == 8
    assert summary["weeks"] == sorted(summary["weeks"], key=lambda w: w["week_start"])
    this_week = summary["weeks"][-1]
    assert (this_week["qualified"], this_week["won"]) == (2, 1)
    assert datetime.fromisoformat(this_week["week_start"]).weekday() == 0  # a Monday

    assert (await ws.ok("GET", f"/contacts/{asha}"))["lead_cold"] is True
    await move(ws, asha, "follow_up")  # any move clears the flag
    assert (await ws.ok("GET", f"/contacts/{asha}"))["lead_cold"] is False


async def test_the_cold_days_setting(ws: Ws) -> None:
    assert (await ws.ok("GET", "/leads/settings")) == {"cold_after_days": 7}
    assert (await ws.ok("PATCH", "/leads/settings", json={"cold_after_days": 14})) == {
        "cold_after_days": 14
    }
    assert (await ws.ok("GET", "/leads/summary"))["cold_after_days"] == 14
    for bad in (0, 91):
        refused = await ws.call("PATCH", "/leads/settings", json={"cold_after_days": bad})
        assert refused.status_code == 422


# ---------------------------------------------------------------- the event


async def test_a_move_is_a_lead_stage_changed_event(engine: AsyncEngine, ws: Ws) -> None:
    await ws.ok(
        "POST",
        "/webhook-endpoints",
        201,
        json={"url": "https://hooks.example.com/in", "events": ["lead.stage_changed"]},
    )
    contact = await person(engine, ws, "asha", "Asha")
    await move(ws, contact, "won", "Paid in full")
    await move(ws, contact, "won")  # no change, no event
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT event_type, payload FROM webhook_deliveries ORDER BY created_at")
            )
        ).all()
    [(kind, payload)] = rows
    assert kind == "lead.stage_changed"
    data = payload["data"]
    assert (data["from"], data["to"], data["reason"]) == ("new", "won", "Paid in full")
    assert data["changed_by"] == {"kind": "member", "user_id": ws.user_id, "rule": None}
    assert data["contact"]["id"] == str(contact)
    catalogue = await ws.ok("GET", "/webhook-events")
    assert "lead.stage_changed" in [e["type"] for e in catalogue["items"]]
