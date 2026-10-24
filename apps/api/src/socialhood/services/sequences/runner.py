"""Running sequences: the sweeper's work, one due enrolment at a time (GR-24).

``run_due`` runs the active enrolments whose step is due (``repositories.sequences.due`` finds them
across workspaces, in active sequences on accounts that can send; the job does that) each in its
own transaction under a row lock (``SKIP LOCKED``: a second worker passes over it). One run of
one enrolment:

1. the step at ``current_step`` is read; if there is none the enrolment is completed;
2. if the step already has a run row (a retry after a crash between the send and the commit can't
   happen, the two are one transaction, but a second worker could), nothing is sent again;
3. the step may be held, not run: until business hours open (``respect_hours``), or on WhatsApp
   for a template while the number's quality is Low or its daily limit is used up (the limit is
   shared with broadcasts, services/broadcasts/dispatch, which counts these sends too);
4. the step decides what to send (``rules.decide``) and hands it to the normal send queue
   (``sending.queue_outbound``, source ``automation``), so the token bucket, retries, statuses,
   inbox and realtime all work as for any message. The message's client id is derived from the
   enrolment and the step, so a repeated hand-over returns the message already queued;
5. a ``sequence_step_runs`` row records sent, skipped (with the reason) or failed, one per
   (enrolment, step) by a unique constraint, and the enrolment moves to the next step: due after
   that step's delay counted from entry or from now, or completed.

A hold changes only ``next_due_at``. A step that is skipped or fails is finished: the sequence goes
on. An account that needs reconnecting is not picked up at all until it works again.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.broadcasts import QualityRating
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.models.sequences import (
    EnrolmentStatus,
    RunStatus,
    SequenceEnrolment,
    SequenceStatus,
    SequenceStep,
    SequenceStepRun,
)
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import OutboundTemplate
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import broadcasts as broadcast_repo
from socialhood.repositories import ingest as ingest_rows
from socialhood.repositories import sequences as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services import business_hours, sending
from socialhood.services.automations import actions, render
from socialhood.services.broadcasts import dispatch, health, throttle
from socialhood.services.broadcasts import variables as variable_rules
from socialhood.services.reply_window import reply_window
from socialhood.services.saved_replies import contact_values, fill
from socialhood.services.sequences import rules, schedule
from socialhood.services.webhooks import events

log = get_logger(__name__)

NAMESPACE = uuid.UUID("3d8f6a52-91b7-4c7e-8a5e-5b0a8f2c6d14")
HOLD_ACCOUNT = timedelta(minutes=15)
HOLD_QUALITY = timedelta(minutes=30)
HOLD_NO_HOURS = timedelta(days=1)  # business hours that never open: look again tomorrow
REASON_MAX = 300
ACCOUNT_CODES = frozenset({"account_needs_reconnect", "capability_unavailable"})


def client_id(enrolment_id: uuid.UUID, position: int) -> uuid.UUID:
    """The message's client id for one step of one enrolment: stable, so a step is never queued
    twice."""
    return uuid.uuid5(NAMESPACE, f"{enrolment_id}:{position}")


async def run_due(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    due: list[tuple[uuid.UUID, uuid.UUID]],
    *,
    now: datetime | None = None,
) -> Counter[str]:
    """Run the enrolments in ``due`` ((workspace, enrolment) pairs, found by the job across
    workspaces with ``repo.due``); returns how many ended each way (``sent``, ``skipped``,
    ``failed``, ``held``, ``completed``, ``gone``...)."""
    now = now or datetime.now(UTC)
    outcomes: Counter[str] = Counter()
    for workspace_id, enrolment_id in due:
        try:
            with workspace_scope(workspace_id):
                async with sessionmaker() as session:
                    outcome = await run_one(session, deps, enrolment_id, now)
                    await commit_and_publish(session, redis)
        except Exception:
            # One bad enrolment doesn't stop the rest; the next sweep tries it again.
            log.exception("sequence_step_failed", enrolment_id=str(enrolment_id))
            outcome = "error"
        outcomes[outcome] += 1
    return outcomes


async def run_one(
    session: AsyncSession, deps: PlatformDeps, enrolment_id: uuid.UUID, now: datetime
) -> str:
    """The module docstring's steps for one enrolment. Returns what happened."""
    row = await repo.get_enrolment(session, enrolment_id, lock=True, skip_locked=True)
    if (
        row is None
        or row.status != EnrolmentStatus.ACTIVE
        or row.next_due_at is None
        or row.next_due_at > now
    ):
        return "gone"
    sequence = await repo.get(session, row.sequence_id)
    if sequence is None or sequence.status != SequenceStatus.ACTIVE:
        return "inactive"
    steps = await repo.steps_of(session, sequence.id)
    step = next((s for s in steps if s.position == row.current_step), None)
    if step is None:  # the steps were taken away from under it
        _finish(row, now)
        await session.flush()
        await _completed(session, row, sequence.name)
        return "completed"
    acct = await accounts.get(session, row.social_account_id)
    contact = await repo.contact_of(session, row.contact_id)
    if acct is None or contact is None or acct.status != AccountStatus.ACTIVE:
        return await _hold(session, row, now + HOLD_ACCOUNT)
    if await repo.step_run(session, row.id, step.position) is not None:
        return await _advance(session, row, steps, now)  # already run: only move on

    if step.respect_hours:
        held = await _hours_hold(session, acct, now)
        if held is not None:
            return await _hold(session, row, held)

    conv = await ingest_rows.find_conversation_for_contact(session, acct.id, contact.id)
    window = reply_window(
        acct.platform, conv.last_inbound_at if conv else None, human_agent=False, now=now
    )
    decision = rules.decide(
        platform=acct.platform,
        window_open=window.state == "open",
        has_conversation=conv is not None,
        has_text=bool(step.text),
        has_template=bool(step.template_name),
        consent_skip=await dispatch.consent_skip(session, contact.id)
        if acct.platform == "whatsapp"
        else None,
        marketing_enabled=bool(deps.settings.broadcasts_enabled),
    )
    if decision.action == "skip":
        await _record(
            session, row, step, RunStatus.SKIPPED, now, code=decision.code, reason=decision.reason
        )
        return await _advance(session, row, steps, now, outcome="skipped")

    if decision.action == "template":
        held = await _template_hold(session, deps, acct, now)
        if held is not None:
            return await _hold(session, row, held)
        if conv is None:
            conv, _ = await ingest_rows.get_or_create_conversation(
                session, social_account_id=acct.id, contact_id=contact.id, platform=acct.platform
            )
    assert conv is not None  # a text send needs the conversation decide() checked
    return await _send(session, deps, row, step, steps, acct, contact, conv, decision.action, now)


