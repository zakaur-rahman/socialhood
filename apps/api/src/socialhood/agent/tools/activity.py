"""Ask Social Hood's activity tool (GR-05): list_recent_failures, for "what's failing?" and "why
didn't my automation reply?". Owners and admins, like the Activity page. Reasons are the page's
plain sentences; no payloads, no message text."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.tools.common import clip, tool, when
from socialhood.models.identity import Role
from socialhood.services.activity import feed

SHOWN = 10


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListRecentFailuresInput(_Input):
    automation_id: uuid.UUID | None = Field(
        default=None, description="Only this automation's failures."
    )


class FailureLine(BaseModel):
    kind: str  # automation_run, flow_step, message, webhook_delivery, account
    what_happened: str
    reason: str | None = None
    what_to_do: str | None = None  # the one action, in words ("Reconnect Instagram")
    can_retry: bool
    at: datetime
    at_label: str | None = None


class RecentFailuresResult(ToolResult):
    failures: list[FailureLine]


@tool(
    name="list_recent_failures",
    label="Checking what failed",
    description=(
        "The latest failures on the Activity page: automation runs that failed, messages that "
        "weren't sent, webhook deliveries that failed and accounts that need reconnecting, each "
        "with its plain reason and what to do. For 'what's failing?' or 'why didn't my "
        "automation reply?'."
    ),
    input_model=ListRecentFailuresInput,
    result_model=RecentFailuresResult,
    min_role=Role.ADMIN,
)
async def list_recent_failures(
    ctx: ToolContext, args: ListRecentFailuresInput
) -> RecentFailuresResult:
    page = await feed.feed(
        ctx.session,
        failures_only=True,
        kind=None,
        automation_id=args.automation_id,
        account_id=None,
        cursor=None,
        limit=SHOWN,
    )
    lines = [
        FailureLine(
            kind=item.kind,
            what_happened=item.title,
            reason=clip(item.reason, 300),
            what_to_do="Retry"
            if item.retryable and item.action is None
            else (item.action.label if item.action else None),
            can_retry=item.retryable,
            at=item.occurred_at,
            at_label=when(ctx, item.occurred_at),
        )
        for item in page.items
    ]
    count = f"{len(lines)} recent failure{'' if len(lines) == 1 else 's'}"
    more = (
        ["There are older failures too; the Activity page lists them all."]
        if page.next_cursor
        else []
    )
    return RecentFailuresResult(
        summary=clip(count if lines else "Nothing has failed recently.", 300) or count,
        failures=lines,
        caveats=more,
    )
