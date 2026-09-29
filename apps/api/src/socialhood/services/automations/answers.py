"""Tap first: the commenter's answer releases the automation's message (T4.8; FR-AUT-21,
FR-AUT-22).

A tap-first comment run's private reply is its opening, with one quick reply whose payload is
``shr:{run_id}``; the run then waits (``awaiting_reply``). Before DM keyword matching, the
runtime asks ``find`` what a new customer message from contact C on account A answers, among C's
waiting runs on A whose opening went out in the last 7 days:

- a tapped quick reply naming one of C's runs on A answers that run only (once it has been
  released, a second tap answers it again and sends nothing);
- anything else they write (quick replies are not shown on desktop) answers every waiting run,
  oldest first, at most 3;
- otherwise the message answers nothing and keyword automations run as usual.

An answering message is marked ``automation_handled``, so no DM keyword automation and no AI
reply runs on it. ``release`` then reads the profile fresh (their answer is the consent the
profile API needs), which refreshes the contact's name and tells whether they follow the
account; then, under each run's row lock and only while ``confirmed_at`` is empty, it sets
``confirmed_at`` and ``follows_business`` and hands the message (text with the real first name
and the disclosure line, image, link buttons) to services/sending.queue_outbound. The run
follows that send (services/automations/results). A second tap or a redelivered webhook finds
the runs released and sends nothing more. The follow status never holds the message back; a
nudge for people who don't follow comes after it (services/automations/nudge).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.errors import ApiError
from socialhood.models.automations import Automation, AutomationAction, AutomationRun, RunResult
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime import events
from socialhood.repositories import automation_runs as runs
from socialhood.repositories import inbox
from socialhood.repositories import ingest as rows
from socialhood.services.automations import actions, results

log = get_logger(__name__)

ANSWER_WINDOW = timedelta(days=7)  # openings older than this are not released
MAX_RELEASED = 3  # runs one typed reply releases


@dataclass(frozen=True)
class Answer:
    """What a customer message answers: the runs to release, oldest first. Empty when it
    taps an opening already answered (it is still handled, and sends nothing)."""

    run_ids: list[uuid.UUID]


async def find(
    session: AsyncSession, msg: Message, contact_id: uuid.UUID, *, now: datetime
) -> Answer | None:
    """None when the message answers no tap-first opening."""
    since = now - ANSWER_WINDOW
    tapped = actions.tapped_run_id(msg.quick_reply_payload)
    if tapped is not None:
        run = await runs.tapped_run(session, tapped, contact_id, msg.social_account_id)
        if run is not None and run.confirmed_at is not None:
            return Answer([])  # a second tap
        if (
            run is not None
            and run.result == RunResult.AWAITING_REPLY
            and await runs.opening_sent_since(session, run.id, since)
        ):
            return Answer([run.id])
    waiting = await runs.awaiting_for(
        session, contact_id, msg.social_account_id, since=since, limit=MAX_RELEASED
    )
    return Answer(waiting) if waiting else None


async def release(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    contact_id: uuid.UUID,
    answer: Answer,
    now: datetime,
) -> int:
    """Mark the answering message handled and send each run's message once; returns how many
    runs this call released."""
    from socialhood.services.ingest_followups import follow_status

    follows: bool | None = None
    if answer.run_ids:
        # Their answer allows the profile lookup: the real first name, and the follow status.
        follows = await follow_status(sessionmaker, redis, deps, contact_id=contact_id, now=now)
    released = 0
    async with sessionmaker() as session:
        # Conversation, then message, then runs: the order ingest takes them in.
        conv = await rows.lock_conversation(session, conversation_id)
        msg = await rows.lock_message(session, message_id)
        contact = await inbox.get_contact(session, contact_id)
        if conv is None or msg is None or contact is None:
            return 0
        msg.automation_handled = True  # FR-AUT-07 and FR-AUT-21: no keyword automation, no AI
        disclosure = await actions.disclosure(session)
        for run_id in answer.run_ids:
            run = await runs.lock(session, run_id)
            if run is None or run.result != RunResult.AWAITING_REPLY or run.confirmed_at:
                continue  # released already (a second tap, or a redelivery)
            automation = await runs.get_automation(session, run.automation_id)
            if automation is None:
                continue
            run.confirmed_at = now
            run.follows_business = follows
            run.conversation_id = conv.id
            await _send(session, deps, automation, run, conv, contact, disclosure, now=now)
            released += 1
            log.info(
                "automation_answered",
                automation_id=str(automation.id),
                run_id=str(run.id),
                result=run.result,
                follows_business=follows,
            )
        await session.flush()
        await events.commit_and_publish(session, redis)
    return released


async def _send(
    session: AsyncSession,
    deps: PlatformDeps,
    automation: Automation,
    run: AutomationRun,
    conv: Conversation,
    contact: Contact,
    disclosure: str | None,
    *,
    now: datetime,
) -> None:
    """The automation's message, as a DM in the window their answer opened."""
    from socialhood.services import sending  # sending → … → ingest → the runtime

    if automation.action != AutomationAction.SEND_MESSAGE:
        results.answered_failed(run, *actions.AI_UNAVAILABLE)
        return
    text = actions.render_message(automation, contact, username=None, disclosure_line=disclosure)
    if text is None:
        results.answered_failed(run, *actions.NO_MESSAGE)
        return
    image = automation.message_media_asset_id
    try:
        dm = await sending.queue_outbound(
            session,
            conv,
            source="automation",
            client_id=actions.client_id_for(run.id, "message"),
            text=text,
            attachment_asset_ids=[image] if image else (),
            buttons=actions.buttons(automation),
            automation_run_id=run.id,
            deps=deps,
            now=now,
        )
    except ApiError as error:
        results.answered_failed(run, error.code, actions.api_error_reason(error))
        return
    # The run's DM is now the message (the opening stays linked from the comment).
    run.private_reply_message_id = dm.id
    results.hand_over(run)
