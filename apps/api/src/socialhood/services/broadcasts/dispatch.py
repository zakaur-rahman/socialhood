"""One batch of a sending broadcast (GR-23): the dispatch_broadcast job's work.

A batch hands up to ``throttle.BATCH_SIZE`` waiting recipients to the send queue
(``services.sending.queue_outbound`` with the template, source ``broadcast``), cut to what is
allowed now:

- the number's daily limit, less the people already messaged in the last 24 hours;
- the plan's monthly recipients, less those already counted this period.

Rules:
- Idempotent per recipient: the message's client id is derived from the recipient's id, so a batch
  that ran twice, or died after queuing a message, sends nothing twice (``queue_outbound`` returns
  the message already queued for that id). The recipient rows are locked (SKIP LOCKED) while a
  batch works, so two batches never take the same people.
- Resumable: a broadcast's progress is its recipients' state, so any later batch carries on; the
  job queues itself again a minute later while people are waiting (or when the daily limit frees a
  place), and the minutely sweeper starts a batch for any sending broadcast whose job was lost.
- Consent is checked again for each person at their turn: someone who sent STOP after the audience
  was fixed is skipped as ``opted_out``.
- Pauses (with a plain reason, and a notice to the owners and admins): the number's quality is
  Low, the plan no longer includes broadcasts or has no recipients left this month, the number
  needs reconnecting. The owner resumes. With BROADCASTS_ENABLED off a batch does nothing.
- A recipient the queue refuses for its own reason (the number is blocked for this person, say) is
  marked failed with a plain reason; the batch carries on.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.plans import current_plan, entitlement
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.broadcasts import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    QualityRating,
    RecipientState,
    SkipReason,
)
from socialhood.models.connections import AccountStatus
from socialhood.models.contacts import (
    ConsentChannel,
    ConsentPurpose,
    ConsentStatus,
    ContactConsent,
)
from socialhood.models.inbox import Contact
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import OutboundTemplate
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import broadcasts as repo
from socialhood.repositories import ingest as ingest_rows
from socialhood.repositories import sequences as sequence_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services import sending
from socialhood.services.broadcasts import health, lifecycle, service, throttle

log = get_logger(__name__)

NAMESPACE = uuid.UUID("5b1f1c2e-2c0e-4a4e-9a56-0a8f3b0f7d11")
# Errors that stop the whole broadcast rather than one person.
STOPS = {
    "quota_exceeded": ("plan", "Your plan's broadcast recipients for this month are used up."),
    "entitlement_required": ("plan", "Your plan no longer includes broadcasts."),
    "account_needs_reconnect": (
        "account",
        "This WhatsApp number needs reconnecting. Reconnect it, then resume the broadcast.",
    ),
    "capability_unavailable": (
        "account",
        "This WhatsApp number can't send template messages right now.",
    ),
}
REASON_MAX = 300


class StopBroadcast(Exception):
    """A reason that stops the whole broadcast, not just one person."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class Batch:
    """What a batch did and when to run the next one (None: nothing more to do)."""

    handed_over: int = 0
    skipped: int = 0
    failed: int = 0
    next_in_s: float | None = None
    state: str = "idle"  # idle, sending, paused, completed


def client_id(recipient_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, str(recipient_id))


async def consent_skip(session: AsyncSession, contact_id: uuid.UUID) -> str | None:
    """Why this person may not be messaged now, or None when their latest record grants it."""
    status = await session.scalar(
        select(ContactConsent.status)
        .where(
            ContactConsent.contact_id == contact_id,
            ContactConsent.channel == ConsentChannel.WHATSAPP,
            ContactConsent.purpose == ConsentPurpose.MARKETING,
        )
        .order_by(ContactConsent.occurred_at.desc(), ContactConsent.created_at.desc())
        .limit(1)
    )
    if status == ConsentStatus.GRANTED:
        return None
    return SkipReason.OPTED_OUT if status == ConsentStatus.REVOKED else SkipReason.NO_CONSENT


async def run_batch(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    broadcast_id: uuid.UUID,
    now: datetime | None = None,
) -> Batch:
    now = now or datetime.now(UTC)
    if not deps.settings.broadcasts_enabled:
        return Batch()
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            result = await _batch(session, deps, broadcast_id, now)
            await commit_and_publish(session, redis)
            return result


