"""Dodo webhook events (T8.3; TR-BIL-02, TR-WH-05).

Route the stored event to its workspace (webhooks/dodo_routing.py: the checkout's
``metadata.workspace_id``, else the stored ``dodo_subscription_id``), then apply it in that
workspace's scope with billing/lifecycle.apply_event. An event for no known workspace, of a type
we don't act on, or older than the subscription's last_event_at is ``ignored`` with the reason.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.platform import WebhookEvent
from socialhood.services.webhook_handlers import Outcome


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    raise NotImplementedError("T8.3")
