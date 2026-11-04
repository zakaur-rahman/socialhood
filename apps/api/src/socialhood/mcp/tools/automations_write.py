"""Automations writes (01-design.md §4.1, §4.4): pause_automation.

Pausing stops an automation now, which stops its customer replies. It is the safe direction, so it
goes directly. Pausing one that isn't live changes nothing. Turning one on is a person's decision
in the dashboard, so no AI app tool does it.

It uses no dedupe window: a person may turn the automation back on, and an identical pause a minute
later must then run, not replay the earlier result. Pausing a paused automation is idempotent by
itself, and an ``idempotency_key`` makes a retry replay.
"""

from __future__ import annotations

import uuid

from pydantic import Field

from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import Access, WriteInput, WriteOutput, registry, tool
from socialhood.models.automations import AutomationStatus
from socialhood.models.identity import Role
from socialhood.services.automations import definitions


class AutomationIdInput(WriteInput):
    automation_id: uuid.UUID = Field(description="From list_automations.")


class AutomationStateResult(WriteOutput):
    automation_id: uuid.UUID
    name: str
    status: str  # draft, active, paused
    changed: bool
    dashboard_url: str | None = None


@tool(
    registry,
    name="pause_automation",
    title="Pause an automation",
    description=(
        "Pause a live automation now, so it stops replying to customers. Its settings are kept, "
        "and a person can turn it back on in Amplychat. Pausing one that is not live changes "
        "nothing. Part of Creator and Business."
    ),
    input_model=AutomationIdInput,
    output_model=AutomationStateResult,
    scope="automations:write",
    access=Access.WRITE,
    min_role=Role.ADMIN,
    destructive=True,
)
async def pause_automation(call: ToolCall, args: AutomationIdInput) -> AutomationStateResult:
    before = await definitions.get_or_404(call.session, args.automation_id, for_update=True)
    was_live = before.status == AutomationStatus.ACTIVE
    automation = await definitions.pause(call.session, args.automation_id, now=call.now)
    if was_live:
        call.note("automation.paused", "automation", automation.id)
    return AutomationStateResult(
        summary=(
            f"Paused “{automation.name}”. It no longer replies to customers"
            if was_live
            else f"“{automation.name}” was not live, so nothing changed"
        ),
        automation_id=automation.id,
        name=automation.name,
        status=automation.status,
        changed=was_live,
        dashboard_url=call.dashboard_url(f"automations/{automation.id}"),
    )
