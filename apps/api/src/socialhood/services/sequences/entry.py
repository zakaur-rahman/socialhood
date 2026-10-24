"""Entry and stop events for sequences (GR-24). Each runs in the caller's transaction and never
commits. They are called from the places the product already has for these events, not from new
ones:

- a lead captured: ``webhooks.events.lead_captured`` (GR-14's capture steps, GR-04's event);
- a tag added or removed: ``webhooks.events.contacts_tagged`` (every way a tag is added or removed);
- a lead stage change: ``webhooks.events.lead_stage_changed`` (GR-18);
- a customer message: ``services.ingest`` (the reply stop, and the replies to a broadcast that
  ``broadcasts.inbound`` has just worked out).

Rules:
- A contact is in a sequence once at a time: a second entry while one is active does nothing. A
  contact who finished or was stopped enters again only if the sequence allows re-entry.
- Only an *active* sequence on the contact's own account takes people in. A paused sequence keeps
  those already in it, and takes nobody new.
- Entry: a lead moving into a stage enters the sequences that start on that stage (``lead_stage``).
- Stopping: a customer message stops the contact's active enrolments in sequences with
  ``stop_on_reply``; a stop tag added, a tag taken off (``stop_removed_tag_ids``) or a stop stage
  stops those in the sequences that list it. A stopped enrolment keeps its history and says why.
- Each entry and each stop raises the ``sequence.enrolled`` or ``sequence.stopped`` event (GR-04).
- Entry from a reply to a broadcast comes *after* the reply stops the others, so a message never
  stops the sequence it started.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence as Seq
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Message
from socialhood.models.sequences import (
    EnrolmentStatus,
    EntryType,
    Sequence,
    SequenceEnrolment,
    StopReason,
)
from socialhood.observability.logging import get_logger
from socialhood.repositories import sequences as repo
from socialhood.services.sequences import rules
from socialhood.services.webhooks import events
from socialhood.services.webhooks.events import TagChange

log = get_logger(__name__)

CAPTURE_EVENT = {
    "email": "Gave their email",
    "phone": "Gave their phone number",
    "field": "Answered a question",
}


def capture_kind(kind: str) -> str:
    """A captured answer's kind as a sequence sees it: email, phone or field (any other answer)."""
    return kind if kind in ("email", "phone") else "field"


async def enrol(
    session: AsyncSession,
    sequence: Sequence,
    contact: Contact,
    *,
    event: str,
    now: datetime,
) -> SequenceEnrolment | None:
    """Put ``contact`` into ``sequence`` (see the module docstring); None when they are not taken
    in. The first step is due after its delay, counted from now."""
    if sequence.status != "active" or contact.social_account_id != sequence.social_account_id:
        return None
    if await repo.has_enrolment(
        session, sequence.id, contact.id, active_only=sequence.allow_reentry
    ):
        return None
    first = await repo.first_step(session, sequence.id)
    if first is None:
        return None
    row = SequenceEnrolment(
        sequence_id=sequence.id,
        contact_id=contact.id,
        social_account_id=sequence.social_account_id,
        status=EnrolmentStatus.ACTIVE,
        current_step=first.position,
        next_due_at=now + timedelta(seconds=first.delay_seconds),
        enrolled_at=now,
        entry_event=event[:200],
    )
    try:
        async with session.begin_nested():  # the partial unique index: one active per contact
            session.add(row)
            await session.flush()
    except IntegrityError:
        return None
    log.info("sequence_enrolled", sequence_id=str(sequence.id), contact_id=str(contact.id))
    await events.sequence_event(
        session,
        "sequence.enrolled",
        contact,
        sequence_id=sequence.id,
        sequence_name=sequence.name,
        enrolment_id=row.id,
        entry_event=row.entry_event,
    )
    return row


async def _stopped(
    session: AsyncSession,
    contact: Contact,
    stopped: Seq[tuple[uuid.UUID, uuid.UUID]],
    *,
    reason: str,
    detail: str | None,
) -> None:
    """Raise ``sequence.stopped`` for each enrolment ``repo.stop_matching`` just stopped."""
    if not stopped or not await events.wanted(session, "sequence.stopped"):
        return
    names = dict(
        (
            await session.execute(
                select(Sequence.id, Sequence.name).where(
                    Sequence.id.in_({sequence_id for _, sequence_id in stopped})
                )
            )
        ).all()
    )
    for enrolment_id, sequence_id in stopped:
        await events.sequence_event(
            session,
            "sequence.stopped",
            contact,
            sequence_id=sequence_id,
            sequence_name=names.get(sequence_id, ""),
            enrolment_id=enrolment_id,
            reason=reason,
            reason_text=rules.stop_text(reason, detail),
        )


