"""Instagram webhook events: route to the account's workspace, parse, then ingest DMs (F-06, T3.2)
or take in comments (F-12, T4.4: services/automations/comments). The caller
(services/webhook_processing) commits and publishes the real-time events queued here.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.events import InboundComment
from socialhood.platforms.instagram.parse import parse
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations import comments
from socialhood.services.ingest import ingest
from socialhood.services.webhook_handlers import Outcome
from socialhood.webhooks.routing import resolve_account


def platform_deps() -> PlatformDeps:
    """The worker's (webhook events are processed by the worker); tests replace it."""
    from socialhood.jobs.runtime import runtime

    rt = runtime()
    return deps_from(rt.http, rt.settings)


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    if event.event_type == "invalid":
        return Outcome("ignored", "unreadable payload")
    routed = await resolve_account(session, "instagram", event.platform_account_id or "")
    if routed is None:
        return Outcome("ignored", "unknown or disconnected account")
    wid = routed.workspace_id
    with workspace_scope(wid):
        parsed = parse(event.payload)
        acct = await accounts.get(session, routed.account_id)
        if acct is None:
            return Outcome("ignored", "unknown or disconnected account", wid)
        if isinstance(parsed, InboundComment):
            taken = await comments.intake(session, acct, parsed, deps=platform_deps)
            if taken.comment is None:
                return Outcome("ignored", taken.ignored, wid)
            return Outcome("processed", None, wid)
        result = await ingest(session, acct, [parsed])
    if result.ignored and not result.changed:
        return Outcome("ignored", "; ".join(result.ignored), wid)
    return Outcome("processed", None, wid)
