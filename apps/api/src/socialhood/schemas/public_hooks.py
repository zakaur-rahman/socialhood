"""REST hooks for Zapier triggers (GR-26): subscribe, list and the one-time signing secret."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

TriggerName = Literal["new_contact", "lead_captured", "tag_added", "new_message", "run_completed"]
HookStatusName = Literal["active", "paused", "disabled"]


class HookSubscribe(RequestModel):
    trigger: TriggerName
    target_url: str = Field(min_length=8, max_length=2000)  # https; checked further when saved


class Hook(ResponseModel):
    id: uuid.UUID
    trigger: TriggerName
    target_url: str
    status: HookStatusName
    created_at: datetime


class HookSubscribed(Hook):
    """Subscribe only: the secret the deliveries are signed with (Standard Webhooks)."""

    signing_secret: str


class HookList(ResponseModel):
    items: list[Hook]
