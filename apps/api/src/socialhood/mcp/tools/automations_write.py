"""Automations writes (01-design.md §4.1, §4.4): pause_automation.

Pausing stops an automation now, which stops its customer replies. Like the other automation
writes it is previewed first (mcp/confirmations.py): the first call changes nothing and returns a
``confirmation_token``, and the pause needs ``confirmed: true`` with that token. Pausing one that
isn't live changes nothing and needs no preview. Turning one on is activate_automation
(tools/automations_create.py).

It uses no dedupe window: a person may turn the automation back on, and an identical pause a minute
later must then run, not replay the earlier result. Pausing a paused automation is idempotent by
itself, and an ``idempotency_key`` makes a retry replay.
"""

from __future__ import annotations

import uuid

from pydantic import Field

from socialhood.mcp import confirmations
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import Access, ConfirmedInput, WriteOutput, registry, tool
from socialhood.models.automations import AutomationStatus
from socialhood.models.identity import Role
from socialhood.services.automations import definitions


class AutomationIdInput(ConfirmedInput):
    automation_id: uuid.UUID = Field(description="From list_automations.")


class AutomationStateResult(WriteOutput):
    automation_id: uuid.UUID
    name: str
    status: str  # draft, active, paused (what it would be, in a preview)
    changed: bool
    next_step: str | None = None
    dashboard_url: str | None = None


@tool(
    registry,
    name="pause_automation",
    title="Pause an automation",
    description=(
        "Pause a live automation, so it stops replying to customers. Its settings are kept, and "
        "it can be turned back on with activate_automation or in Amplychat. Previewed first: "
        "show the member the preview and call again only after they agree, with confirmed true "
        "and its confirmation_token. Pausing one that is not live changes nothing. Part of "
        "Creator and Business."
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
    url = call.dashboard_url(f"automations/{before.id}")
    if was_live and not args.confirmed:
        return AutomationStateResult(
            summary=f"Preview: “{before.name}” would be paused and stop replying to customers. "
            "Nothing is changed yet",
            preview=True,
            confirmation_token=confirmations.issue(call, args),
            automation_id=before.id,
            name=before.name,
            status=AutomationStatus.PAUSED.value,
            changed=False,
            next_step=confirmations.next_step("pause it"),
            dashboard_url=url,
        )
    if was_live:
        confirmations.require(call, args, args.confirmation_token)
    automation = await definitions.pause(call.session, args.automation_id, now=call.now)
    if was_live:
        call.note("automation.paused", "automation", automation.id)
    return AutomationStateResult(
        summary=(
            f"Paused “{automation.name}”. It no longer replies to customers"
            if was_live
            else f"“{automation.name}” was not live, so nothing changed"
        )[:400],
        automation_id=automation.id,
        name=automation.name,
        status=automation.status,
        changed=was_live,
        dashboard_url=url,
    )
