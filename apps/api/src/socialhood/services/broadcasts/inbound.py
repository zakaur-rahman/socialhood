"""What a customer's WhatsApp message does to broadcasts (GR-23). Runs from ingest for a new
inbound message (never for backfilled history), in the caller's transaction. Nothing here commits.

- **STOP.** A message that is only a stop phrase (services/broadcasts/stop.py) withdraws the
  contact's WhatsApp marketing consent: a ``revoked`` record with source ``stop_reply`` and the
  message as evidence (its id and the first 100 characters). It is recorded even when the contact
  had no consent on file, so "asked us to stop" is on the record. The latest record wins, so the
  contact is never broadcast to again until someone records new consent; a broadcast that is
  already sending checks consent again at each person's turn and skips them.
- **Replies.** A message within ``REPLY_WINDOW`` of a broadcast message to this contact counts as
  a reply to every such broadcast not yet answered (``replied_at``); a STOP also sets
  ``stopped_at`` on those, so the broadcast page can say how many people unsubscribed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.broadcasts import BroadcastRecipient, RecipientState
from socialhood.models.connections import SocialAccount
from socialhood.models.contacts import (
    ConsentChannel,
    ConsentPurpose,
    ConsentSource,
    ConsentStatus,
    ContactConsent,
)
from socialhood.models.inbox import Contact, Message
from socialhood.observability.logging import get_logger
from socialhood.services import contacts
from socialhood.services.broadcasts import stop

log = get_logger(__name__)

REPLY_WINDOW = timedelta(days=7)
EVIDENCE_TEXT = 100


async def on_inbound(
    session: AsyncSession, acct: SocialAccount, contact: Contact, msg: Message, now: datetime
) -> list[uuid.UUID]:
    """Returns the broadcasts this message newly counts as a reply to (GR-24 starts sequences on
    them)."""
    if acct.platform != ConsentChannel.WHATSAPP or msg.kind != "text":
        return []
    at = msg.occurred_at or now
    stopping = stop.is_stop(msg.text)
    since = at - REPLY_WINDOW
    recent = (
        await session.scalars(
            select(BroadcastRecipient)
            .where(
                BroadcastRecipient.contact_id == contact.id,
                BroadcastRecipient.state == RecipientState.DISPATCHED,
                BroadcastRecipient.dispatched_at >= since,
                # Meta's timestamps are whole seconds: a reply in the same second still counts.
                func.date_trunc("second", BroadcastRecipient.dispatched_at) <= at,
            )
            .with_for_update()
        )
    ).all()
    replied: list[uuid.UUID] = []
    for recipient in recent:
        if recipient.replied_at is None:
            recipient.replied_at = at
            replied.append(recipient.broadcast_id)
        if stopping and recipient.stopped_at is None:
            recipient.stopped_at = at
    if stopping:
        await _withdraw(session, contact, msg, at)
    if recent or stopping:
        await session.flush()
    return replied


async def _withdraw(session: AsyncSession, contact: Contact, msg: Message, at: datetime) -> None:
    latest = (
        await session.execute(
            select(ContactConsent.status, ContactConsent.occurred_at)
            .where(
                ContactConsent.contact_id == contact.id,
                ContactConsent.channel == ConsentChannel.WHATSAPP,
                ContactConsent.purpose == ConsentPurpose.MARKETING,
            )
            .order_by(ContactConsent.occurred_at.desc(), ContactConsent.created_at.desc())
            .limit(1)
        )
    ).one_or_none()
    if latest is not None:
        if latest.status == ConsentStatus.REVOKED:
            return  # already withdrawn: one record is enough
        # WhatsApp stamps a message to the second, so a grant recorded in that same second would
        # otherwise outrank the STOP that followed it: the withdrawal always comes last.
        at = max(at, latest.occurred_at + timedelta(milliseconds=1))
    await contacts.record_consent(
        session,
        contact.id,
        channel=ConsentChannel.WHATSAPP,
        status=ConsentStatus.REVOKED,
        source=ConsentSource.STOP_REPLY,
        evidence={"message_id": str(msg.id), "text": (msg.text or "")[:EVIDENCE_TEXT]},
        at=at,
    )
    log.info("broadcast_stop_reply", contact_id=str(contact.id))
