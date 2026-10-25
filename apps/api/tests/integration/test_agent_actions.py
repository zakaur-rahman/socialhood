"""The action gateway end to end (GR-36; FR-AGT-08, FR-AGT-09, TR-AGT-04): the agent proposes a
flow or a segment, nothing is saved until a member approves, and approving runs the normal
services. Rejection, expiry, a refused approval, idempotency, roles and the audit trail.

The proposals are made by calling the registered tools with a ToolContext for a real step (what
the executor does), so the tools, the gateway and the routes are the real ones; only the model's
choice of tool is skipped."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.agent.registry import Principal, ToolContext, ToolResult
from socialhood.agent.tools import load_tools
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.identity import Role
from tests.integration.test_agent_api import Team
from tests.support.agent import make_agent_run
from tests.support.api import Clerk, sign_in
from tests.support.inbox import make_account, make_thread


@pytest.fixture
async def team(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis) -> Team:
    """An owner and a team member (role agent) in one workspace."""
    owner, me = await sign_in(client, clerk, email="owner@example.com", first_name="Olivia")
    wid = me["workspaces"][0]["id"]
    member_clerk = clerk.add(email="member@example.com", first_name="Ben", last_name="Das")
    member_me = (await client.get("/v1/me", headers=clerk.headers(member_clerk))).json()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'agent')"
            ),
            {"w": wid, "u": member_me["id"]},
        )
    return Team(client, clerk, engine, redis, wid, owner, me["id"], member_clerk, member_me["id"])


PRICE_FLOW = {
    "request": "when someone comments PRICE send them the price list",
    "name": "Price list on PRICE",
    "trigger": "comment_keyword",
    "keywords": ["PRICE"],
    "steps": [{"type": "send", "text": "Here's our price list: example.com/prices"}],
}


async def propose(
    team: Team,
    name: str,
    args: dict[str, Any],
    *,
    role: Role = Role.OWNER,
    user_id: str | None = None,
    run_id: uuid.UUID | None = None,
    step_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID, ToolResult]:
    """Call proposal tool ``name`` for a running step; (run id, step id, result)."""
    if run_id is None or step_id is None:
        made = await make_agent_run(
            team.engine,
            workspace_id=team.wid,
            requested_by_user_id=user_id or team.owner_id,
            status="running",
            answer=None,
            answer_refs=[],
            completed_at=None,
            steps=[{"tool": name, "tier": "draft", "args": args, "status": "running"}],
        )
        run_id, step_id = made.id, made.step_ids[0]
    spec = load_tools().get(name)
    assert spec is not None
    with workspace_scope(uuid.UUID(team.wid)):
        async with AsyncSession(team.engine, expire_on_commit=False) as session:
            ctx = ToolContext(
                session=session,
                sessionmaker=make_sessionmaker(team.engine),
                platform=None,  # type: ignore[arg-type]
                workspace_id=uuid.UUID(team.wid),
                timezone=ZoneInfo("Asia/Kolkata"),
                now=datetime.now(UTC),
                principal=Principal(user_id=uuid.UUID(user_id or team.owner_id), role=role),
                run_id=run_id,
                step_id=step_id,
                step_key=f"{run_id}:0",
            )
            result = await spec.handler(ctx, spec.input_model.model_validate(args))
            await session.commit()
    return run_id, step_id, result


async def count(team: Team, table: str) -> int:
    [row] = await team.rows(f"SELECT count(*) AS n FROM {table}")  # noqa: S608
    return int(row["n"])


async def make_vips(team: Team) -> None:
    """A tag "vip" on two contacts, one of whom has an email, and one contact without it."""
    created = await team.post("/tags", {"name": "vip"})
    assert created.status_code == 201, created.text
    tag_id = created.json()["id"]
    account = await make_account(team.engine, team.wid)
    for email in ("a@example.com", None, "c@example.com"):
        thread = await make_thread(
            team.engine, workspace_id=team.wid, account_id=account, username=None
        )
        if email:
            await team.execute(
                "UPDATE contacts SET email = :e WHERE id = :c", e=email, c=thread.contact_id
            )
        if email != "c@example.com":  # c has an email but no tag
            await team.execute(
                "INSERT INTO contact_tags (workspace_id, contact_id, tag_id) VALUES (:w, :c, :t)",
                w=team.wid,
                c=thread.contact_id,
                t=tag_id,
            )


SEGMENT = {"name": "VIPs with email", "tags": ["vip"], "has_email": True}


async def decide(
    team: Team,
    approval_id: Any,
    verb: str,
    body: dict[str, Any] | None = None,
    who: str | None = None,
) -> httpx.Response:
    return await team.post(f"/agent/approvals/{approval_id}/{verb}", body or {}, who=who)


# ---------------------------------------------------------------- segments


async def test_a_segment_waits_for_approval_then_is_saved(team: Team) -> None:
    await make_vips(team)
    run_id, step_id, result = await propose(team, "propose_segment", SEGMENT)
    assert result.action_card.kind == "segment_proposal"  # type: ignore[attr-defined]
    assert result.match_count == 1  # type: ignore[attr-defined]
    approval_id = result.approval_id  # type: ignore[attr-defined]

    # Proposed, not saved.
    assert await count(team, "contact_segments") == 0
    [row] = await team.rows("SELECT * FROM agent_approvals")
    assert (row["status"], row["run_id"], row["step_id"]) == ("pending", run_id, step_id)
    assert row["idempotency_key"] == f"{run_id}:0"
    assert row["payload"]["tool"] == "propose_segment"
    assert (
        timedelta(hours=23, minutes=59)
        < row["expires_at"] - row["created_at"]
        <= timedelta(hours=24, minutes=1)
    )
    [step] = await team.rows("SELECT decision FROM agent_steps WHERE id = :s", s=step_id)
    assert step["decision"] == "approval"

    listed = await team.get("/agent/approvals")
    [item] = listed.json()["items"]
    assert (item["id"], item["status"], item["can_decide"]) == (str(approval_id), "pending", True)
    assert "VIPs with email" in item["summary"]

    approved = await decide(team, approval_id, "approve")
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved"
    assert body["decided_by"]["id"] == team.owner_id
    assert body["outcome"]["ok"] is True
    assert body["outcome"]["resource_kind"] == "segment"
    [segment] = await team.rows("SELECT name, filter FROM contact_segments")
    assert segment["name"] == "VIPs with email"
    assert segment["filter"]["has_email"] is True
    assert [e["event"] for e in body["events"]] == ["proposed", "approved", "executed"]
    assert body["events"][1]["actor"]["id"] == team.owner_id

    again = await decide(team, approval_id, "approve")
    assert again.status_code == 409  # a write never runs twice
    assert await count(team, "contact_segments") == 1


async def test_a_refused_approval_saves_nothing_and_can_be_edited(team: Team) -> None:
    await make_vips(team)
    _, _, result = await propose(team, "propose_segment", SEGMENT)
    approval_id = result.approval_id  # type: ignore[attr-defined]
    taken = await team.post("/contact-segments", {"name": "VIPs with email", "filter": {}})
    assert taken.status_code == 201

    refused = await decide(team, approval_id, "approve")
    assert refused.status_code == 200, refused.text
    body = refused.json()
    assert body["status"] == "pending"  # still the member's to edit or reject
    assert body["outcome"]["ok"] is False
    assert "already exists" in body["outcome"]["summary"]
    assert await count(team, "contact_segments") == 1
    assert [e["event"] for e in body["events"]] == ["proposed", "failed"]

    args = {**body["payload"]["args"], "name": "VIPs who gave an email"}
    fixed = await decide(team, approval_id, "approve", {"args": args})
    assert fixed.json()["status"] == "approved"
    assert fixed.json()["outcome"]["ok"] is True
    assert await count(team, "contact_segments") == 2
    bad = await decide(team, approval_id, "approve", {"args": {"nope": 1}})
    assert bad.status_code == 409  # decided already; checked before the arguments


async def test_edited_arguments_that_do_not_fit_are_a_validation_error(team: Team) -> None:
    await make_vips(team)
    _, _, result = await propose(team, "propose_segment", SEGMENT)
    response = await decide(team, result.approval_id, "approve", {"args": {"nope": 1}})  # type: ignore[attr-defined]
    assert response.status_code == 422
    assert await count(team, "contact_segments") == 0


async def test_an_unknown_tag_is_refused_before_anything_is_stored(team: Team) -> None:
    with pytest.raises(ApiError) as caught:
        await propose(team, "propose_segment", {"name": "Gold", "tags": ["gold"]})
    assert caught.value.code == "validation_error"
    assert await count(team, "agent_approvals") == 0


# ---------------------------------------------------------------- flows


async def test_a_flow_is_saved_as_a_draft_automation_and_never_switched_on(team: Team) -> None:
    await make_account(team.engine, team.wid)
    _, _, result = await propose(team, "propose_flow", PRICE_FLOW)
    assert result.action_card.kind == "flow_proposal"  # type: ignore[attr-defined]
    assert any("price list" in line for line in result.lines)  # type: ignore[attr-defined]
    assert await count(team, "automations") == 0

    approved = await decide(team, result.approval_id, "approve")  # type: ignore[attr-defined]
    assert approved.status_code == 200, approved.text
    outcome = approved.json()["outcome"]
    assert outcome["ok"] is True
    assert outcome["resource_kind"] == "automation"
    assert outcome["route"] == f"automations/{outcome['resource_id']}"
    [automation] = await team.rows("SELECT * FROM automations")
    assert str(automation["id"]) == outcome["resource_id"]
    assert (automation["status"], automation["trigger"]) == ("draft", "comment_keyword")
    assert automation["activated_at"] is None
    assert automation["flow_version"] == 1
    assert await count(team, "automation_flows") == 1
    [keyword] = await team.rows("SELECT keyword_normalized AS normalized FROM automation_keywords")
    assert keyword["normalized"] == "price"


async def test_a_flow_with_a_tag_resolves_it_and_a_missing_tag_is_refused(team: Team) -> None:
    await make_account(team.engine, team.wid)
    steps = [
        {"type": "send", "text": "Thanks for asking!"},
        {"type": "action", "action": "add_tag", "tag": "VIP"},
    ]
    with pytest.raises(ApiError) as caught:
        await propose(team, "propose_flow", {**PRICE_FLOW, "steps": steps})
    assert "no tag called" in (caught.value.detail or "")
    assert await count(team, "agent_approvals") == 0

    created = await team.post("/tags", {"name": "vip"})
    _, _, result = await propose(team, "propose_flow", {**PRICE_FLOW, "steps": steps})
    approved = await decide(team, result.approval_id, "approve")  # type: ignore[attr-defined]
    assert approved.json()["outcome"]["ok"] is True
    [flow] = await team.rows("SELECT definition FROM automation_flows")
    assert flow["definition"]["steps"][1]["action"]["tag_id"] == created.json()["id"]


async def test_an_assign_step_names_a_member_and_is_saved_as_a_draft(team: Team) -> None:
    await make_account(team.engine, team.wid)
    steps = [
        {"type": "send", "text": "Thanks! Someone will be with you."},
        {
            "type": "action",
            "action": "assign",
            "assign_to": "member",
            "member": "MEMBER@example.com",
        },
    ]
    _, _, result = await propose(team, "propose_flow", {**PRICE_FLOW, "steps": steps})
    lines = result.lines  # type: ignore[attr-defined]
    assert any(line.startswith("2. assign to ") and "team member" not in line for line in lines)
    approved = await decide(team, result.approval_id, "approve")  # type: ignore[attr-defined]
    assert approved.json()["outcome"]["ok"] is True
    [flow] = await team.rows("SELECT definition FROM automation_flows")
    assert flow["definition"]["steps"][1]["action"] == {
        "kind": "assign",
        "mode": "member",
        "user_id": team.member_id,
    }


async def test_an_assign_step_for_a_stranger_is_refused_and_lists_the_team(team: Team) -> None:
    await make_account(team.engine, team.wid)
    steps = [{"type": "action", "action": "assign", "member": "nobody@elsewhere.com"}]
    with pytest.raises(ApiError) as caught:
        await propose(team, "propose_flow", {**PRICE_FLOW, "steps": steps})
    assert caught.value.code == "validation_error"
    assert "no team member called" in (caught.value.detail or "")
    assert await count(team, "agent_approvals") == 0


async def test_a_round_robin_assign_step_says_what_to_switch_on(team: Team) -> None:
    await make_account(team.engine, team.wid)
    steps = [
        {"type": "send", "text": "Thanks!"},
        {"type": "action", "action": "assign", "assign_to": "round_robin"},
    ]
    _, _, result = await propose(team, "propose_flow", {**PRICE_FLOW, "steps": steps})
    lines = " ".join(result.lines)  # type: ignore[attr-defined]
    assert "assign to the next available member" in lines
    assert "not handed out in turn yet" in lines  # the workspace setting is off

    await team.execute(
        "UPDATE workspaces SET assignment_round_robin = true WHERE id = :w", w=team.wid
    )
    await team.execute(
        "UPDATE workspace_members SET available_for_assignment = false WHERE workspace_id = :w",
        w=team.wid,
    )
    _, _, again = await propose(team, "propose_flow", {**PRICE_FLOW, "steps": steps})
    said = " ".join(again.lines)  # type: ignore[attr-defined]
    assert "Nobody is available for assignment now" in said
    assert "not handed out in turn yet" not in said


async def test_a_new_flow_for_an_existing_automation_keeps_its_status(team: Team) -> None:
    await make_account(team.engine, team.wid)
    _, _, first = await propose(team, "propose_flow", PRICE_FLOW)
    done = await decide(team, first.approval_id, "approve")  # type: ignore[attr-defined]
    automation_id = done.json()["outcome"]["resource_id"]

    change = {
        "request": "add a thank-you after the price list",
        "automation_id": automation_id,
        "steps": [
            {"type": "send", "text": "Here's our price list: example.com/prices"},
            {"type": "send", "text": "Reply here with any questions."},
        ],
    }
    _, _, second = await propose(team, "propose_flow", change)
    assert "stays draft" in " ".join(second.lines)  # type: ignore[attr-defined]
    saved = await decide(team, second.approval_id, "approve")  # type: ignore[attr-defined]
    assert saved.json()["outcome"]["ok"] is True
    assert await count(team, "automations") == 1
    [row] = await team.rows("SELECT status FROM automations")
    assert row["status"] == "draft"


async def test_a_flow_over_the_plan_step_cap_is_refused_when_proposed(team: Team) -> None:
    await make_account(team.engine, team.wid)
    steps = [{"type": "send", "text": f"Message {i}"} for i in range(1, 30)]
    with pytest.raises(ApiError) as caught:
        await propose(team, "propose_flow", {**PRICE_FLOW, "steps": steps})
    assert caught.value.code == "quota_exceeded"
    assert await count(team, "agent_approvals") == 0
    assert await count(team, "automations") == 0


# ---------------------------------------------------------------- rejection, expiry, idempotency


async def test_rejecting_saves_nothing_and_is_recorded(team: Team) -> None:
    await make_vips(team)
    _, _, result = await propose(team, "propose_segment", SEGMENT)
    rejected = await decide(team, result.approval_id, "reject")  # type: ignore[attr-defined]
    assert rejected.status_code == 200
    body = rejected.json()
    assert (body["status"], body["decided_by"]["id"]) == ("rejected", team.owner_id)
    assert [e["event"] for e in body["events"]] == ["proposed", "rejected"]
    assert await count(team, "contact_segments") == 0
    assert (await decide(team, result.approval_id, "approve")).status_code == 409  # type: ignore[attr-defined]
    assert (await decide(team, result.approval_id, "reject")).status_code == 409  # type: ignore[attr-defined]


async def test_an_approval_expires_and_can_no_longer_be_approved(team: Team) -> None:
    await make_vips(team)
    _, _, result = await propose(team, "propose_segment", SEGMENT)
    await team.execute(
        "UPDATE agent_approvals SET expires_at = now() - interval '1 minute' WHERE id = :a",
        a=result.approval_id,  # type: ignore[attr-defined]
    )
    pending = await team.get("/agent/approvals")
    assert pending.json()["items"] == []  # past its time: no longer waiting
    listed = await team.get("/agent/approvals", status="expired")
    [item] = listed.json()["items"]
    assert item["status"] == "expired"
    assert [e["event"] for e in item["events"]] == ["proposed", "expired"]
    assert item["events"][1]["actor"] is None
    response = await decide(team, result.approval_id, "approve")  # type: ignore[attr-defined]
    assert response.status_code == 409
    assert "expired" in response.json()["detail"]
    assert await count(team, "contact_segments") == 0


async def test_an_unexpired_approval_past_due_is_expired_by_the_decision_itself(team: Team) -> None:
    await make_vips(team)
    _, _, result = await propose(team, "propose_segment", SEGMENT)
    await team.execute(
        "UPDATE agent_approvals SET expires_at = now() - interval '1 minute' WHERE id = :a",
        a=result.approval_id,  # type: ignore[attr-defined]
    )
    assert (await decide(team, result.approval_id, "approve")).status_code == 409  # type: ignore[attr-defined]
    [row] = await team.rows("SELECT status FROM agent_approvals")
    assert row["status"] == "expired"  # saved even though the request was refused


async def test_proposing_twice_from_one_step_files_one_approval(team: Team) -> None:
    await make_vips(team)
    run_id, step_id, first = await propose(team, "propose_segment", SEGMENT)
    _, _, second = await propose(team, "propose_segment", SEGMENT, run_id=run_id, step_id=step_id)
    assert first.approval_id == second.approval_id  # type: ignore[attr-defined]
    assert await count(team, "agent_approvals") == 1
    assert await count(team, "agent_approval_events") == 1


# ---------------------------------------------------------------- roles


async def test_a_team_member_cannot_propose(team: Team) -> None:
    await make_vips(team)
    with pytest.raises(ApiError) as caught:
        await propose(team, "propose_segment", SEGMENT, role=Role.AGENT, user_id=team.member_id)
    assert caught.value.code == "forbidden"
    assert await count(team, "agent_approvals") == 0


async def test_a_team_member_cannot_approve_and_sees_only_their_own_runs(team: Team) -> None:
    await make_vips(team)
    # Proposed in the owner's run: a team member can't see it at all.
    _, _, theirs = await propose(team, "propose_segment", SEGMENT)
    member = team.member
    assert (await team.get("/agent/approvals", who=member)).json()["items"] == []
    for verb in ("approve", "reject"):
        hidden = await decide(team, theirs.approval_id, verb, who=member)  # type: ignore[attr-defined]
        assert hidden.status_code == 404

    # An approval on the member's own run is visible but they can't approve (the screen is for
    # owners and admins); the card tells the web.
    _, _, mine = await propose(
        team, "propose_segment", {**SEGMENT, "name": "Mine"}, user_id=team.member_id
    )
    listed = await team.get("/agent/approvals", who=member)
    [item] = listed.json()["items"]
    assert (item["id"], item["can_decide"]) == (str(mine.approval_id), False)  # type: ignore[attr-defined]
    refused = await decide(team, mine.approval_id, "approve", who=member)  # type: ignore[attr-defined]
    assert refused.status_code == 403
    assert await count(team, "contact_segments") == 0
    # They can withdraw their own proposal.
    assert (await decide(team, mine.approval_id, "reject", who=member)).status_code == 200  # type: ignore[attr-defined]


async def test_an_admin_approves_what_the_owner_asked_for(team: Team) -> None:
    await make_vips(team)
    admin = await team.join("admin-1", "admin")
    del admin
    _, _, result = await propose(team, "propose_segment", SEGMENT)
    response = await decide(team, result.approval_id, "approve", who="admin-1")  # type: ignore[attr-defined]
    assert response.status_code == 200, response.text
    assert response.json()["decided_by"]["name"] is not None


# ---------------------------------------------------------------- the run trace


async def test_the_run_detail_shows_its_approvals_and_their_trail(team: Team) -> None:
    await make_vips(team)
    run_id, _, result = await propose(team, "propose_segment", SEGMENT)
    await decide(team, result.approval_id, "approve")  # type: ignore[attr-defined]
    detail = (await team.get(f"/agent/runs/{run_id}")).json()
    [approval] = detail["approvals"]
    assert approval["id"] == str(result.approval_id)  # type: ignore[attr-defined]
    assert approval["status"] == "approved"
    assert [e["event"] for e in approval["events"]] == ["proposed", "approved", "executed"]
    assert approval["requested_by"]["id"] == team.owner_id
    only_run = await team.get("/agent/approvals", status="approved", run_id=str(run_id))
    assert [i["id"] for i in only_run.json()["items"]] == [approval["id"]]
    elsewhere = await team.get("/agent/approvals", status="all", run_id=str(uuid.uuid4()))
    assert elsewhere.json()["items"] == []
