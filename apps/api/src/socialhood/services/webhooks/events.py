"""Outbound events (GR-04): the catalogue, their payloads, and ``emit``.

Every event is sent as the same envelope, signed with the endpoint's secret (Standard Webhooks:
``webhook-id`` is the event id, the receiver's idempotency key):

    {"id": "<event id>", "type": "lead.captured", "version": 1,
     "created_at": "<ISO 8601>", "workspace_id": "<id>", "data": {...}}

A payload carries no access tokens and no more personal data than the event needs: a contact is
its id, platform, @username and name; an email or phone only in the events about them
(``lead.captured``, and ``contact.updated`` when they changed).

``emit`` runs in the transaction that caused the event: one delivery per active endpoint
subscribed to it, each with its deliver_webhook job (services/webhooks/delivery.py). Nothing is
written when no endpoint wants the event. Backfilled history emits nothing.

A ``lead.captured`` also queues a row for the workspace's Google Sheet (services/sheets.py).

``conversation.assigned`` (GR-20) and ``broadcast.finished`` (GR-23) are in the catalogue so
endpoints can subscribe now; they're emitted once those features exist.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Message
from socialhood.models.integrations import (
    DeliveryStatus,
    EndpointStatus,
    WebhookDelivery,
    WebhookEndpoint,
)
from socialhood.observability.logging import get_logger

log = get_logger(__name__)

START_DELAY_S = 1.0  # the caller commits after emitting


@dataclass(frozen=True)
class EventType:
    name: str
    version: int
    description: str
    emitted: bool = True  # False until the feature that raises it exists


EVENTS: tuple[EventType, ...] = (
    EventType("contact.created", 1, "A new person wrote, commented or opened an entry link."),
    EventType("contact.updated", 1, "A contact's email, phone or custom fields changed."),
    EventType("contact.tagged", 1, "A tag was added to or removed from a contact."),
    EventType("lead.captured", 1, "An automation's question saved an email, phone or field."),
    EventType("lead.stage_changed", 1, "A contact's lead stage changed."),
    EventType("message.received", 1, "A customer sent a direct message."),
    EventType("conversation.assigned", 1, "A conversation was assigned.", emitted=False),
    EventType("automation.run.completed", 1, "An automation run finished."),
    EventType("broadcast.finished", 1, "A broadcast finished sending.", emitted=False),
)
BY_NAME = {e.name: e for e in EVENTS}
TEST_EVENT = "webhook.test"  # "Send test event" (not subscribable)


def envelope(event_type: str, data: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    known = BY_NAME.get(event_type)
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "version": known.version if known else 1,
        "created_at": now.isoformat(),
        "workspace_id": str(require_workspace()),
        "data": data,
    }


# ---------------------------------------------------------------- payload parts


def contact_ref(contact: Contact, platform: str | None = None) -> dict[str, Any]:
    return {
        "id": str(contact.id),
        "platform": platform,
        "username": contact.username,
        "name": contact.display_name,
    }


async def _platform(session: AsyncSession, contact: Contact) -> str | None:
    return await session.scalar(
        select(SocialAccount.platform).where(SocialAccount.id == contact.social_account_id)
    )


# ---------------------------------------------------------------- emitting


async def _endpoints(session: AsyncSession, event_type: str) -> list[WebhookEndpoint]:
    rows = await session.scalars(
        select(WebhookEndpoint).where(
            WebhookEndpoint.status == EndpointStatus.ACTIVE,
            WebhookEndpoint.events.contains([event_type]),
        )
    )
    return list(rows.all())


async def wanted(session: AsyncSession, event_type: str) -> bool:
    """Whether any active endpoint receives ``event_type`` (to skip building a payload)."""
    return bool(await _endpoints(session, event_type))


async def emit(
    session: AsyncSession, event_type: str, data: dict[str, Any], *, now: datetime | None = None
) -> int:
    """Queue the event for every active endpoint that wants it; returns how many deliveries."""
    return await emit_many(session, event_type, [data], now=now)


async def emit_many(
    session: AsyncSession,
    event_type: str,
    items: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> int:
    """One event per item, the endpoints looked up once (bulk tagging)."""
    endpoints = await _endpoints(session, event_type) if items else []
    if not endpoints:
        return 0
    now = now or datetime.now(UTC)
    deliveries = []
    for data in items:
        body = envelope(event_type, data, now=now)
        deliveries += [
            WebhookDelivery(
                endpoint_id=endpoint.id,
                event_id=uuid.UUID(body["id"]),
                event_type=event_type,
                payload=body,
                status=DeliveryStatus.PENDING,
                next_attempt_at=now,
            )
            for endpoint in endpoints
        ]
    session.add_all(deliveries)
    await session.flush()
    for delivery in deliveries:
        await enqueue_delivery(delivery.id, delay_s=START_DELAY_S)
    return len(deliveries)


async def enqueue_delivery(
    delivery_id: uuid.UUID, *, delay_s: float = START_DELAY_S, not_found: int = 0
) -> None:
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.outbound import deliver_webhook

    try:
        await enqueue(
            deliver_webhook,
            key=f"whd:{delivery_id}",
            delay_s=delay_s,
            workspace_id=str(require_workspace()),
            delivery_id=str(delivery_id),
            not_found=not_found,
        )
    except Exception:  # never fail what raised the event; the delivery stays pending
        log.warning("webhook_enqueue_failed", delivery_id=str(delivery_id))


# ---------------------------------------------------------------- the events


async def contact_created(session: AsyncSession, contact: Contact, *, platform: str) -> None:
    await emit(session, "contact.created", {"contact": contact_ref(contact, platform)})


async def contact_updated(session: AsyncSession, contact: Contact, changed: list[str]) -> None:
    """``changed``: "email", "phone" and "fields.<key>"; their new values ride along."""
    if not changed:
        return
    values: dict[str, Any] = {}
    for name in changed:
        if name == "email":
            values["email"] = contact.email
        elif name == "phone":
            values["phone"] = contact.phone
        elif name.startswith("fields."):
            values[name] = (contact.fields or {}).get(name.removeprefix("fields."))
    await emit(
        session,
        "contact.updated",
        {
            "contact": contact_ref(contact, await _platform(session, contact)),
            "changed": changed,
            "values": values,
        },
    )


@dataclass(frozen=True)
class TagChange:
    contact: Contact
    tag_id: uuid.UUID
    tag_name: str
    added: bool


async def contacts_tagged(session: AsyncSession, changes: list[TagChange]) -> None:
    if not changes or not await wanted(session, "contact.tagged"):
        return
    platforms = dict(
        (
            await session.execute(
                select(SocialAccount.id, SocialAccount.platform).where(
                    SocialAccount.id.in_({c.contact.social_account_id for c in changes})
                )
            )
        ).all()
    )
    await emit_many(
        session,
        "contact.tagged",
        [
            {
                "contact": contact_ref(c.contact, platforms.get(c.contact.social_account_id)),
                "tag": {"id": str(c.tag_id), "name": c.tag_name},
                "action": "added" if c.added else "removed",
            }
            for c in changes
        ],
    )


async def lead_captured(
    session: AsyncSession,
    contact: Contact,
    *,
    kind: str,
    value: object,
    field_key: str | None,
    automation_id: uuid.UUID,
    automation_name: str,
    run_id: uuid.UUID,
) -> None:
    platform = await _platform(session, contact)
    await emit(
        session,
        "lead.captured",
        {
            "contact": contact_ref(contact, platform),
            "captured": {"kind": kind, "field_key": field_key, "value": value},
            "automation": {"id": str(automation_id), "name": automation_name},
            "run_id": str(run_id),
        },
    )
    # GR-27: the workspace's Google Sheet gets a row for the same capture.
    from socialhood.services import sheets

    await sheets.queue_lead(session, contact, platform=platform, automation_name=automation_name)


async def lead_stage_changed(
    session: AsyncSession,
    contact: Contact,
    *,
    from_stage: str,
    to_stage: str,
    actor_kind: str,
    actor_user_id: uuid.UUID | None,
    rule: str | None,
    reason: str | None,
) -> None:
    """A lead's stage moved (GR-18), by a member, an automation or a rule."""
    if not await wanted(session, "lead.stage_changed"):
        return
    await emit(
        session,
        "lead.stage_changed",
        {
            "contact": contact_ref(contact, await _platform(session, contact)),
            "from": from_stage,
            "to": to_stage,
            "changed_by": {
                "kind": actor_kind,
                "user_id": str(actor_user_id) if actor_user_id else None,
                "rule": rule,
            },
            "reason": reason,
        },
    )


