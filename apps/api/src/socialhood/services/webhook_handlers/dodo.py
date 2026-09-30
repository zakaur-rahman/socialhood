"""Dodo webhook events (T8.3; TR-BIL-02, TR-WH-05).

Route the stored event to its workspace (webhooks/dodo_routing.py: the checkout's
``metadata.workspace_id``, else the stored ``dodo_subscription_id``), then apply it in that
workspace's scope with billing/lifecycle.apply_event. An event for no known workspace, of a type
we don't act on, or older than the subscription's last_event_at is ``ignored`` with the reason.
Only events that passed the signature check at intake are stored, so only they get here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing import lifecycle
from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.services.webhook_handlers import Outcome
from socialhood.settings import get_settings
from socialhood.webhooks.dodo_routing import resolve_workspace


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    workspace_id = await resolve_workspace(session, event.payload)
    if workspace_id is None:
        return Outcome("ignored", "no workspace for this event")
    with workspace_scope(workspace_id):
        applied = await lifecycle.apply_event(
            session, event, now=datetime.now(UTC), settings=get_settings()
        )
    if applied.changed:
        return Outcome("processed", workspace_id=workspace_id)
    return Outcome("ignored", applied.reason, workspace_id)
