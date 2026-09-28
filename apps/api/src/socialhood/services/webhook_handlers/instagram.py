"""Instagram webhook events: route to the account's workspace, parse, ingest (F-06, F-12).

T3.2 replaces the body of ``handle`` with: parse the stored payload into typed events
(platforms/instagram/parse.py) and pass them to services/ingest.py. Comments stay ignored until
P6 (T6.1).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.services.webhook_handlers import Outcome
from socialhood.webhooks.routing import resolve_account


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    if event.event_type == "invalid":
        return Outcome("ignored", "unreadable payload")
    routed = await resolve_account(session, "instagram", event.platform_account_id or "")
    if routed is None:
        return Outcome("ignored", "unknown or disconnected account")
    with workspace_scope(routed.workspace_id):
        return Outcome(
            "ignored", f"{event.event_type} handling arrives with the inbox", routed.workspace_id
        )
