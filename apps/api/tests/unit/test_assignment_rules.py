"""GR-20: the assignment rules that need no database: who may assign whom, round-robin turns, the
words of the note in the thread, the flow action's checks, and the notification's channels."""

from __future__ import annotations

import uuid

import pytest

from socialhood.models.identity import DEFAULT_NOTIFICATION_PREFS, Role
from socialhood.models.notifications import (
    PUSH_EVENT_OF_TYPE,
    NotificationType,
    PushEvent,
)
from socialhood.schemas.flows import ActionStep, Assign, FlowDefinition, SendStep
from socialhood.services import assignment
from socialhood.services.automations import flows
from socialhood.services.notifications import channels_for

A, B, C = (uuid.UUID(int=n) for n in (1, 2, 3))


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN])
@pytest.mark.parametrize("current", [None, A, B])
@pytest.mark.parametrize("target", [None, A, B])
def test_owners_and_admins_assign_anything(
    role: Role, current: uuid.UUID | None, target: uuid.UUID | None
) -> None:
    assert assignment.may_assign(role, A, current, target)


def test_agents_take_release_and_hand_on_their_own() -> None:
    agent = Role.AGENT
    assert assignment.may_assign(agent, A, None, A)  # take a free one
    assert assignment.may_assign(agent, A, A, None)  # release
    assert assignment.may_assign(agent, A, A, B)  # hand on
    assert not assignment.may_assign(agent, A, None, B)  # give out a free one
    assert not assignment.may_assign(agent, A, B, A)  # take from a colleague
    assert not assignment.may_assign(agent, A, B, None)
    assert not assignment.may_assign(agent, A, B, C)


def test_the_next_available_member_takes_the_turn() -> None:
    everyone = [A, B, C]
    assert assignment.next_in_turn(everyone, {A, B, C}, None) == A
    assert assignment.next_in_turn(everyone, {A, B, C}, A) == B
    assert assignment.next_in_turn(everyone, {A, B, C}, C) == A  # wraps round


def test_a_member_who_is_away_is_skipped_and_nobody_available_is_none() -> None:
    everyone = [A, B, C]
    assert assignment.next_in_turn(everyone, {A, C}, A) == C
    assert assignment.next_in_turn(everyone, {A}, A) == A  # the only one left
    assert assignment.next_in_turn(everyone, {B}, B) == B
    assert assignment.next_in_turn(everyone, set(), A) is None


def test_the_member_whose_turn_it_was_going_away_does_not_stall_the_turn() -> None:
    # B had the last turn and is now away: the turn goes on to C, not back to A.
    assert assignment.next_in_turn([A, B, C], {A, C}, B) == C
    # A cursor for a member who has left starts again from the first.
    assert assignment.next_in_turn([A, B], {A, B}, C) == A


def test_the_turns_are_fair_over_many_assignments() -> None:
    everyone, last, counts = [A, B, C], None, {A: 0, B: 0, C: 0}
    for _ in range(9):
        last = assignment.next_in_turn(everyone, set(everyone), last)
        assert last is not None
        counts[last] += 1
    assert counts == {A: 3, B: 3, C: 3}


@pytest.mark.parametrize(
    ("via", "target", "previous", "self_assigned", "expected"),
    [
        ("member", "Priya", None, False, "Sam assigned this to Priya"),
        ("member", "Sam", None, True, "Sam took this conversation"),
        ("member", None, "Priya", False, "Sam removed Priya from this conversation"),
        ("member", None, None, False, "Sam removed the assignee from this conversation"),
        ("round_robin", "Priya", None, False, "Assigned to Priya (round-robin)"),
        ("automation", "Priya", None, False, "An automation assigned this to Priya"),
        ("automation", None, "Priya", False, "An automation removed the assignee"),
    ],
)
def test_the_note_in_the_thread(
    via: assignment.Via,
    target: str | None,
    previous: str | None,
    self_assigned: bool,
    expected: str,
) -> None:
    text = assignment.note_text(
        via, actor="Sam", previous=previous, target=target, self_assigned=self_assigned
    )
    assert text == expected


def flow_with(action: Assign) -> FlowDefinition:
    return FlowDefinition(
        start="a",
        steps=[
            SendStep(id="a", text="Hi", next="b"),
            ActionStep(id="b", action=action),
        ],
    )


def errors_for(action: Assign, members: frozenset[uuid.UUID] = frozenset()) -> dict[str, str]:
    ctx = flows.Context(trigger="dm_keyword", disclosure=None, member_ids=members)
    return {e.field: e.message for e in flows.activation_errors(flow_with(action), ctx)}


def test_a_flow_can_assign_to_a_member_in_the_team() -> None:
    assert errors_for(Assign(mode="member", user_id=A), frozenset({A})) == {}


def test_a_flow_that_assigns_to_a_member_must_name_one_who_is_on_the_team() -> None:
    assert errors_for(Assign(mode="member")) == {
        "flow.steps.1.action.user_id": flows.COPY["member_needed"]
    }
    assert errors_for(Assign(mode="member", user_id=A), frozenset({B})) == {
        "flow.steps.1.action.user_id": flows.COPY["member_missing"]
    }


@pytest.mark.parametrize("mode", ["round_robin", "nobody"])
def test_the_other_modes_need_no_member(mode: str) -> None:
    assert errors_for(Assign(mode=mode)) == {}  # type: ignore[arg-type]


def test_an_assigned_conversation_follows_the_needs_you_switch() -> None:
    assert PUSH_EVENT_OF_TYPE[NotificationType.CONVERSATION_ASSIGNED] == PushEvent.NEEDS_YOU
    on = DEFAULT_NOTIFICATION_PREFS
    off = {**on, "push": {**on["push"], "needs_you": False}}
    assert channels_for("conversation_assigned", role="agent", prefs=on) == ["in_app", "push"]
    assert channels_for("conversation_assigned", role="agent", prefs=off) == ["in_app"]
