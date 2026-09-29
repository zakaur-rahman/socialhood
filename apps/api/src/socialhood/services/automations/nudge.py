"""The follow nudge, never a follow gate (T4.8; FR-AUT-22).

An automation with the nudge on sends one more message after its message, only to people
Instagram reports as not following the account (``is_user_follow_business``): the nudge text with
the disclosure line and a "View profile" link button to the account's profile. The message itself
is never held back or changed by the follow status (Meta's Spam Community Standard forbids
requiring follows for content).

It goes out only once the run's message has reached Instagram, so it always follows the message
in the conversation: ``after_message`` (called by services/automations/results when a run's
message is sent) enqueues ``run_automation("nudge", run_id)``, whose body is ``run``. The follow
status is read fresh when the person has just written: a tap-first answer reads it before its
message (services/automations/answers); a DM keyword run reads it here. Unknown (the profile is
refused or silent) means no nudge. A comment run without tap first never nudges: nobody has
answered, so Instagram allows no further message and the profile cannot be read; an AI-reply
automation ignores the setting. The run records
the follow status and the nudge message; the nudge is queued once (``nudge_message_id``, a stable
``client_id``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.errors import ApiError
from socialhood.models.automations import AutomationRun
from socialhood.models.inbox import Conversation, MessageStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime import events
from socialhood.repositories import automation_runs as runs
from socialhood.repositories import inbox
from socialhood.repositories import ingest as rows
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations import actions

log = get_logger(__name__)

DELIVERED = frozenset({MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ})
# "missing": the message is not recorded as sent yet (the runtime looks again soon).
NudgeOutcome = Literal["missing", "sent", "already_sent", "skipped"]


def _eligible(run: AutomationRun) -> bool:
    """A run whose person wrote to the account (a DM trigger, or a tap-first answer) and who is
    not known to follow it. A tap-first answer's follow status was read when it came in."""
    if run.nudge_message_id is not None or run.follows_business is True:
        return False
    if run.confirmed_at is not None:
        return run.follows_business is False
    return run.trigger_message_id is not None


async def after_message(session: AsyncSession, run: AutomationRun) -> None:
    """The run's message reached Instagram: enqueue the nudge when one may be due."""
    if not _eligible(run):
        return
    automation = await runs.get_automation(session, run.automation_id)
    if automation is None or actions.render_nudge(automation, None, disclosure_line=None) is None:
        return
    from socialhood.services.automations.runtime import enqueue_run

    try:
        await enqueue_run("nudge", run.id, run.workspace_id)
    except Exception:  # never fail the send that called this; the nudge is only a nudge
        log.warning("follow_nudge_enqueue_failed", run_id=str(run.id))


async def run(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    run_id: uuid.UUID,
    now: datetime,
) -> NudgeOutcome:
    """The nudge job's body (``run_automation("nudge", run_id)``)."""
    from socialhood.services.ingest_followups import follow_status

    async with sessionmaker() as session:
        row = await runs.get(session, run_id)
        if row is None:
            return "skipped"
        if row.nudge_message_id is not None:
            return "already_sent"
        automation = await runs.get_automation(session, row.automation_id)
        dm = (
            await inbox.get_message(session, row.private_reply_message_id)
            if row.private_reply_message_id
            else None
        )
        if (
            dm is None
            or automation is None
            or actions.render_nudge(automation, None, disclosure_line=None) is None
        ):
            return "skipped"
        if dm.status not in DELIVERED:
            return "skipped" if dm.status == MessageStatus.FAILED else "missing"
        if not _eligible(row) or row.contact_id is None:
            return "skipped"
        contact_id, conversation_id = row.contact_id, dm.conversation_id
        check = row.confirmed_at is None  # a DM keyword run: read it now
        follows = row.follows_business
    if check:
        follows = await follow_status(sessionmaker, redis, deps, contact_id=contact_id, now=now)

    async with sessionmaker() as session:
        conv = await rows.lock_conversation(session, conversation_id)
        row = await runs.lock(session, run_id)
        if row is None or row.nudge_message_id is not None:
            return "already_sent"
        if check:
            row.follows_business = follows
        if follows is not False or conv is None:
            await session.commit()
            return "skipped"
        automation = await runs.get_automation(session, row.automation_id)
        contact = await inbox.get_contact(session, contact_id)
        acct = await accounts.get(session, conv.social_account_id)
        text = (
            actions.render_nudge(
                automation, contact, disclosure_line=await actions.disclosure(session)
            )
            if automation is not None
            else None
        )
        if text is None or acct is None:
            await session.commit()
            return "skipped"
        sent = await _queue(session, deps, row, conv, text, acct.username, now=now)
        await session.flush()
        await events.commit_and_publish(session, redis)
    return "sent" if sent else "skipped"


async def _queue(
    session: AsyncSession,
    deps: PlatformDeps,
    row: AutomationRun,
    conv: Conversation,
    text: str,
    username: str | None,
    *,
    now: datetime,
) -> bool:
    """The nudge, with its "View profile" button, through the send pipeline."""
    from socialhood.services import sending  # sending → … → ingest → the runtime

    try:
        nudge = await sending.queue_outbound(
            session,
            conv,
            source="automation",
            client_id=actions.client_id_for(row.id, "nudge"),
            text=text,
            buttons=actions.nudge_buttons(username),
            automation_run_id=row.id,
            deps=deps,
            now=now,
        )
    except ApiError as error:
        log.info("follow_nudge_refused", run_id=str(row.id), error_code=error.code)
        return False
    row.nudge_message_id = nudge.id
    log.info("follow_nudge_queued", run_id=str(row.id), message_id=str(nudge.id))
    return True