async def on_captured(session: AsyncSession, contact: Contact, *, kind: str) -> None:
    """A capture step saved an email, a phone or an answer."""
    now = datetime.now(UTC)
    shown = capture_kind(kind)
    for sequence in await repo.active_for_entry(
        session, contact.social_account_id, EntryType.CAPTURED
    ):
        if sequence.entry_capture_kind in (None, shown):
            await enrol(session, sequence, contact, event=CAPTURE_EVENT[shown], now=now)


async def on_tagged(session: AsyncSession, changes: Seq[TagChange]) -> None:
    """Tags were added or removed. A tag added enters the sequences that start on it and stops
    those that stop on it; a tag taken off stops the sequences that need it gone."""
    now = datetime.now(UTC)
    for change in changes:
        contact, tag_id, name = change.contact, change.tag_id, change.tag_name
        if not change.added:
            stopped = await repo.stop_matching(
                session,
                contact.id,
                reason=StopReason.TAG_REMOVED,
                detail=name[:100] or None,
                now=now,
                sequence_ids=select(Sequence.id).where(
                    Sequence.stop_removed_tag_ids.contains([tag_id])
                ),
            )
            await _stopped(
                session, contact, stopped, reason=StopReason.TAG_REMOVED, detail=name[:100] or None
            )
            continue
        stopped = await repo.stop_matching(
            session,
            contact.id,
            reason=StopReason.TAG,
            detail=name[:100] or None,
            now=now,
            sequence_ids=select(Sequence.id).where(Sequence.stop_tag_ids.contains([tag_id])),
        )
        await _stopped(session, contact, stopped, reason=StopReason.TAG, detail=name[:100] or None)
        for sequence in await repo.active_for_entry(
            session, contact.social_account_id, EntryType.TAGGED
        ):
            if sequence.entry_tag_id == tag_id:
                await enrol(session, sequence, contact, event=f"Tagged {name}"[:200], now=now)


async def on_stage(session: AsyncSession, contact: Contact, to_stage: str, label: str) -> None:
    """A contact's lead stage changed: stop the sequences that stop on the new stage, then enter
    the ones that start on it (so a stage never stops the sequence it just started)."""
    now = datetime.now(UTC)
    stopped = await repo.stop_matching(
        session,
        contact.id,
        reason=StopReason.STAGE,
        detail=label[:100],
        now=now,
        sequence_ids=select(Sequence.id).where(Sequence.stop_stages.contains([to_stage])),
    )
    await _stopped(session, contact, stopped, reason=StopReason.STAGE, detail=label[:100])
    for sequence in await repo.active_for_entry(
        session, contact.social_account_id, EntryType.LEAD_STAGE
    ):
        if sequence.entry_stage == to_stage:
            await enrol(session, sequence, contact, event=f"Lead stage: {label}"[:200], now=now)


async def on_inbound(
    session: AsyncSession,
    acct: SocialAccount,
    contact: Contact,
    msg: Message,
    replied_broadcasts: Seq[uuid.UUID],
) -> None:
    """A customer message: it stops the contact's sequences that stop on a reply, then enters them
    in the sequences that start on a reply to the broadcast(s) it answered."""
    now = datetime.now(UTC)
    stopped = await repo.stop_matching(
        session,
        contact.id,
        reason=StopReason.REPLY,
        detail=None,
        now=now,
        sequence_ids=select(Sequence.id).where(Sequence.stop_on_reply.is_(True)),
    )
    await _stopped(session, contact, stopped, reason=StopReason.REPLY, detail=None)
    if not replied_broadcasts:
        return
    for sequence in await repo.active_for_entry(session, acct.id, EntryType.BROADCAST_REPLIED):
        if sequence.entry_broadcast_id in (None, *replied_broadcasts):
            await enrol(session, sequence, contact, event="Replied to a broadcast", now=now)
