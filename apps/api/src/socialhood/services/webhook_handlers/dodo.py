"""Dodo webhook events (T8.3; TR-BIL-02, TR-WH-05).

Route the stored event to its workspace (webhooks/dodo_routing.py: the checkout's
``metadata.workspace_id``, else the stored ``dodo_subscription_id``), then apply it in that
workspace's scope with billing/lifecycle.apply_event. An event for no known workspace, of a type
we don't act on, or older than the subscription's last_event_at is ``ignored`` with the reason.
Only events that passed the signature check at intake are stored, so only they get here.

A live subscription whose workspace was deleted or is being deleted (a checkout paid after the
deletion, say) would otherwise bill forever: it raises an alert and queues
``cancel_orphan_subscription``, which cancels it in Dodo at once and retries while Dodo fails.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing import lifecycle
from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.observability.logging import get_logger
from socialhood.services.webhook_handlers import Outcome
from socialhood.settings import get_settings
from socialhood.webhooks.dodo_routing import orphaned_subscription, resolve_workspace

log = get_logger(__name__)

ORPHAN_CANCEL_TASK = "cancel_orphan_subscription"


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    workspace_id = await resolve_workspace(session, event.payload)
    if workspace_id is None:
        orphan = await orphaned_subscription(session, event.payload)
        if orphan is not None:
            await _cancel_orphan(orphan, event)
            return Outcome("ignored", "the workspace was deleted; its subscription is cancelled")
        return Outcome("ignored", "no workspace for this event")
    with workspace_scope(workspace_id):
        applied = await lifecycle.apply_event(
            session, event, now=datetime.now(UTC), settings=get_settings()
        )
    if applied.changed:
        return Outcome("processed", workspace_id=workspace_id)
    return Outcome("ignored", applied.reason, workspace_id)


async def _cancel_orphan(subscription_id: str, event: WebhookEvent) -> None:
    from socialhood.jobs.app import BULK
    from socialhood.jobs.enqueue import enqueue_named

    log.error(
        "alert",
        kind="billing_orphan_subscription",
        detail=f"{subscription_id} is live but its workspace was deleted; cancelling it",
        event_type=event.event_type,
        webhook_event_id=str(event.id),
    )
    # One waiting job per subscription: every later event about it finds this one queued.
    await enqueue_named(
        ORPHAN_CANCEL_TASK,
        lane=BULK,
        key=f"dodo_cancel:{subscription_id}",
        subscription_id=subscription_id,
    )
