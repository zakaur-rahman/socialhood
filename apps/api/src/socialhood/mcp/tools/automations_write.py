"""Automations writes (01-design.md §4.1, §4.4): pause_automation and resume_automation.

- **Pause** stops an automation now, which stops its customer replies; pausing is the safe
  direction, so it goes directly. Pausing one that isn't live changes nothing.
- **Resume** turns back on an automation that **was live before**. A draft that never went live is
  refused ("Activate it in Amplychat first"): a first activation stays a human decision in the
  app. Resuming runs the app's own activation (its validation and the plan's active-automation
  limit), and restarts a private-reply queue it held, as the app does. It messages customers
  again, so it is previewed first (mcp/confirmations.py): the activation runs in a savepoint and
  is rolled back.

Neither uses the dedupe window: the two undo each other, so an identical resend a minute later
must run, not replay the earlier result. Each call is idempotent by itself (pausing a paused
automation, resuming a live one), and an ``idempotency_key`` makes a retry replay.
"""

from __future__ import annotations

import uuid

from pydantic import Field

from socialhood.errors import ApiError
from socialhood.mcp import confirmations
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import (
    Access,
    ConfirmedInput,
    WriteInput,
    WriteOutput,
    registry,
    tool,
)
from socialhood.models.automations import AutomationStatus
from socialhood.models.identity import Role
from socialhood.realtime import events
from socialhood.services.automations import definitions, queue


class AutomationIdInput(WriteInput):
    automation_id: uuid.UUID = Field(description="From list_automations.")


class ResumeAutomationInput(ConfirmedInput):
    automation_id: uuid.UUID = Field(description="From list_automations.")


class AutomationStateResult(WriteOutput):
    automation_id: uuid.UUID
    name: str
    status: str  # draft, active, paused
    changed: bool
    next_step: str | None = None
    dashboard_url: str | None = None


NEVER_LIVE = (
    "This automation has never been live, so it can't be resumed from here. Open it in "
    "Amplychat and activate it there."
)


@tool(
    registry,
    name="pause_automation",
    title="Pause an automation",
    description=(
        "Pause a live automation now, so it stops replying to customers. Its settings are kept "
        "and it can be resumed. Pausing one that is not live changes nothing. Part of Creator and "
        "Business."
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


@tool(
    registry,
    name="resume_automation",
    title="Resume an automation",
    description=(
        "Turn a paused automation back on. Only an automation that was live before can be "
        "resumed; a draft that never went live is activated in Amplychat. It is checked and "
        "limited as when activating in the app. Once on, it messages the people who match, so "
        "it is previewed first: show the member the preview and call again only after they "
        "agree, with confirmed true and its confirmation_token. Part of Creator and Business."
    ),
    input_model=ResumeAutomationInput,
    output_model=AutomationStateResult,
    scope="automations:write",
    access=Access.WRITE,
    min_role=Role.ADMIN,
    open_world=True,
)
async def resume_automation(call: ToolCall, args: ResumeAutomationInput) -> AutomationStateResult:
    current = await definitions.get_or_404(call.session, args.automation_id, for_update=True)
    url = call.dashboard_url(f"automations/{current.id}")
    if current.status == AutomationStatus.ACTIVE:
        return AutomationStateResult(
            summary=f"“{current.name}” is already live",
            automation_id=current.id,
            name=current.name,
            status=current.status,
            changed=False,
            dashboard_url=url,
        )
    if current.activated_at is None:
        raise ApiError("conflict", NEVER_LIVE + (f" {url}" if url else ""))
    if args.confirmed:
        confirmations.require(call, args, args.confirmation_token)
    was = current.status
    savepoint = None if args.confirmed else await call.session.begin_nested()
    automation = await definitions.activate(
        call.session,
        current.id,
        plan=call.plan,
        disclosure=call.workspace.automation_disclosure,
        now=call.now,
    )
    if savepoint is not None:
        result = AutomationStateResult(
            summary=f"Preview: “{automation.name}” would go live again and message the people who "
            "match. Nothing is changed yet",
            automation_id=automation.id,
            name=automation.name,
            status=was,
            changed=False,
            preview=True,
            confirmation_token=confirmations.issue(call, args),
            next_step=confirmations.next_step("resume it"),
            dashboard_url=url,
        )
        await savepoint.rollback()
        events.discard(call.session)
        return result
    call.note("automation.resumed", "automation", automation.id)
    account_id, workspace_id = automation.social_account_id, call.workspace.id
    waiting = bool(account_id) and await queue.automation_waiting(call.session, automation.id)
    if account_id is not None and waiting:

        async def drain() -> None:
            await queue.enqueue_drain(account_id, workspace_id)

        call.after_commit.append(drain)
    return AutomationStateResult(
        summary=f"Resumed “{automation.name}”. It is live again",
        automation_id=automation.id,
        name=automation.name,
        status=automation.status,
        changed=True,
        dashboard_url=url,
    )
