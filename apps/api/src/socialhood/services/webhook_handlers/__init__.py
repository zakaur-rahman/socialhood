"""One handler per webhook provider (TR-WH-05). Each module exposes
``async def handle(session, event) -> Outcome``; services/webhook_processing.py dispatches."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.platform import WebhookEvent


@dataclass(frozen=True)
class Outcome:
    status: Literal["processed", "ignored"]
    reason: str | None = None
    workspace_id: uuid.UUID | None = None


Handler = Callable[[AsyncSession, WebhookEvent], Awaitable[Outcome]]
