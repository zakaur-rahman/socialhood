"""Ask Amplychat's sequences tool (GR-24): list_sequences, for "which follow-ups are running?" and
"why did Priya stop getting them?". Owners and admins, like Automations. Read-only: what each
sequence is, how many people are in it, and the latest skips and stops with their reasons. Never a
message body."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.tools.common import clip, tool
from socialhood.models.identity import Role
from socialhood.services.sequences import service


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListSequencesInput(_Input):
    status: str | None = Field(
        default=None, max_length=10, description="draft, active or paused; leave out for all."
    )


class SequenceLine(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    account: str | None = None
    starts_when: str  # "A tag is added: VIP"
    steps: int
    people_in: int
    completed: int
    stopped: int
    stops_on: list[str]  # "a reply", "the tag VIP", "the lead stage Won"
    problems: list[str]


class SequencesResult(ToolResult):
    sequences: list[SequenceLine]


def _stops(
    stop_on_reply: bool, tag_names: list[str], stages: list[str], removed_tag_names: list[str]
) -> list[str]:
    found = ["a reply"] if stop_on_reply else []
    found += [f"the tag {name}" for name in tag_names]
    found += [f"the tag {name} being removed" for name in removed_tag_names]
    found += [f"the lead stage {stage.replace('_', ' ')}" for stage in stages]
    return found


@tool(
    name="list_sequences",
    label="Checking the sequences",
    description=(
        "The workspace's sequences (timed follow-up messages): each one's status, what starts "
        "it, how many steps, how many people are in it, finished or stopped, and what stops it. "
        "For questions like 'which follow-ups are running?'."
    ),
    input_model=ListSequencesInput,
    result_model=SequencesResult,
    min_role=Role.ADMIN,
)
async def list_sequences(ctx: ToolContext, args: ListSequencesInput) -> SequencesResult:
    listed = await service.list_out(ctx.session)
    rows = [s for s in listed.items if args.status in (None, s.status)]
    lines = [
        SequenceLine(
            id=s.id,
            name=s.name,
            status=s.status,
            account=s.account_label,
            starts_when=s.entry.label,
            steps=s.step_count,
            people_in=s.enrolments.active,
            completed=s.enrolments.completed,
            stopped=s.enrolments.stopped,
            stops_on=_stops(
                s.stop.on_reply, s.stop.tag_names, list(s.stop.stages), s.stop.removed_tag_names
            ),
            problems=s.problems,
        )
        for s in rows
    ]
    running = sum(1 for line in lines if line.status == "active")
    count = f"{len(lines)} sequence{'' if len(lines) == 1 else 's'}"
    summary = f"{count}, {running} running" if lines else "No sequences yet"
    return SequencesResult(
        summary=clip(summary, 300) or summary,
        sequences=lines,
        caveats=[f"“{line.name}” can't run: {line.problems[0]}" for line in lines if line.problems],
    )