async def _batch(
    session: AsyncSession, deps: PlatformDeps, broadcast_id: uuid.UUID, now: datetime
) -> Batch:
    row = await session.scalar(
        select(Broadcast)
        .where(Broadcast.id == broadcast_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.status != BroadcastStatus.SENDING:
        return Batch()
    acct = await accounts.get(session, row.social_account_id)
    if acct is None or acct.status in (AccountStatus.NEEDS_RECONNECT, AccountStatus.DISCONNECTED):
        await lifecycle.pause(
            session, row, code="account", reason=STOPS["account_needs_reconnect"][1]
        )
        return Batch(state="paused")

    plan = await current_plan(session)
    limit = int(entitlement(plan, service.KEY) or 0)
    if limit <= 0:
        await lifecycle.pause(session, row, code="plan", reason=STOPS["entitlement_required"][1])
        return Batch(state="paused")
    used, _, _ = await service.quota_used(session, now)
    quota_left = max(0, limit - used)
    if quota_left == 0:
        await lifecycle.pause(session, row, code="limit", reason=STOPS["quota_exceeded"][1])
        return Batch(state="paused")

    number = await health.current(session, deps, acct, now=now)
    if number is not None and number.quality_rating == QualityRating.RED:
        await lifecycle.pause(session, row, code="quality", reason=health.RED_REASON)
        return Batch(state="paused")

    daily_limit, _ = health.daily_limit_of(number)
    # Sequences' template sends (GR-24) use the same number and the same daily limit.
    recent = await repo.dispatch_times(session, acct.id, now - throttle.WINDOW)
    recent += await sequence_repo.template_send_times(session, acct.id, now - throttle.WINDOW)
    room = throttle.room(daily_limit, len(recent))
    waiting = await repo.waiting(session, row.id)
    take = throttle.batch_size(room_now=room, waiting=waiting, quota_left=quota_left)
    if waiting and take == 0:
        # At the number's daily limit: wait for the 24-hour window to free a place.
        free_at = throttle.next_room_at(recent, daily_limit, now)
        wait = (free_at - now).total_seconds() if free_at else throttle.BATCH_EVERY.total_seconds()
        return Batch(state="sending", next_in_s=max(throttle.BATCH_EVERY.total_seconds(), wait))

    handed = skipped = failed = 0
    stop: StopBroadcast | None = None
    for recipient in await repo.pending_batch(session, row.id, take):
        try:
            outcome = await _one(session, deps, row, acct.id, recipient, now)
        except StopBroadcast as error:
            stop = error
            break
        if outcome == "handed":
            handed += 1
        elif outcome == "skipped":
            skipped += 1
        else:
            failed += 1
        await session.flush()
    if stop is not None:
        await lifecycle.pause(session, row, code=stop.code, reason=stop.reason)
        return Batch(handed, skipped, failed, state="paused")

    if await repo.waiting(session, row.id) == 0:
        lifecycle.complete(row, now)
        await session.flush()
        log.info("broadcast_completed", broadcast_id=str(row.id), handed_over=handed)
        return Batch(handed, skipped, failed, state="completed")
    return Batch(
        handed,
        skipped,
        failed,
        state="sending",
        next_in_s=throttle.BATCH_EVERY.total_seconds(),
    )


async def _one(
    session: AsyncSession,
    deps: PlatformDeps,
    row: Broadcast,
    account_id: uuid.UUID,
    recipient: BroadcastRecipient,
    now: datetime,
) -> str:
    """Hand one person to the send queue: ``handed``, ``skipped`` or ``failed``; raises
    StopBroadcast for a reason that stops the whole broadcast."""
    skip = await consent_skip(session, recipient.contact_id)
    if skip is not None:
        recipient.state = RecipientState.SKIPPED
        recipient.skip_reason = skip
        return "skipped"
    contact = await session.scalar(select(Contact).where(Contact.id == recipient.contact_id))
    if contact is None:  # deleted since the audience was fixed
        recipient.state = RecipientState.FAILED
        recipient.error_code = "not_found"
        recipient.error_message = "This contact was deleted."
        return "failed"
    conv, _ = await ingest_rows.get_or_create_conversation(
        session, social_account_id=account_id, contact_id=contact.id, platform="whatsapp"
    )
    template = OutboundTemplate(
        name=row.template_name,
        language=row.template_language,
        params=tuple(str(p) for p in recipient.params),
    )
    try:
        async with session.begin_nested():
            message = await sending.queue_outbound(
                session,
                conv,
                source="broadcast",
                client_id=client_id(recipient.id),
                template=template,
                deps=deps,
                now=now,
            )
    except ApiError as error:
        if error.code in STOPS:
            code, reason = STOPS[error.code]
            raise StopBroadcast(code, error.detail or reason) from error
        recipient.state = RecipientState.FAILED
        recipient.error_code = error.code
        recipient.error_message = (error.detail or "WhatsApp couldn't take this message.")[
            :REASON_MAX
        ]
        return "failed"
    recipient.state = RecipientState.DISPATCHED
    recipient.message_id = message.id
    recipient.dispatched_at = recipient.dispatched_at or now
    return "handed"
