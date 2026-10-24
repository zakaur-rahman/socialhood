"""Shopify webhook events (GR-31): route to the store's workspace, then apply the product change
(services/catalogue/shopify.handle_webhook). The caller (services/webhook_processing) commits.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.repositories import catalogue as repo
from socialhood.services.catalogue import shopify
from socialhood.services.webhook_handlers import Outcome
from socialhood.webhooks.routing import shopify_owner


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    if event.event_type == "invalid":
        return Outcome("ignored", "unreadable payload")
    shop = event.platform_account_id or ""
    workspace_id = await shopify_owner(session, shop) if shop else None
    if workspace_id is None:
        return Outcome("ignored", "unknown store")
    payload = event.payload or {}
    with workspace_scope(workspace_id):
        conn = await repo.get_shopify(session, lock=True)
        if conn is None:
            return Outcome("ignored", "unknown store", workspace_id)
        status, reason = await shopify.handle_webhook(
            session, conn, str(payload.get("topic") or event.event_type), payload.get("body") or {}
        )
    return Outcome(status, reason, workspace_id)
