"""Razorpay webhook events (GR-32): route to the workspace the webhook address belongs to, then
apply the payment (services/orders/webhook.apply). The caller (services/webhook_processing)
commits.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.services.orders import payments, webhook
from socialhood.services.webhook_handlers import Outcome
from socialhood.webhooks.routing import razorpay_owner


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    if event.event_type == "invalid":
        return Outcome("ignored", "unreadable payload")
    workspace_id = await razorpay_owner(session, event.platform_account_id or "")
    if workspace_id is None:
        return Outcome("ignored", "unknown account")
    payload = event.payload or {}
    with workspace_scope(workspace_id):
        conn = await payments.get(session, lock=True)
        if conn is None:
            return Outcome("ignored", "unknown account", workspace_id)
        status, reason = await webhook.apply(
            session, conn, str(payload.get("event") or event.event_type), payload.get("body") or {}
        )
    return Outcome(status, reason, workspace_id)  # type: ignore[arg-type]
