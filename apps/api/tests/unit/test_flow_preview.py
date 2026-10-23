"""GR-13: the flow editor's dry run (services/automations/flow_preview) and the plan's step cap
(services/automations/flow_store.check_step_cap). Pure: no database."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from socialhood.billing.plans import ENTITLEMENTS, entitlement
from socialhood.errors import ApiError
from socialhood.schemas.flows import FlowDefinition
from socialhood.services.automations import flow_preview, flow_store, flows

TAG = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def flow(*steps: dict[str, Any]) -> FlowDefinition:
    return FlowDefinition.model_validate({"start": steps[0]["id"], "steps": list(steps)})


def send(id: str, text: str = "Hi", **kw: Any) -> dict[str, Any]:
    return {"type": "send", "id": id, "text": text, **kw}


def preview(definition: FlowDefinition, *choices: int, disclosure: str | None = None) -> list[Any]:
    return flow_preview.preview(
        definition,
        choices=choices,
        first_name="Priya",
        username="priya.shah",
        disclosure=disclosure,
        tag_names={TAG: "VIP"},
    )


CATALOGUE = flow(
    send(
        "hello",
        "Hi {first_name|there}!",
        quick_replies=[{"title": "A", "next": "a"}, {"title": "B", "next": "b"}],
    ),
    send("a", "You chose A"),
    send("b", "You chose B", next="after"),
    {"type": "action", "id": "after", "action": {"kind": "add_tag", "tag_id": str(TAG)}},
)


def test_a_walk_takes_the_first_exit_unless_told_otherwise() -> None:
    first = preview(CATALOGUE)
    assert [s.step_id for s in first] == ["hello", "a"]
    assert first[0].exits == ["Taps A", "Taps B", "Types an answer"]
    assert (first[0].picked, first[1].picked) == (0, None)
    second = preview(CATALOGUE, 1)
    assert [s.step_id for s in second] == ["hello", "b", "after"]
    assert second[2].title == "Add the tag VIP"


def test_messages_carry_the_sample_name_and_the_disclosure() -> None:
    steps = preview(CATALOGUE, disclosure="Sent automatically")
    assert steps[0].text == "Hi Priya!\n\nSent automatically"
    assert steps[0].quick_replies == ["A", "B"]


def test_a_choice_past_the_last_exit_takes_the_last() -> None:
    assert [s.step_id for s in preview(CATALOGUE, 9)] == ["hello"]  # "types an answer" ends it


def test_each_kind_has_a_plain_title() -> None:
    definition = flow(
        {"type": "ask", "id": "q", "text": "Email?", "expect": "email", "next": "w"},
        {"type": "delay", "id": "w", "seconds": 600, "next": "x"},
        {
            "type": "randomize",
            "id": "x",
            "paths": [{"weight": 1, "next": "e"}, {"weight": 3, "next": "e"}],
        },
        {"type": "end", "id": "e"},
    )
    steps = preview(definition, 0, 1)  # the question is a fork too: answer, then path B
    assert [s.title for s in steps] == ["Ask for an email", "Wait 10 minutes", "Split", "End"]
    assert steps[2].exits == ["Path A (1)", "Path B (3)"]
    assert steps[2].picked == 1


def test_a_broken_graph_has_no_path() -> None:
    broken = flow(send("a", next="b"))
    assert preview(broken) == []


def test_exit_labels_follow_the_successors() -> None:
    definition = flow(
        {
            "type": "branch",
            "id": "b",
            "rules": [
                {"when": {"kind": "tag", "tag_id": str(TAG)}, "next": "m"},
                {"when": {"kind": "follows_business", "follows": False}, "next": "m"},
            ],
        },
        send("m"),
    )
    step = definition.steps[0]
    labels = flows.exit_labels(step, {TAG: "VIP"})
    assert labels == ["Has the tag VIP", "Doesn't follow you", "Otherwise"]
    assert len(labels) == len(flows.successors(step))


def test_the_free_plan_caps_the_steps_and_every_plan_can_branch() -> None:
    assert ENTITLEMENTS["flow_steps"] == {"free": 5, "pro": 50, "max": 50}
    assert flow_store.step_cap("free") == 5
    five = flow(*[send(f"s{i}", next=f"s{i + 1}") for i in range(4)], send("s4"))
    flow_store.check_step_cap(five, "free")
    six = flow(*[send(f"s{i}", next=f"s{i + 1}") for i in range(5)], send("s5"))
    with pytest.raises(ApiError) as raised:
        flow_store.check_step_cap(six, "free")
    assert raised.value.code == "quota_exceeded"
    assert raised.value.plan_limit is not None
    assert (raised.value.plan_limit.entitlement, raised.value.plan_limit.limit) == ("flow_steps", 5)
    flow_store.check_step_cap(six, "pro")
    assert entitlement("pro", "flow_steps") == 50
