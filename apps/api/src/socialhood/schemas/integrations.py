"""Outbound webhooks (GR-04): endpoints, deliveries and the event catalogue."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

EventName = Literal[
    "contact.created",
    "contact.updated",
    "contact.tagged",
    "lead.captured",
    "lead.stage_changed",
    "message.received",
    "conversation.assigned",
    "automation.run.completed",
    "broadcast.finished",
    "order.created",
    "order.paid",
    "order.refunded",
    "sequence.enrolled",
    "sequence.step_sent",
    "sequence.completed",
    "sequence.stopped",
]
EndpointStatusName = Literal["active", "paused", "disabled"]
DeliveryStatusName = Literal["pending", "succeeded", "failed"]


class WebhookEventType(ResponseModel):
    type: EventName
    version: int
    description: str
    emitted: bool  # false until the feature that raises it exists


class WebhookEventTypeList(ResponseModel):
    items: list[WebhookEventType]


class WebhookEndpointCreate(RequestModel):
    url: str = Field(min_length=8, max_length=2000)  # https; checked further when saved
    description: str | None = Field(default=None, max_length=100)
    events: list[EventName] = Field(min_length=1, max_length=20)


class WebhookEndpointPatch(RequestModel):
    url: str | None = Field(default=None, min_length=8, max_length=2000)
    description: str | None = Field(default=None, max_length=100)
    events: list[EventName] | None = Field(default=None, min_length=1, max_length=20)
    # Turning a paused or disabled endpoint on starts its failure count again.
    status: Literal["active", "paused"] | None = None


class WebhookEndpoint(ResponseModel):
    id: uuid.UUID
    url: str
    description: str | None = None
    events: list[EventName]
    status: EndpointStatusName
    failing_deliveries: int
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    disabled_at: datetime | None = None
    created_at: datetime


class WebhookEndpointWithSecret(WebhookEndpoint):
    """Create and rotate: the signing secret, shown this once (Standard Webhooks, whsec_…)."""

    signing_secret: str


class WebhookEndpointList(ResponseModel):
    items: list[WebhookEndpoint]
    limit: int | None = None  # the plan's webhook_endpoints; None means no limit


class WebhookDelivery(ResponseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_id: uuid.UUID
    event_type: str
    status: DeliveryStatusName
    attempts: int
    response_code: int | None = None
    duration_ms: int | None = None
    error: str | None = None
    next_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    replay_of_id: uuid.UUID | None = None
    created_at: datetime
    payload: dict[str, Any]


class WebhookDeliveryList(ResponseModel):
    items: list[WebhookDelivery]
    next_cursor: str | None = None
