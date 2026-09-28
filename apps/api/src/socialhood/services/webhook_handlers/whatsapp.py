"""WhatsApp webhook events: messages and delivery statuses (F-04, T3.12)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.platform import WebhookEvent
from socialhood.services.webhook_handlers import Outcome


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    return Outcome("ignored", "WhatsApp handling arrives with T3.12")
