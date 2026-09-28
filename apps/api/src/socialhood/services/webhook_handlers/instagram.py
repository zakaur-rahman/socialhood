"""Instagram webhook events: route to the account's workspace, parse, ingest (F-06, T3.2).

Comments are parsed but stay ignored until P6 (T6.1). The caller (services/webhook_processing)
commits and publishes the real-time events ingest queued.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.platforms.events import InboundComment
from socialhood.platforms.instagram.parse import parse
from socialhood.repositories import social_accounts as accounts
from socialhood.services.ingest import ingest
from socialhood.services.webhook_handlers import Outcome
from socialhood.webhooks.routing import resolve_account

COMMENTS_LATER = "comments arrive in P6"


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    if event.event_type == "invalid":
        return Outcome("ignored", "unreadable payload")
    routed = await resolve_account(session, "instagram", event.platform_account_id or "")
    if routed is None:
        return Outcome("ignored", "unknown or disconnected account")
    wid = routed.workspace_id
    with workspace_scope(wid):
        parsed = parse(event.payload)
        if isinstance(parsed, InboundComment):
            return Outcome("ignored", COMMENTS_LATER, wid)
        acct = await accounts.get(session, routed.account_id)
        if acct is None:
            return Outcome("ignored", "unknown or disconnected account", wid)
        result = await ingest(session, acct, [parsed])
    if result.ignored and not result.changed:
        return Outcome("ignored", "; ".join(result.ignored), wid)
    return Outcome("processed", None, wid)
