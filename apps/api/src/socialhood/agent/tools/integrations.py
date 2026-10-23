"""Ask Social Hood's integrations tool (GR-04): list_webhook_endpoints, for "is my Zapier hook
working?". Owners and admins, like Settings, Integrations. Never the signing secret."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.tools.common import clip, tool, when
from socialhood.models.identity import Role
from socialhood.services.webhooks import endpoints as service


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListWebhookEndpointsInput(_Input):
    pass


class EndpointLine(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    status: str  # active, paused, disabled (turned off after repeated failures)
    events: list[str]
    failing_deliveries: int  # deliveries in a row that ran out of attempts
    last_success_at: datetime | None = None
    last_success_label: str | None = None
    last_failure_at: datetime | None = None
    last_failure_label: str | None = None


class WebhookEndpointsResult(ToolResult):
    endpoints: list[EndpointLine]


@tool(
    name="list_webhook_endpoints",
    label="Checking the integrations",
    description=(
        "The workspace's webhook endpoints (Settings, Integrations): each one's address, the "
        "events it receives, whether it's on, and when it last delivered or failed. For "
        "questions like 'is my Zapier webhook working?'."
    ),
    input_model=ListWebhookEndpointsInput,
    result_model=WebhookEndpointsResult,
    min_role=Role.ADMIN,
)
async def list_webhook_endpoints(
    ctx: ToolContext, args: ListWebhookEndpointsInput
) -> WebhookEndpointsResult:
    listed = await service.list_endpoints(ctx.session)
    lines = [
        EndpointLine(
            id=e.id,
            name=e.description or e.url,
            url=e.url,
            status=e.status,
            events=list(e.events),
            failing_deliveries=e.failing_deliveries,
            last_success_at=e.last_success_at,
            last_success_label=when(ctx, e.last_success_at),
            last_failure_at=e.last_failure_at,
            last_failure_label=when(ctx, e.last_failure_at),
        )
        for e in listed.items
    ]
    off = [line for line in lines if line.status == "disabled"]
    caveats = [f"“{line.name}” was turned off after repeated failures." for line in off]
    count = f"{len(lines)} webhook endpoint{'' if len(lines) == 1 else 's'}"
    return WebhookEndpointsResult(
        summary=clip(count + (f", {len(off)} turned off" if off else ""), 300) or count,
        endpoints=lines,
        caveats=caveats,
    )
