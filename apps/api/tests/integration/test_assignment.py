"""GR-20: assigning conversations. Done when a round-robin assignment notifies the agent and the
"Assigned to me" view shows only their conversations. Also who may assign whom, the note in the
thread, the audit row and timeline entry, availability, concurrent inbound messages taking
different turns, removing a member, the flow action, and the routes under tenancy."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.auth.invitations import FakeInvitationSender, use_invitation_sender
from socialhood.services.automations.runtime import Outcome
from socialhood.services.webhook_processing import process_event
from socialhood.settings import Settings
from tests.integration.test_flow_runs import ref, send, started, with_flow
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.inbox import make_thread
from tests.support.ingest import sessions
from tests.support.runtime import World, make_world, platform_deps


@pytest.fixture(autouse=True)
def _sender() -> Any:
    with use_invitation_sender(FakeInvitationSender()):
        yield


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None) -> Ws:
    owner = await workspace(client, clerk)
    await set_plan(engine, owner.wid, "pro")  # three seats
    return owner


async def join(ws: Ws, email: str, role: str = "agent") -> Ws:
    await ws.ok("POST", "/invitations", 201, json={"email": email, "role": role})
    clerk_id = ws.clerk.add(email=email)
    me = await ws.client.get("/v1/me", headers=ws.clerk.headers(clerk_id))
    assert me.status_code == 200, me.text
    return Ws(ws.client, ws.clerk, clerk_id, ws.wid, me.json()["id"], ws.account_id)


async def thread(ws: Ws, engine: AsyncEngine, name: str = "Priya Shah") -> str:
    made = await make_thread(
        engine, workspace_id=ws.wid, account_id=ws.account_id, display_name=name, username=None
    )
    return str(made.conversation_id)


async def assign(who: Ws, conversation: str, user_id: str | None) -> httpx.Response:
    return await who.call(
        "PUT", f"/conversations/{conversation}/assignee", json={"user_id": user_id}
    )


async def assignee_of(ws: Ws, conversation: str) -> str | None:
    detail = await ws.ok("GET", f"/conversations/{conversation}")
    return detail["assignee"]["user_id"] if detail["assignee"] else None


async def inbound(ws: Ws, sender: str, body: str = "Hello") -> None:
    """A sandbox message, stored; ``process`` handles it next."""
    await ws.ok(
        "POST",
        "/dev/sandbox/inbound",
        200,
        json={"account_id": ws.account_id, "kind": "dm", "text": body, "from_id": sender},
    )


async def process(engine: AsyncEngine, redis: Redis) -> None:
    """Process every stored webhook event, all at once (as the worker would)."""
    ids = [
        r["id"]
        for r in await rows(engine, "SELECT id FROM webhook_events WHERE status = 'received'")
    ]
    maker = sessions(engine)
    await asyncio.gather(*(process_event(maker, event_id, redis) for event_id in ids))


async def name_of(ws: Ws, user_id: str) -> str:
    members = {m["user_id"]: m["name"] for m in (await ws.ok("GET", "/assignment"))["members"]}
    return str(members[user_id])


async def notifications_of(who: Ws) -> list[dict[str, Any]]:
    return (await who.ok("GET", "/notifications"))["items"]


# ---------------------------------------------------------------- manual assignment


async def test_an_admin_assigns_and_unassigns_with_a_note_audit_and_timeline(
    ws: Ws, engine: AsyncEngine
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    conv = await thread(ws, engine)
    assert await assignee_of(ws, conv) is None

    detail = await ws.ok("PUT", f"/conversations/{conv}/assignee", json={"user_id": sam.user_id})
    assert detail["assignee"]["user_id"] == sam.user_id
    assert detail["assigned_at"] is not None
    sam_name = await name_of(ws, sam.user_id)
    messages = (await ws.ok("GET", f"/conversations/{conv}/messages"))["items"]
    notes = [m["text"] for m in messages if m["kind"] == "system"]
    assert notes == [f"{await name_of(ws, ws.user_id)} assigned this to {sam_name}"]

    audited = await ws.ok("GET", "/audit-events", params={"action": "conversation.assigned"})
    events = audited["items"]
    assert [e["target_id"] for e in events] == [conv]
    assert events[0]["detail"]["to_user_id"] == sam.user_id
    assert events[0]["detail"]["via"] == "member"

    contact = (await ws.ok("GET", "/conversations"))["items"][0]["contact"]["id"]
    timeline = (await ws.ok("GET", f"/contacts/{contact}/timeline"))["items"]
    assert [i["title"] for i in timeline if i["kind"] == "assignment"] == [
        f"Assigned to {sam_name}"
    ]

    cleared = await ws.ok("PUT", f"/conversations/{conv}/assignee", json={"user_id": None})
    assert cleared["assignee"] is None
    assert cleared["assigned_at"] is None
    again = await ws.ok("PUT", f"/conversations/{conv}/assignee", json={"user_id": None})
    assert again["assignee"] is None  # nothing changes, nothing more is written
    unassigned = await ws.ok("GET", "/audit-events", params={"action": "conversation.unassigned"})
    assert len(unassigned["items"]) == 1


async def test_agents_take_release_and_hand_on_but_cannot_take_from_others(
    ws: Ws, engine: AsyncEngine
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    kim = await join(ws, "kim@example.com", "agent")
    first, second = await thread(ws, engine, "A"), await thread(ws, engine, "B")

    assert (await assign(sam, first, sam.user_id)).status_code == 200  # takes it
    assert (await assign(kim, first, kim.user_id)).status_code == 403  # not from a colleague
    assert (await assign(kim, first, None)).status_code == 403
    assert (await assign(kim, second, sam.user_id)).status_code == 403  # nor gives out a free one
    assert (await assign(sam, first, kim.user_id)).status_code == 200  # hands on their own
    assert await assignee_of(ws, first) == kim.user_id
    assert (await assign(kim, first, None)).status_code == 200  # releases
    assert (await assign(ws, second, sam.user_id)).status_code == 200  # an owner assigns anyone


async def test_the_assignee_must_be_a_member_of_this_workspace(
    ws: Ws, engine: AsyncEngine, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    other = await workspace(client, clerk, email="other@example.com")
    conv = await thread(ws, engine)
    response = await assign(ws, conv, other.user_id)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert await assignee_of(ws, conv) is None


async def test_the_assignee_is_told_unless_they_assigned_it_to_themselves(
    ws: Ws, engine: AsyncEngine
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    mine, theirs = await thread(ws, engine, "Mine"), await thread(ws, engine, "Theirs")
    await assign(sam, mine, sam.user_id)
    assert await notifications_of(sam) == []

    await assign(ws, theirs, sam.user_id)
    [note] = await notifications_of(sam)
    assert note["type"] == "conversation_assigned"
    assert note["title"] == "Theirs was assigned to you"
    assert note["link"] == f"/inbox/{theirs}"
    [row] = await rows(
        engine, "SELECT channels FROM notifications WHERE user_id = :u", u=sam.user_id
    )
    assert "in_app" in row["channels"]
    assert "push" in row["channels"]  # the "needs you" switch is on by default


async def test_a_member_with_the_needs_you_switch_off_gets_no_push(
    ws: Ws, engine: AsyncEngine
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    prefs = {
        "email_digest": False,
        "push": {"needs_you": False, "new_lead": True, "window_closing": True, "account": True},
    }
    await sam.ok("PUT", "/notification-preferences", json=prefs)
    conv = await thread(ws, engine)
    await assign(ws, conv, sam.user_id)
    [row] = await rows(
        engine, "SELECT channels FROM notifications WHERE user_id = :u", u=sam.user_id
    )
    assert row["channels"] == ["in_app"]


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


# ---------------------------------------------------------------- the views


async def test_assigned_to_me_shows_only_my_conversations(ws: Ws, engine: AsyncEngine) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    first, second, third = [await thread(ws, engine, n) for n in ("A", "B", "C")]
    await assign(ws, first, sam.user_id)
    await assign(ws, second, ws.user_id)

    def ids(listed: dict[str, Any]) -> set[str]:
        return {c["id"] for c in listed["items"]}

    assert ids(await sam.ok("GET", "/conversations", params={"view": "mine"})) == {first}
    assert ids(await ws.ok("GET", "/conversations", params={"view": "mine"})) == {second}
    assert ids(await ws.ok("GET", "/conversations", params={"view": "unassigned"})) == {third}
    by_member = await ws.ok("GET", "/conversations", params={"assignee_id": sam.user_id})
    assert ids(by_member) == {first}
    assert (await sam.ok("GET", "/conversations/counts"))["mine"] == 1
    assert (await ws.ok("GET", "/conversations/counts"))["mine"] == 1
    row = next(c for c in (await ws.ok("GET", "/conversations"))["items"] if c["id"] == first)
    assert row["assignee"]["user_id"] == sam.user_id


# ---------------------------------------------------------------- round-robin


async def test_round_robin_is_off_by_default_and_admins_turn_it_on(ws: Ws) -> None:
    overview = await ws.ok("GET", "/assignment")
    assert overview["round_robin"] is False
    assert [m["is_you"] for m in overview["members"]] == [True]
    sam = await join(ws, "sam@example.com", "agent")
    assert (
        await sam.call("PUT", "/assignment/settings", json={"round_robin": True})
    ).status_code == 403
    on = await ws.ok("PUT", "/assignment/settings", json={"round_robin": True})
    assert on["round_robin"] is True
    assert (await sam.ok("GET", "/assignment"))["round_robin"] is True  # any member reads it


async def test_a_round_robin_assignment_notifies_the_agent(
    ws: Ws, engine: AsyncEngine, redis: Redis
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    await ws.ok("PUT", "/assignment/settings", json={"round_robin": True})
    for i in range(4):
        await inbound(ws, f"cust_{i}")
    await process(engine, redis)
    mine = await sam.ok("GET", "/conversations", params={"view": "mine"})
    theirs = await ws.ok("GET", "/conversations", params={"view": "mine"})
    assert len(mine["items"]) == 2
    assert len(theirs["items"]) == 2  # the turns alternate between the two members
    assert {c["id"] for c in mine["items"]}.isdisjoint({c["id"] for c in theirs["items"]})
    notes = await notifications_of(sam)
    assert [n["type"] for n in notes] == ["conversation_assigned"] * 2
    assert notes[0]["body"] == "It was your turn in the round-robin."
    audited = await ws.ok("GET", "/audit-events", params={"action": "conversation.assigned"})
    assert {e["detail"]["via"] for e in audited["items"]} == {"round_robin"}
    assert {e["actor_name"] for e in audited["items"]} == {"Round-robin"}


async def test_a_member_who_is_away_is_skipped(ws: Ws, engine: AsyncEngine, redis: Redis) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    await ws.ok("PUT", "/assignment/settings", json={"round_robin": True})
    await sam.ok("PUT", f"/members/{sam.user_id}/availability", 204, json={"available": False})
    members = {m["user_id"]: m for m in (await ws.ok("GET", "/assignment"))["members"]}
    assert members[sam.user_id]["available"] is False
    for i in range(3):
        await inbound(ws, f"cust_{i}")
    await process(engine, redis)
    assert len((await ws.ok("GET", "/conversations", params={"view": "mine"}))["items"]) == 3
    assert (await sam.ok("GET", "/conversations", params={"view": "mine"}))["items"] == []


async def test_nobody_available_leaves_it_unassigned_and_manual_ignores_availability(
    ws: Ws, engine: AsyncEngine, redis: Redis
) -> None:
    await ws.ok("PUT", "/assignment/settings", json={"round_robin": True})
    await ws.ok("PUT", f"/members/{ws.user_id}/availability", 204, json={"available": False})
    await inbound(ws, "cust_1")
    await process(engine, redis)
    [listed] = (await ws.ok("GET", "/conversations"))["items"]
    assert listed["assignee"] is None
    assert (await assign(ws, listed["id"], ws.user_id)).status_code == 200  # still allowed by hand


async def test_availability_is_yours_unless_you_are_an_admin(ws: Ws) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    kim = await join(ws, "kim@example.com", "agent")
    denied = await sam.call(
        "PUT", f"/members/{kim.user_id}/availability", json={"available": False}
    )
    assert denied.status_code == 403
    await ws.ok("PUT", f"/members/{kim.user_id}/availability", 204, json={"available": False})
    gone = await ws.call("PUT", f"/members/{uuid.uuid4()}/availability", json={"available": False})
    assert gone.status_code == 404


async def test_concurrent_messages_take_different_turns(
    ws: Ws, engine: AsyncEngine, redis: Redis
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    await ws.ok("PUT", "/assignment/settings", json={"round_robin": True})
    await asyncio.gather(*(inbound(ws, f"cust_{i}") for i in range(6)))
    await process(engine, redis)
    assert len((await ws.ok("GET", "/conversations", params={"view": "mine"}))["items"]) == 3
    assert len((await sam.ok("GET", "/conversations", params={"view": "mine"}))["items"]) == 3


async def test_removing_a_member_gives_their_conversations_back(
    ws: Ws, engine: AsyncEngine
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    conv = await thread(ws, engine)
    await assign(ws, conv, sam.user_id)
    await ws.ok("DELETE", f"/members/{sam.user_id}", 204)
    assert await assignee_of(ws, conv) is None
    removed = await ws.ok("GET", "/audit-events", params={"action": "member.removed"})
    assert removed["items"][0]["detail"]["unassigned"] == 1


async def test_an_assignment_reaches_open_inboxes_live(
    ws: Ws, engine: AsyncEngine, redis: Redis
) -> None:
    sam = await join(ws, "sam@example.com", "agent")
    conv = await thread(ws, engine)
    await assign(ws, conv, sam.user_id)
    stream = await redis.xrange(f"events:{ws.wid}")
    updated = [fields["data"] for _, fields in stream if fields["type"] == "conversation.updated"]
    assert any(sam.user_id in data for data in updated)


# ---------------------------------------------------------------- the flow action


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


async def add_member(world: World, name: str) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:8]
    async with world.engine.begin() as conn:
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO users (clerk_user_id, email, name) VALUES (:c, :e, :n)"
                    " RETURNING id"
                ),
                {"c": f"user_{suffix}", "e": f"{suffix}@example.com", "n": name},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'agent')"
            ),
            {"w": world.wid, "u": user_id},
        )
    return uuid.UUID(str(user_id))


async def run_assign_flow(world: World, action: dict[str, Any]) -> None:
    await with_flow(
        world,
        {
            "start": "a",
            "steps": [
                send("a", "One moment.", next="assign"),
                {"type": "action", "id": "assign", "action": action},
            ],
        },
    )
    run = await started(world, ref())
    assert await world.run("flow", run["id"]) is Outcome.FIRED


async def test_the_flow_action_assigns_a_chosen_member(world: World) -> None:
    priya = await add_member(world, "Priya")
    await run_assign_flow(world, {"kind": "assign", "mode": "member", "user_id": str(priya)})
    [conv] = await world.rows("SELECT assignee_user_id FROM conversations")
    assert conv["assignee_user_id"] == priya
    [note] = await world.rows("SELECT text FROM messages WHERE kind = 'system'")
    assert note["text"].startswith("An automation assigned this to Priya")
    [audit] = await world.rows("SELECT actor_label, detail FROM audit_events")
    assert audit["actor_label"].startswith("Automation:")
    assert audit["detail"]["via"] == "automation"
    [told] = await world.rows("SELECT type FROM notifications WHERE user_id = :u", u=priya)
    assert told["type"] == "conversation_assigned"


async def test_the_flow_action_takes_the_next_member_in_turn(world: World) -> None:
    await add_member(world, "Priya")
    await run_assign_flow(world, {"kind": "assign", "mode": "round_robin"})
    [conv] = await world.rows("SELECT assignee_user_id FROM conversations")
    assert conv["assignee_user_id"] is not None


async def test_the_flow_action_skips_a_member_who_has_left(world: World) -> None:
    await run_assign_flow(world, {"kind": "assign", "mode": "member", "user_id": str(uuid.uuid4())})
    [conv] = await world.rows("SELECT assignee_user_id FROM conversations")
    assert conv["assignee_user_id"] is None
    [run] = await world.rows("SELECT flow_state FROM automation_runs")
    assert run["flow_state"] == "done"  # the flow went on


async def test_a_flow_naming_a_stranger_cannot_be_activated(ws: Ws) -> None:
    created = await ws.draft()
    flow = {
        "start": "a",
        "steps": [
            {"type": "send", "id": "a", "text": "Hi", "next": "b"},
            {
                "type": "action",
                "id": "b",
                "action": {"kind": "assign", "mode": "member", "user_id": str(uuid.uuid4())},
            },
        ],
    }
    saved = await ws.ok("PUT", f"/automations/{created['id']}/flow", json=flow)
    assert any("action.user_id" in path for path in saved["missing_for_activation"])
    refused = await ws.call("POST", f"/automations/{created['id']}/activate")
    assert refused.status_code == 422