async def message_received(
    session: AsyncSession, contact: Contact, msg: Message, *, platform: str
) -> None:
    await emit(
        session,
        "message.received",
        {
            "contact": contact_ref(contact, platform),
            "conversation_id": str(msg.conversation_id),
            "message": {
                "id": str(msg.id),
                "kind": msg.kind,
                "text": msg.text,
                "occurred_at": msg.occurred_at.isoformat(),
            },
        },
    )


async def run_completed(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    result: str,
    trigger: str,
    automation_id: uuid.UUID,
    automation_name: str,
    contact: Contact | None,
) -> None:
    """Once per run: a run's result can be reported more than once (the send, then its echo)."""
    if not await wanted(session, "automation.run.completed"):
        return
    already = await session.scalar(
        select(WebhookDelivery.id)
        .where(
            WebhookDelivery.event_type == "automation.run.completed",
            WebhookDelivery.payload["data"]["run"]["id"].astext == str(run_id),
        )
        .limit(1)
    )
    if already is not None:
        return
    await emit(
        session,
        "automation.run.completed",
        {
            "run": {"id": str(run_id), "result": result, "trigger": trigger},
            "automation": {"id": str(automation_id), "name": automation_name},
            "contact": contact_ref(contact, await _platform(session, contact)) if contact else None,
        },
    )