async def _send(
    session: AsyncSession,
    deps: PlatformDeps,
    row: SequenceEnrolment,
    step: SequenceStep,
    steps: list[SequenceStep],
    acct: SocialAccount,
    contact: Contact,
    conv: Conversation,
    action: str,
    now: datetime,
) -> str:
    values = contact_values(contact)
    text: str | None = None
    template: OutboundTemplate | None = None
    if action == "text":
        text = render.with_disclosure(
            fill(step.text or "", values), await actions.disclosure(session)
        )
    else:
        params = variable_rules.resolve(step.variables, values)
        if params is None:
            await _record(
                session,
                row,
                step,
                RunStatus.SKIPPED,
                now,
                code="missing_value",
                reason=rules.REASONS["missing_value"],
            )
            return await _advance(session, row, steps, now, outcome="skipped")
        template = OutboundTemplate(
            name=step.template_name or "",
            language=step.template_language or "",
            params=tuple(params),
        )
    try:
        async with session.begin_nested():
            message: Message = await sending.queue_outbound(
                session,
                conv,
                source="automation",
                client_id=client_id(row.id, step.position),
                text=text,
                template=template,
                deps=deps,
                now=now,
            )
    except ApiError as error:
        if error.code in ACCOUNT_CODES:
            return await _hold(session, row, now + HOLD_ACCOUNT)
        if error.code == "reply_window_closed":
            await _record(
                session,
                row,
                step,
                RunStatus.SKIPPED,
                now,
                code="window_closed",
                reason=rules.REASONS["window_closed"],
            )
            return await _advance(session, row, steps, now, outcome="skipped")
        await _record(
            session,
            row,
            step,
            RunStatus.FAILED,
            now,
            code=error.code,
            reason=actions.api_error_reason(error)[:REASON_MAX],
        )
        return await _advance(session, row, steps, now, outcome="failed")
    await _record(session, row, step, RunStatus.SENT, now, sent_as=action, message_id=message.id)
    await events.sequence_event(
        session,
        "sequence.step_sent",
        contact,
        sequence_id=row.sequence_id,
        sequence_name=await repo.name_of(session, row.sequence_id),
        enrolment_id=row.id,
        step=step.position + 1,
        step_count=len(steps),
        sent_as=action,
        message_id=str(message.id),
    )
    return await _advance(session, row, steps, now, outcome="sent")


