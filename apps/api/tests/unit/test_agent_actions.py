"""The agent's proposed writes without a database (GR-36): the flow the model describes becomes a
typed, valid flow; the proposal tools refuse before touching anything when they must; broadcasts
are an unavailable slot; and the approval vocabulary matches what is stored."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, get_args
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from socialhood.agent import actions
from socialhood.agent.registry import CURRENT_RELEASE, Principal, Release, ToolContext, registry
from socialhood.agent.tools import load_tools
from socialhood.agent.tools.proposals import (
    ProposedStep,
    ProposeFlowInput,
    ProposeSegmentInput,
    build_flow,
)
from socialhood.errors import ApiError
from socialhood.models.agent import (
    APPROVAL_TTL,
    AgentApprovalEventKind,
    ApprovalStatus,
    RiskTier,
)
from socialhood.models.identity import Role
from socialhood.schemas.agent import ApprovalEventName, ApprovalListStatus, ApprovalStatusName
from socialhood.schemas.assignment import Assignable, AssignmentOverview
from socialhood.schemas.contacts import ContactFilterSpec
from socialhood.schemas.flows import (
    ActionStep,
    AddTag,
    Assign,
    BranchStep,
    SendStep,
    TagCondition,
)
from socialhood.services import agent_actions, assignment
from socialhood.services.automations import flows

VIP = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
TAGS = {"vip": VIP}


def steps(*raw: dict[str, Any]) -> list[ProposedStep]:
    return [ProposedStep.model_validate(r) for r in raw]


def ctx_for(role: Role, *, step: bool = True) -> ToolContext:
    """A context whose session is never touched: the gateway must refuse first."""
    return ToolContext(
        session=None,  # type: ignore[arg-type]
        sessionmaker=None,  # type: ignore[arg-type]
        platform=None,  # type: ignore[arg-type]
        workspace_id=uuid.uuid4(),
        timezone=ZoneInfo("Asia/Kolkata"),
        now=datetime(2026, 10, 24, 9, tzinfo=UTC),
        principal=Principal(user_id=uuid.uuid4(), role=role),
        run_id=uuid.uuid4(),
        step_id=uuid.uuid4() if step else None,
        step_key="run:0" if step else None,
    )


# ---------------------------------------------------------------- building the flow


def test_a_price_list_flow_is_a_valid_one_step_flow() -> None:
    flow = build_flow(steps({"type": "send", "text": "Here is our price list: example.com/p"}), {})
    assert flows.graph(flow)  # the flow engine accepts it
    [only] = flow.steps
    assert isinstance(only, SendStep)
    assert flow.start == only.id == "s1"
    assert only.next is None


def test_steps_chain_in_order_and_the_last_ends_the_flow() -> None:
    flow = build_flow(
        steps(
            {"type": "send", "text": "Hi!"},
            {"type": "action", "action": "add_tag", "tag": "VIP"},
            {"type": "delay", "seconds": 60},
            {"type": "end"},
        ),
        TAGS,
    )
    flows.graph(flow)
    assert [s.next for s in flow.steps[:3]] == ["s2", "s3", "s4"]  # type: ignore[union-attr]
    tag = flow.steps[1]
    assert isinstance(tag, ActionStep)
    assert isinstance(tag.action, AddTag)
    assert tag.action.tag_id == VIP  # tags are named by the model and resolved here


def test_a_branch_goes_where_its_rules_say_and_otherwise_to_the_next_step() -> None:
    flow = build_flow(
        steps(
            {
                "type": "branch",
                "rules": [{"when": {"kind": "tag", "tag": "vip"}, "goto": "vip"}],
            },
            {"type": "send", "text": "Welcome!", "goto": "vip"},
            {"id": "vip", "type": "send", "text": "Welcome back, VIP!"},
        ),
        TAGS,
    )
    flows.graph(flow)
    branch = flow.steps[0]
    assert isinstance(branch, BranchStep)
    assert isinstance(branch.rules[0].when, TagCondition)
    assert (branch.rules[0].next, branch.otherwise) == ("vip", "s2")


def test_quick_replies_lead_to_their_steps_and_typed_answers_to_the_next() -> None:
    flow = build_flow(
        steps(
            {
                "type": "send",
                "text": "Pick one",
                "quick_replies": [{"title": "Prices", "goto": "prices"}, {"title": "Hours"}],
            },
            {"type": "send", "text": "We open at 9.", "goto": "prices"},
            {"id": "prices", "type": "send", "text": "Cakes from 500."},
        ),
        {},
    )
    flows.graph(flow)
    first = flow.steps[0]
    assert isinstance(first, SendStep)
    assert [q.next for q in first.quick_replies] == ["prices", "s2"]
    assert first.on_text == "s2"


def test_an_unknown_tag_is_a_validation_error_that_lists_the_tags() -> None:
    with pytest.raises(ApiError) as caught:
        build_flow(steps({"type": "action", "action": "add_tag", "tag": "gold"}), TAGS)
    assert caught.value.code == "validation_error"
    assert "no tag called" in (caught.value.detail or "")
    assert "gold" in (caught.value.detail or "")
    assert "vip" in (caught.value.detail or "")


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "send"},  # no text
        {"type": "ask"},  # no question
        {"type": "delay"},  # no seconds
        {"type": "branch"},  # no rules
        {"type": "action"},  # no action
        {"type": "action", "action": "set_field", "field_key": "city"},  # no value
    ],
    ids=["send", "ask", "delay", "branch", "action", "set_field"],
)
def test_a_step_missing_what_it_needs_says_so(bad: dict[str, Any]) -> None:
    with pytest.raises(ApiError) as caught:
        build_flow(steps(bad), TAGS)
    assert caught.value.code == "validation_error"
    assert caught.value.errors[0].field.startswith("steps.0")


BEN = uuid.UUID("00000000-0000-4000-8000-0000000000b1")
ANN = uuid.UUID("00000000-0000-4000-8000-0000000000b2")
ROSTER = assignment.Roster(
    [(BEN, "Ben Das", "ben@maple.in"), (ANN, "Ann", "ann@maple.in"), (uuid.uuid4(), "Ann", None)]
)


def test_an_assign_step_resolves_a_member_by_name_or_email() -> None:
    by_name = build_flow(
        steps({"type": "action", "action": "assign", "assign_to": "member", "member": " ben das "}),
        TAGS,
        ROSTER,
    )
    [step] = by_name.steps
    assert isinstance(step, ActionStep)
    assert step.action == Assign(mode="member", user_id=BEN)
    by_email = build_flow(
        steps({"type": "action", "action": "assign", "member": "BEN@maple.in"}), TAGS, ROSTER
    )
    assert by_email.steps[0].action == Assign(mode="member", user_id=BEN)  # type: ignore[attr-defined]
    assert flows.graph(by_name)


def test_an_assign_step_can_hand_out_in_turn_or_to_nobody() -> None:
    turn = build_flow(
        steps({"type": "action", "action": "assign", "assign_to": "round_robin"}), TAGS
    )
    assert turn.steps[0].action == Assign(mode="round_robin")  # type: ignore[attr-defined]
    nobody = build_flow(steps({"type": "action", "action": "assign", "assign_to": "nobody"}), TAGS)
    assert nobody.steps[0].action == Assign(mode="nobody")  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("step", "words"),
    [
        ({"action": "assign"}, "needs assign_to"),
        ({"action": "assign", "assign_to": "member"}, "name or email"),
        ({"action": "assign", "member": "Zed"}, "no team member called"),
        ({"action": "assign", "member": "Ann"}, "More than one member"),
        ({"action": "assign", "assign_to": "nobody", "member": "Ben Das"}, "only named when"),
    ],
    ids=["nothing", "no_member", "stranger", "ambiguous", "member_with_nobody"],
)
def test_an_assign_step_that_cannot_be_built_says_why(step: dict[str, Any], words: str) -> None:
    with pytest.raises(ApiError) as caught:
        build_flow(steps({"type": "action", **step}), TAGS, ROSTER)
    assert caught.value.code == "validation_error"
    assert words in (caught.value.detail or "")
    assert caught.value.errors[0].field == "steps.0"


def test_the_stranger_message_lists_the_team() -> None:
    with pytest.raises(ApiError) as caught:
        build_flow(steps({"type": "action", "action": "assign", "member": "Zed"}), TAGS, ROSTER)
    assert "Ben Das, Ann, Ann" in (caught.value.detail or "")


def test_the_proposal_lines_name_the_member_assigned_to() -> None:
    flow = build_flow(
        steps(
            {"type": "send", "text": "Hi"},
            {"type": "action", "action": "assign", "member": "Ben Das"},
            {"type": "action", "action": "assign", "assign_to": "round_robin"},
            {"type": "action", "action": "assign", "assign_to": "nobody"},
        ),
        TAGS,
        ROSTER,
    )
    assert actions.flow_lines(flow, {BEN: "Ben Das"}) == [
        "send “Hi”",
        "assign to Ben Das",
        "assign to the next available member",
        "remove the assignee",
    ]
    assert actions.flow_lines(flow)[1] == "assign to a team member"


def overview(*, round_robin: bool, available: list[bool]) -> AssignmentOverview:
    return AssignmentOverview(
        round_robin=round_robin,
        members=[
            Assignable(
                user_id=uuid.uuid4(),
                name=f"M{i}",
                avatar_url=None,
                role="agent",
                available=ok,
                open_conversations=0,
                is_you=False,
            )
            for i, ok in enumerate(available)
        ],
    )


def test_round_robin_says_what_to_switch_on() -> None:
    flow = build_flow(
        steps({"type": "action", "action": "assign", "assign_to": "round_robin"}), TAGS
    )
    assert actions.assign_notes(flow, overview(round_robin=True, available=[True])) == []
    off = actions.assign_notes(flow, overview(round_robin=False, available=[True]))
    assert len(off) == 1
    assert "not handed out in turn yet" in off[0]
    nobody = actions.assign_notes(flow, overview(round_robin=True, available=[False, False]))
    assert len(nobody) == 1
    assert "Nobody is available" in nobody[0]
    both = actions.assign_notes(flow, overview(round_robin=False, available=[]))
    assert len(both) == 2


def test_only_a_round_robin_step_needs_the_notes() -> None:
    member = build_flow(
        steps({"type": "action", "action": "assign", "member": "Ben Das"}), TAGS, ROSTER
    )
    assert actions.assign_notes(member, overview(round_robin=False, available=[])) == []


def test_the_tool_schema_offers_assign() -> None:
    schema = ProposedStep.model_json_schema()
    offered = schema["properties"]["action"]["anyOf"][0]["enum"]
    assert "assign" in offered
    assert schema["properties"]["assign_to"]["anyOf"][0]["enum"] == [
        "member",
        "round_robin",
        "nobody",
    ]
    assert "member" in schema["properties"]


def test_two_steps_with_the_same_id_are_refused() -> None:
    with pytest.raises(ApiError):
        build_flow(steps({"id": "a", "type": "end"}, {"id": "a", "type": "end"}), TAGS)


def test_the_tool_inputs_are_strict_and_capped() -> None:
    with pytest.raises(ValidationError):
        ProposeFlowInput.model_validate({"request": "x", "steps": [], "sql": "drop"})
    with pytest.raises(ValidationError):
        ProposeFlowInput.model_validate({"request": "x", "steps": [{"type": "end"}] * 31})
    with pytest.raises(ValidationError):
        ProposedStep.model_validate({"type": "send", "text": "x" * 1001})
    with pytest.raises(ValidationError):
        ProposeSegmentInput.model_validate({"name": "n", "tags": ["t"] * 11})
    for model in (ProposeFlowInput, ProposeSegmentInput):
        assert model.model_json_schema()["type"] == "object"  # for the planner


# ---------------------------------------------------------------- the registry


def test_proposal_tools_are_drafts_for_admins_and_broadcasts_are_not_offered() -> None:
    load_tools()
    for name in ("propose_flow", "propose_segment"):
        spec = registry.get(name)
        assert spec is not None
        assert (spec.tier, spec.release, spec.min_role) == (RiskTier.DRAFT, Release.R1, Role.ADMIN)
    broadcast = registry.get(actions.BROADCAST_TOOL)
    assert broadcast is not None
    assert broadcast.release == Release.R2
    offered = {s.name for s in registry.available(release=CURRENT_RELEASE, role=Role.OWNER)}
    assert {"propose_flow", "propose_segment"} <= offered
    assert actions.BROADCAST_TOOL not in offered
    agent_role = {s.name for s in registry.available(release=CURRENT_RELEASE, role=Role.AGENT)}
    assert not {"propose_flow", "propose_segment"} & agent_role


def test_every_action_has_a_tool_and_a_role() -> None:
    load_tools()
    assert set(actions.ACTIONS) == {actions.FLOW_TOOL, actions.SEGMENT_TOOL}
    for tool_name, spec in actions.ACTIONS.items():
        assert registry.get(tool_name) is not None
        assert actions.required_role(spec) == Role.ADMIN  # both screens are for owners and admins
    assert "yet" in actions.UNAVAILABLE[actions.BROADCAST_TOOL]


# ---------------------------------------------------------------- the gateway refuses first


async def test_a_team_member_cannot_propose_a_write() -> None:
    args = actions.SegmentActionArgs(name="VIPs", filter=ContactFilterSpec())
    with pytest.raises(ApiError) as caught:
        await agent_actions.propose(ctx_for(Role.AGENT), actions.SEGMENT, args)
    assert caught.value.code == "forbidden"


async def test_the_broadcast_slot_is_refused_with_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(actions.UNAVAILABLE, actions.SEGMENT_TOOL, "Not yet.")
    args = actions.SegmentActionArgs(name="x", filter=ContactFilterSpec())
    with pytest.raises(ApiError) as caught:
        await agent_actions.propose(ctx_for(Role.OWNER), actions.SEGMENT, args)
    assert caught.value.code == "conflict"
    assert caught.value.detail == "Not yet."


async def test_a_proposal_needs_the_step_that_makes_it() -> None:
    args = actions.SegmentActionArgs(name="x", filter=ContactFilterSpec())
    with pytest.raises(RuntimeError, match="step"):
        await agent_actions.propose(ctx_for(Role.OWNER, step=False), actions.SEGMENT, args)


# ---------------------------------------------------------------- words and vocabulary


def test_a_filter_reads_in_plain_words() -> None:
    spec = ContactFilterSpec(
        tag_ids=[VIP],
        has_email=True,
        stages=["qualified", "follow_up"],
        inactive_for_days=30,
        fields=["city:pune", "size:*"],
    )
    lines = actions.filter_lines(spec, {VIP: "vip"})
    assert lines == [
        "Has the tag vip",
        "Has an email",
        "Lead stage is qualified or follow up",
        "No activity for 30 days or more",
        "city is pune",
        "size is filled in",
    ]
    assert actions.filter_lines(ContactFilterSpec(), {}) == ["Everyone"]


def test_the_stored_and_api_names_agree() -> None:
    assert set(get_args(ApprovalStatusName)) == set(ApprovalStatus)
    assert set(get_args(ApprovalListStatus)) == set(ApprovalStatus) | {"all"}
    assert set(get_args(ApprovalEventName)) == set(AgentApprovalEventKind)


def test_an_approval_expires_after_a_day() -> None:
    assert APPROVAL_TTL.total_seconds() == 24 * 3600
