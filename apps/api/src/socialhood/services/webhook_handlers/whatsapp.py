"""WhatsApp webhook events: messages, reactions and delivery statuses (F-06, F-07, TR-WH-05).

Route by metadata.phone_number_id, parse the stored event (platforms/whatsapp/parse.py), then:
messages and reactions go to services/ingest.py like every platform's; delivery statuses update
the outbound message (services/whatsapp_status.py). A status can arrive before the send job has
stored the message's wamid, so a recent status for an unknown message is retried (the webhook
job's backoff) and ignored on the last attempt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent
from socialhood.platforms.events import DeliveryStatus, Unsupported
from socialhood.platforms.whatsapp.parse import parse_event
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories.webhook_events import MAX_ATTEMPTS
from socialhood.services import ingest, whatsapp_status
from socialhood.services.webhook_handlers import Outcome
from socialhood.webhooks.routing import resolve_account

HANDLED = frozenset({"message", "reaction", "status"})
STATUS_RETRY_WINDOW = timedelta(minutes=10)


class StatusNotMatched(RuntimeError):
    """A delivery status for a message we can't find yet; the job retries it."""


def _retry_status(event: WebhookEvent, status: DeliveryStatus) -> bool:
    last_attempt = event.attempts + 1 >= MAX_ATTEMPTS
    recent = datetime.now(UTC) - status.occurred_at < STATUS_RETRY_WINDOW
    return recent and not last_attempt


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    if event.event_type == "invalid":
        return Outcome("ignored", "unreadable payload")
    if event.event_type not in HANDLED:
        return Outcome("ignored", f"{event.event_type} events are not used")
    routed = await resolve_account(session, "whatsapp", event.platform_account_id or "")
    if routed is None:
        return Outcome("ignored", "unknown or disconnected account")
    with workspace_scope(routed.workspace_id):
        acct = await accounts.get(session, routed.account_id)
        if acct is None:
            return Outcome("ignored", "unknown or disconnected account")
        parsed = parse_event(event.payload)
        if isinstance(parsed, Unsupported):
            return Outcome("ignored", parsed.reason, routed.workspace_id)
        if isinstance(parsed, DeliveryStatus):
            result = await whatsapp_status.apply_status(session, acct, parsed)
            if result == "unknown_message":
                if _retry_status(event, parsed):
                    raise StatusNotMatched(f"no outbound message {parsed.platform_message_id} yet")
                return Outcome("ignored", "no outbound message with this id", routed.workspace_id)
            if result == "stale":
                return Outcome("ignored", f"{parsed.status} is not newer", routed.workspace_id)
            return Outcome("processed", workspace_id=routed.workspace_id)
        outcome = await ingest.ingest(session, acct, [parsed])
        if outcome.ignored and not (outcome.created_message_ids or outcome.updated_message_ids):
            return Outcome("ignored", "; ".join(outcome.ignored), routed.workspace_id)
        return Outcome("processed", workspace_id=routed.workspace_id)
