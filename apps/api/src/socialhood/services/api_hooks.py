"""REST hooks for Zapier triggers (GR-26): subscribe and unsubscribe through the public API.

A subscription is an ordinary webhook endpoint (GR-04, services/webhooks/) that carries the key
that made it (``api_key_id``). Everything after that is shared: the event envelope, Standard
Webhooks signing (the signing secret is in the subscribe response, once), the retry schedule, the
delivery log, turning the endpoint off after repeated failures, and the Activity reasons.

- Zapier's trigger names map to the event catalogue (``TRIGGER_EVENTS``). "Tag added" is
  ``contact.tagged`` and Zapier keeps only the ``added`` ones.
- The address follows the endpoint rules (https, not a private address; WEBHOOKS_ALLOW_PRIVATE
  allows a local one in development and e2e).
- Hook endpoints don't count against the plan's ``webhook_endpoints``; a workspace holds at most
  ``MAX_HOOKS`` of them. They go when their key is revoked (services/api_keys.py), and stop
  receiving events when the workspace is no longer on a plan with the public API (PD-6).
- Any key with the ``webhooks:subscribe`` scope in the workspace may unsubscribe a hook (Zapier
  unsubscribes with the key of the connection, which can have been replaced since).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.integrations import EndpointStatus, WebhookEndpoint
from socialhood.repositories.base import scoped_delete
from socialhood.schemas.public_hooks import Hook, HookList, HookSubscribe, HookSubscribed
from socialhood.security.crypto import TokenCipher
from socialhood.services.webhooks.endpoints import _url, new_secret

# Zapier trigger key -> the event it listens to.
TRIGGER_EVENTS: dict[str, str] = {
    "new_contact": "contact.created",
    "lead_captured": "lead.captured",
    "tag_added": "contact.tagged",
    "new_message": "message.received",
    "run_completed": "automation.run.completed",
}
EVENT_TRIGGERS = {event: trigger for trigger, event in TRIGGER_EVENTS.items()}
MAX_HOOKS = 100


def hook_out(endpoint: WebhookEndpoint) -> Hook:
    return Hook(
        id=endpoint.id,
        trigger=EVENT_TRIGGERS.get(endpoint.events[0], endpoint.events[0]),
        target_url=endpoint.url,
        status=endpoint.status,
        created_at=endpoint.created_at,
    )


async def list_hooks(session: AsyncSession) -> HookList:
    rows = await session.scalars(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.api_key_id.is_not(None))
        .order_by(WebhookEndpoint.created_at, WebhookEndpoint.id)
    )
    return HookList(items=[hook_out(e) for e in rows.all()])


async def subscribe(
    session: AsyncSession,
    body: HookSubscribe,
    *,
    key_id: uuid.UUID,
    cipher: TokenCipher,
    allow_private: bool,
) -> HookSubscribed:
    url = _url(body.target_url, allow_private=allow_private)
    count = await session.scalar(
        select(func.count())
        .select_from(WebhookEndpoint)
        .where(WebhookEndpoint.api_key_id.is_not(None))
    )
    if (count or 0) >= MAX_HOOKS:
        raise ApiError("conflict", f"A workspace can have up to {MAX_HOOKS} REST hooks.")
    secret = new_secret()
    endpoint = WebhookEndpoint(
        url=url,
        description=f"Zapier: {body.trigger.replace('_', ' ')}",
        events=[TRIGGER_EVENTS[body.trigger]],
        status=EndpointStatus.ACTIVE,
        secret_enc=cipher.encrypt(secret),
        failing_deliveries=0,
        api_key_id=key_id,
    )
    session.add(endpoint)
    await session.flush()
    await session.refresh(endpoint)
    return HookSubscribed(**hook_out(endpoint).model_dump(), signing_secret=secret)


async def unsubscribe(session: AsyncSession, hook_id: uuid.UUID) -> None:
    result = await session.execute(
        scoped_delete(WebhookEndpoint, id=hook_id).where(WebhookEndpoint.api_key_id.is_not(None))
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise ApiError("not_found", "That hook wasn't found.")
