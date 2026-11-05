"""Dodo webhook events (T8.3; TR-BIL-02, TR-WH-05).

Route the stored event to its workspace (webhooks/dodo_routing.py: the checkout's signed
``metadata.workspace_id``, else the stored ``dodo_subscription_id``), then apply it in that
workspace's scope with billing/lifecycle.apply_event. An event for no known workspace, of a type
we don't act on, or older than the subscription's last_event_at is ``ignored`` with the reason.
Only events that passed the signature check at intake are stored, so only they get here.

A live subscription whose workspace was deleted or is being deleted (a checkout paid after the
deletion, say) would otherwise bill forever: it raises an alert and queues
``cancel_orphan_subscription``, which cancels it in Dodo at once and retries while Dodo fails.

A new subscription or payment that routes nowhere is someone's money with no plan behind it (a
payment link our checkout didn't make): it stays in webhook_events and raises an alert for a person
to look at. A trial the workspace may no longer have is refused and cancelled the same way.
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
NEW_MONEY = frozenset({"subscription.active", "payment.succeeded"})


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    settings = get_settings()
    workspace_id = await resolve_workspace(session, event.payload, settings.token_encryption_keys)
    if workspace_id is None:
        orphan = await orphaned_subscription(session, event.payload)
        if orphan is not None:
            await _cancel_orphan(orphan, event)
            return Outcome("ignored", "the workspace was deleted; its subscription is cancelled")
        if event.event_type in NEW_MONEY:
            log.error(
                "alert",
                kind="billing_unrouted_payment",
                detail=f"{event.event_type} matches no workspace",
                subscription_id=_subscription_of(event),
                webhook_event_id=str(event.id),
            )
        return Outcome("ignored", "no workspace for this event")
    with workspace_scope(workspace_id):
        applied = await lifecycle.apply_event(
            session, event, now=datetime.now(UTC), settings=settings
        )
    if applied.cancel is not None:
        await _queue_cancel(applied.cancel)
    if applied.changed:
        return Outcome("processed", workspace_id=workspace_id)
    return Outcome("ignored", applied.reason, workspace_id)


def _subscription_of(event: WebhookEvent) -> str | None:
    data = event.payload.get("data")
    found = data.get("subscription_id") if isinstance(data, dict) else None
    return found if isinstance(found, str) else None


async def _cancel_orphan(subscription_id: str, event: WebhookEvent) -> None:
    log.error(
        "alert",
        kind="billing_orphan_subscription",
        detail=f"{subscription_id} is live but its workspace was deleted; cancelling it",
        event_type=event.event_type,
        webhook_event_id=str(event.id),
    )
    await _queue_cancel(subscription_id)


async def _queue_cancel(subscription_id: str) -> None:
    from socialhood.jobs.app import BULK
    from socialhood.jobs.enqueue import enqueue_named

    # One waiting job per subscription: every later event about it finds this one queued.
    await enqueue_named(
        ORPHAN_CANCEL_TASK,
        lane=BULK,
        key=f"dodo_cancel:{subscription_id}",
        subscription_id=subscription_id,
    )
