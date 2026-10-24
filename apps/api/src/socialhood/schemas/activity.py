"""The Activity page (GR-05): one merged list of what ran, what failed and why."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from socialhood.schemas.common import ResponseModel

ActivityKindName = Literal[
    "automation_run", "flow_step", "message", "webhook_delivery", "account", "broadcast"
]
ActivityOutcome = Literal["ok", "failed", "partial", "skipped", "attention"]


class ActivityAction(ResponseModel):
    """The one thing to do about it: a link inside the workspace ("/settings/connections")."""

    label: str
    href: str


class ActivityRetry(ResponseModel):
    """Where a safe retry goes: the web posts to the message's retry route, or the webhook
    delivery's replay route, with ``target_id``."""

    kind: Literal["message", "webhook_delivery"]
    target_id: uuid.UUID


class ActivityItem(ResponseModel):
    id: uuid.UUID  # the row it comes from; unique within its kind
    kind: ActivityKindName
    outcome: ActivityOutcome
    occurred_at: datetime
    title: str  # what happened
    reason: str | None = None  # why, in a sentence
    error_code: str | None = None
    automation_id: uuid.UUID | None = None
    automation_name: str | None = None
    social_account_id: uuid.UUID | None = None
    account_label: str | None = None
    platform: str | None = None
    action: ActivityAction | None = None
    retryable: bool = False
    retry: ActivityRetry | None = None


class ActivityList(ResponseModel):
    items: list[ActivityItem]
    next_cursor: str | None = None