async def _hours_hold(session: AsyncSession, acct: SocialAccount, now: datetime) -> datetime | None:
    """When to look again if the account is closed now (business hours, GR-22); None if open."""
    found = await business_hours.active(session, acct.id)
    if found is None or business_hours.is_open(found.hours, now):
        return None
    return schedule.next_open_at(found.hours, now) or now + HOLD_NO_HOURS


async def _template_hold(
    session: AsyncSession, deps: PlatformDeps, acct: SocialAccount, now: datetime
) -> datetime | None:
    """When to look again if the number can't take a template now: its quality is Low, or its
    daily limit (shared with broadcasts) is used up; None if it can."""
    number = await health.current(session, deps, acct, now=now)
    if number is not None and number.quality_rating == QualityRating.RED:
        return now + HOLD_QUALITY
    daily_limit, _ = health.daily_limit_of(number)
    since = now - throttle.WINDOW
    recent = await broadcast_repo.dispatch_times(session, acct.id, since)
    recent += await repo.template_send_times(session, acct.id, since)
    room = throttle.room(daily_limit, len(recent))
    if room is not None and room <= 0:
        free_at = throttle.next_room_at(recent, daily_limit, now)
        return free_at or now + throttle.BATCH_EVERY
    return None


async def _hold(session: AsyncSession, row: SequenceEnrolment, until: datetime) -> str:
    row.next_due_at = until
    await session.flush()
    return "held"


async def _record(
    session: AsyncSession,
    row: SequenceEnrolment,
    step: SequenceStep,
    status: RunStatus,
    now: datetime,
    *,
    code: str | None = None,
    reason: str | None = None,
    sent_as: str | None = None,
    message_id: uuid.UUID | None = None,
) -> None:
    session.add(
        SequenceStepRun(
            enrolment_id=row.id,
            sequence_id=row.sequence_id,
            social_account_id=row.social_account_id,
            contact_id=row.contact_id,
            position=step.position,
            status=status,
            reason_code=code,
            reason=reason,
            sent_as=sent_as,
            message_id=message_id,
            ran_at=now,
        )
    )
    await session.flush()  # the unique (enrolment, position) refuses a second run of the step
    log.info(
        "sequence_step",
        sequence_id=str(row.sequence_id),
        position=step.position,
        status=str(status),
        skip_reason=code,
    )


def _finish(row: SequenceEnrolment, now: datetime) -> None:
    row.status = EnrolmentStatus.COMPLETED
    row.finished_at = now
    row.next_due_at = None


async def _completed(session: AsyncSession, row: SequenceEnrolment, name: str) -> None:
    """``sequence.completed`` for an enrolment that just reached the end."""
    contact = await repo.contact_of(session, row.contact_id)
    if contact is None:
        return
    await events.sequence_event(
        session,
        "sequence.completed",
        contact,
        sequence_id=row.sequence_id,
        sequence_name=name,
        enrolment_id=row.id,
    )


async def _advance(
    session: AsyncSession,
    row: SequenceEnrolment,
    steps: list[SequenceStep],
    now: datetime,
    *,
    outcome: str = "advanced",
) -> str:
    """Move to the next step, due after its delay, or complete the enrolment."""
    row.last_step_at = now
    row.current_step += 1
    upcoming = next((s for s in steps if s.position == row.current_step), None)
    if upcoming is None:
        _finish(row, now)
        outcome = "completed" if outcome == "advanced" else outcome
        await session.flush()
        await _completed(session, row, await repo.name_of(session, row.sequence_id))
    else:
        row.next_due_at = schedule.due_at(
            delay_seconds=upcoming.delay_seconds,
            delay_from=upcoming.delay_from,
            position=upcoming.position,
            enrolled_at=row.enrolled_at,
            previous_ran_at=now,
        )
    await session.flush()
    return outcome
