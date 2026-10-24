"""The flow editor's dry run (GR-13): the steps one run of a saved flow would take, as the contact
would meet them. Pure: no database, no clock, nothing sent.

A run follows one path through the graph. At a fork (a message with quick replies, a question, a
branch, a split) ``choices`` says which way to go, one number per fork in order, 0 where none is
given; the result names every way on (``exits``) and the one taken (``picked``), so the Test tab
can offer the others. Messages and questions are rendered with the sample name, then the
disclosure line, as the runtime sends them. A broken graph has no path (activation reports it).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from socialhood.schemas.automations import FlowPreviewStep
from socialhood.schemas.flows import (
    ActionStep,
    AddTag,
    AiReplyStep,
    AskStep,
    Assign,
    BranchStep,
    DelayStep,
    FlowDefinition,
    HandOff,
    NotifyTeam,
    ProductStep,
    RandomizeStep,
    RemoveTag,
    SendStep,
    SetField,
    Step,
)
from socialhood.services.automations import flows, render

ASK_TITLES = {"text": "Ask a question", "email": "Ask for an email", "phone": "Ask for a phone"}


def _action_title(step: ActionStep, tag_names: Mapping[uuid.UUID, str]) -> str:
    match step.action:
        case AddTag(tag_id=tag_id):
            return f"Add the tag {tag_names.get(tag_id, 'a tag')}"
        case RemoveTag(tag_id=tag_id):
            return f"Remove the tag {tag_names.get(tag_id, 'a tag')}"
        case SetField(key=key, value=value):
            return f"Set {key} to {value}"
        case NotifyTeam():
            return "Notify the team"
        case HandOff():
            return "Hand off to a person"
        case Assign(mode=mode):
            return {
                "member": "Assign to a team member",
                "round_robin": "Assign to the next available member",
                "nobody": "Remove the assignee",
            }[mode]


def _delay_title(seconds: int) -> str:
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"Wait {hours} hour{'' if hours == 1 else 's'}"
    minutes = max(1, round(seconds / 60))
    return f"Wait {minutes} minute{'' if minutes == 1 else 's'}"


def title(step: Step, tag_names: Mapping[uuid.UUID, str]) -> str:
    match step:
        case SendStep():
            return "Message"
        case ProductStep():
            return "Send a product"
        case AskStep():
            return ASK_TITLES[step.expect]
        case BranchStep():
            return "Branch"
        case ActionStep():
            return _action_title(step, tag_names)
        case DelayStep():
            return _delay_title(step.seconds)
        case RandomizeStep():
            return "Split"
        case AiReplyStep():
            return "AI reply"
        case _:
            return "End"


def preview(
    definition: FlowDefinition,
    *,
    choices: Sequence[int] = (),
    first_name: str | None,
    username: str | None,
    disclosure: str | None,
    tag_names: Mapping[uuid.UUID, str] | None = None,
) -> list[FlowPreviewStep]:
    names = tag_names or {}
    try:
        g = flows.graph(definition)
    except flows.FlowError:
        return []
    remaining = list(choices)
    out: list[FlowPreviewStep] = []
    step_id: str | None = definition.start
    while step_id is not None:
        step = g.by_id[step_id]
        targets = flows.successors(step)
        exits = flows.exit_labels(step, names) if len(targets) > 1 else []
        picked = None
        following: str | None = targets[0] if targets else None
        if len(targets) > 1:
            picked = min(remaining.pop(0) if remaining else 0, len(targets) - 1)
            following = targets[picked]
        text = None
        if isinstance(step, SendStep | AskStep) and step.text.strip():
            text = render.with_disclosure(
                render.render(step.text, first_name=first_name, username=username), disclosure
            )
        out.append(
            FlowPreviewStep(
                step_id=step.id,
                kind=step.type,
                title=title(step, names),
                text=text,
                buttons=[b.title for b in step.buttons] if isinstance(step, SendStep) else [],
                quick_replies=(
                    [q.title for q in step.quick_replies] if isinstance(step, SendStep) else []
                ),
                exits=exits,
                picked=picked,
            )
        )
        step_id = following
    return out
