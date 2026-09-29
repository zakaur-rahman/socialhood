"""The automation runtime (T4.4, T4.8; F-11 runtime, F-12, FR-AUT-05…08, FR-AUT-14, FR-AUT-16,
FR-AUT-21, FR-AUT-22).

Entry points for ingest and comment intake, called in their transaction after the row exists:
- ``enqueue_for_message`` / ``enqueue_for_comment`` enqueue ``run_automation(kind, id)`` (key and
  lock ``automation:{kind}:{id}``) when the account has an active automation of that kind, or
  (DMs) when a tap-first opening waits for the contact's answer;
- ``contact_replied`` records FR-AUT-16's reply within 24 h of an automation DM.

Tap first (FR-AUT-21): before keyword matching, a customer DM that answers a waiting opening
releases that run's message and nothing else runs on it (services/automations/answers). The
follow nudge (FR-AUT-22) is ``run_automation("nudge", run_id)``, enqueued once a run's message
has been sent (services/automations/nudge).

``run`` is the job body. It loads the account's active automations of the trigger type inside
their run window and matches the text (services/automations/matching: keyword automations before
any-comment ones, then priority, then the oldest). Matches are tried in that order: one outside
its post scope is passed over, one on cooldown for the contact records a ``skipped_cooldown`` run
and is passed over, and the first that passes records its run (unique per automation and event)
and acts. Any run already recorded for the event means the event was handled: running it again
sends nothing.

- DM: the message (personal fields, disclosure line, image, link buttons) goes through
  services/sending.queue_outbound with source ``automation``, linked to the run; the trigger
  message is marked ``automation_handled`` so the AI leaves it alone (FR-AUT-07). The run is
  ``sent`` at hand-over and follows the send (services/automations/results).
- Comment: the run is recorded ``queued`` and committed before anything is sent. The public reply
  variation is posted at once (FR-AUT-14; its failure never stops the DM, FR-AUT-08) and the
  private reply waits in the account's queue (services/automations/queue, TR-JOB-07). A
  public-reply-only automation never DMs. A reply in a comment thread triggers keyword
  automations only: "any comment" automations answer top-level comments.

AI replies arrive in P5: an ``ai_reply`` automation that runs anyway records a failed run and sends
nothing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.errors import ApiError
from socialhood.models.automations import (
    Automation,
    AutomationAction,
    AutomationRun,
    Comment,
    RunResult,
    SurgeOrder,
)
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Conversation, Direction, Message, MessageSource
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.realtime import events
from socialhood.repositories import automation_runs as runs
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import inbox
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations import actions, matching, results

log = get_logger(__name__)

Kind = Literal["dm", "comment", "nudge"]

DM_TRIGGERS = ("dm_keyword",)
COMMENT_TRIGGERS = ("comment_keyword", "comment_any")
THREAD_REPLY_TRIGGERS = ("comment_keyword",)
START_DELAY_S = 1.0  # the caller commits after enqueueing; well before AI analysis (4 s)
NOT_FOUND_RETRIES = 5
NOT_FOUND_DELAY_S = 1.0
REPLY_WINDOW = timedelta(hours=24)  # FR-AUT-16
PRIVATE_REPLY_LIMIT = timedelta(days=7)  # FR-AUT-10
EXPIRED = ("expired", "Instagram's 7-day limit passed")
AI_UNAVAILABLE = actions.AI_UNAVAILABLE
NO_MESSAGE = actions.NO_MESSAGE


class Outcome(StrEnum):
    MISSING = "missing"  # the trigger row is not visible (yet)
    IGNORED = "ignored"  # not a customer message, or its account is gone
    NO_MATCH = "no_match"
    ALREADY_RAN = "already_ran"
    SKIPPED = "skipped"  # every match was on cooldown, out of scope or expired
    FIRED = "fired"
    ANSWERED = "answered"  # the DM answered a tap-first opening (FR-AUT-21)


# ---------------------------------------------------------------- entry points


async def enqueue_for_message(
    session: AsyncSession, message: Message, *, contact_id: uuid.UUID | None = None
) -> bool:
    """A new inbound customer DM (not an echo, not backfill) from ``contact_id``."""
    from socialhood.services.automations.answers import ANSWER_WINDOW

    answers_opening = contact_id is not None and await runs.has_awaiting(
        session, contact_id, since=datetime.now(UTC) - ANSWER_WINDOW
    )
    if not answers_opening and not await runs.has_active(
        session, message.social_account_id, DM_TRIGGERS
    ):
        return False
    return await enqueue_run("dm", message.id, message.workspace_id)


async def enqueue_for_comment(session: AsyncSession, comment: Comment) -> bool:
    """A new comment from someone other than the account."""
    if not await runs.has_active(session, comment.social_account_id, COMMENT_TRIGGERS):
        return False
    return await enqueue_run("comment", comment.id, comment.workspace_id)


async def enqueue_run(
    kind: Kind,
    trigger_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    delay_s: float = START_DELAY_S,
    not_found: int = 0,
) -> bool:
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.automations import run_automation

    key = f"automation:{kind}:{trigger_id}"
    return await enqueue(
        run_automation,
        key=key,
        lock=key,
        delay_s=delay_s,
        kind=kind,
        trigger_id=str(trigger_id),
        workspace_id=str(workspace_id),
        not_found=not_found,
    )


async def contact_replied(session: AsyncSession, contact_id: uuid.UUID, *, at: datetime) -> int:
    """FR-AUT-16: the contact wrote; count it on runs that reached them in the 24 h before."""
    return await runs.mark_contact_replied(session, contact_id, at=at, window=REPLY_WINDOW)


# ---------------------------------------------------------------- the job


@dataclass(frozen=True)
class _Env:
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    deps: PlatformDeps
    now: datetime


async def run(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    kind: str,
    trigger_id: uuid.UUID,
    workspace_id: uuid.UUID,
    not_found: int = 0,
    now: datetime | None = None,
) -> Outcome:
    """run_automation(kind, id), in the event's workspace scope."""
    env = _Env(sessionmaker, redis, deps, now or datetime.now(UTC))
    handlers = {"dm": _run_dm, "comment": _run_comment, "nudge": _run_nudge}
    handler = handlers.get(kind)
    if handler is None:
        log.warning("automation_unknown_kind", kind=kind)
        return Outcome.IGNORED
    outcome = await handler(env, trigger_id)
    if outcome is Outcome.MISSING:
        if not_found < NOT_FOUND_RETRIES:
            await enqueue_run(
                cast(Kind, kind),
                trigger_id,
                workspace_id,
                delay_s=NOT_FOUND_DELAY_S * (not_found + 1),
                not_found=not_found + 1,
            )
        else:
            log.warning("automation_trigger_missing", kind=kind, trigger_id=str(trigger_id))
    log.info("automation_run", kind=kind, trigger_id=str(trigger_id), outcome=str(outcome))
    return outcome


def _run_row(
    automation: Automation,
    keyword: str,
    *,
    result: RunResult,
    now: datetime,
    contact_id: uuid.UUID | None,
    **values: Any,
) -> dict[str, Any]:
    return actions.run_values(
        automation_id=automation.id,
        matched_keyword=keyword,
        result=result,
        contact_id=contact_id,
        created_at=now,
        updated_at=now,
        **values,
    )


async def _cooling(
    session: AsyncSession, automation: Automation, contact_id: uuid.UUID | None, now: datetime
) -> bool:
    """FR-AUT-05: at most once per contact per cooldown (0 = no cooldown)."""
    if contact_id is None or automation.cooldown_hours <= 0:
        return False
    since = now - timedelta(hours=automation.cooldown_hours)
    return await runs.on_cooldown(session, automation.id, contact_id, since=since)


# ---- DMs


async def _run_dm(env: _Env, message_id: uuid.UUID) -> Outcome:
    from socialhood.services.automations import answers

    async with env.sessionmaker() as session:
        msg = await inbox.get_message(session, message_id)
        if msg is None:
            return Outcome.MISSING
        if msg.direction != Direction.INBOUND or msg.source != MessageSource.CUSTOMER:
            return Outcome.IGNORED
        conv = await inbox.get_conversation(session, msg.conversation_id)
        contact = await inbox.get_contact(session, conv.contact_id) if conv else None
        if conv is None or contact is None:
            return Outcome.IGNORED
        if msg.automation_handled or await runs.event_runs(session, message_id=msg.id):
            return Outcome.ALREADY_RAN
        # Tap first (FR-AUT-21): an answer to a waiting opening comes before any keyword.
        answer = await answers.find(session, msg, contact.id, now=env.now)
        if answer is None:
            return await _match_dm(session, env, msg, conv, contact)
    released = await answers.release(
        env.sessionmaker,
        env.redis,
        env.deps,
        message_id=message_id,
        conversation_id=conv.id,
        contact_id=contact.id,
        answer=answer,
        now=env.now,
    )
    log.info("automation_answer", message_id=str(message_id), released=released)
    return Outcome.ANSWERED


async def _match_dm(
    session: AsyncSession, env: _Env, msg: Message, conv: Conversation, contact: Contact
) -> Outcome:
    """DM keyword automations (F-11 runtime): the first match that passes sends its message."""
    loaded = await runs.candidates(session, msg.social_account_id, DM_TRIGGERS, now=env.now)
    found = matching.matches(msg.text or "", [item.candidate for item in loaded])
    if not found:
        return Outcome.NO_MATCH
    by_id = {item.automation.id: item.automation for item in loaded}
    for match in found:
        automation = by_id[match.automation_id]
        common: dict[str, Any] = {
            "contact_id": contact.id,
            "now": env.now,
            "trigger_message_id": msg.id,
        }
        if await _cooling(session, automation, contact.id, env.now):
            await runs.insert_run(
                session,
                _run_row(automation, match.keyword, result=RunResult.SKIPPED_COOLDOWN, **common),
            )
            continue
        run = await runs.insert_run(
            session,
            _run_row(
                automation,
                match.keyword,
                result=RunResult.SENT,
                conversation_id=conv.id,
                **common,
            ),
        )
        if run is None:  # another worker ran this event first
            await session.rollback()
            return Outcome.ALREADY_RAN
        automation.last_run_at = env.now
        await _send_dm(session, env, automation, run, msg, conv, contact)
        await session.flush()
        await events.commit_and_publish(session, env.redis)
        log.info(
            "automation_fired",
            automation_id=str(automation.id),
            run_id=str(run.id),
            result=run.result,
        )
        return Outcome.FIRED
    await session.commit()
    return Outcome.SKIPPED


# ---- the follow nudge (FR-AUT-22)


async def _run_nudge(env: _Env, run_id: uuid.UUID) -> Outcome:
    from socialhood.services.automations import nudge

    outcome = await nudge.run(env.sessionmaker, env.redis, env.deps, run_id=run_id, now=env.now)
    return {
        "missing": Outcome.MISSING,
        "sent": Outcome.FIRED,
        "already_sent": Outcome.ALREADY_RAN,
        "skipped": Outcome.SKIPPED,
    }[outcome]


async def _send_dm(
    session: AsyncSession,
    env: _Env,
    automation: Automation,
    run: AutomationRun,
    msg: Message,
    conv: Conversation,
    contact: Contact,
) -> None:
    from socialhood.services import sending  # sending → … → ingest → this module

    if automation.action != AutomationAction.SEND_MESSAGE:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = AI_UNAVAILABLE
        return
    text = await actions.message_text(session, automation, contact)
    if text is None:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = NO_MESSAGE
        return
    image = automation.message_media_asset_id
    try:
        dm = await sending.queue_outbound(
            session,
            conv,
            source="automation",
            client_id=actions.client_id_for(run.id),
            text=text,
            attachment_asset_ids=[image] if image else (),
            buttons=actions.buttons(automation),
            automation_run_id=run.id,
            deps=env.deps,
            now=env.now,
        )
    except ApiError as error:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = error.code, actions.api_error_reason(error)
        return
    run.private_reply_message_id = dm.id  # the DM this run sent (the run log links it)
    msg.automation_handled = True  # FR-AUT-07


# ---- comments


@dataclass(frozen=True)
class _Plan:
    dm: bool  # a private reply goes to the queue
    public: bool  # a public reply variation is posted now


def _plan(automation: Automation) -> _Plan:
    if automation.action != AutomationAction.SEND_MESSAGE:
        return _Plan(dm=False, public=False)
    has_dm = bool(automation.message_text and automation.message_text.strip())
    return _Plan(
        dm=has_dm and automation.surge_order != SurgeOrder.PUBLIC_ONLY,
        public=bool(automation.public_reply_texts),
    )


@dataclass(frozen=True)
class _Fired:
    automation: Automation
    run_id: uuid.UUID
    plan: _Plan
    variant: int | None


async def _run_comment(env: _Env, comment_id: uuid.UUID) -> Outcome:
    async with env.sessionmaker() as session:
        comment = await comments_repo.get(session, comment_id)
        if comment is None:
            return Outcome.MISSING
        acct = await accounts.get(session, comment.social_account_id)
        if acct is None:
            return Outcome.IGNORED
        earlier = await runs.event_runs(session, comment_id=comment.id)
        if earlier:
            if any(r.result == RunResult.QUEUED for r in earlier):
                await _enqueue_drain(acct)  # in case the first run could not
            return Outcome.ALREADY_RAN
        triggers = THREAD_REPLY_TRIGGERS if comment.parent_platform_comment_id else COMMENT_TRIGGERS
        loaded = await runs.candidates(session, acct.id, triggers, now=env.now)
        found = matching.matches(comment.text, [item.candidate for item in loaded])
        if not found:
            return Outcome.NO_MATCH
        contact = (
            await inbox.get_contact(session, comment.contact_id) if comment.contact_id else None
        )
        fired = await _first_passing(session, env, comment, contact, loaded, found)
        if fired is None:
            await session.commit()
            return Outcome.SKIPPED
        if isinstance(fired, Outcome):
            await session.rollback()
            return fired
        # The run exists before anything is sent: a second run of this event sends nothing.
        await session.commit()

    if fired.plan.public and fired.variant is not None:
        await _post_public_reply(env, acct, comment, contact, fired)
    if fired.plan.dm:
        await _enqueue_drain(acct)
    log.info("automation_fired", automation_id=str(fired.automation.id), run_id=str(fired.run_id))
    return Outcome.FIRED


async def _first_passing(
    session: AsyncSession,
    env: _Env,
    comment: Comment,
    contact: Contact | None,
    loaded: list[runs.Loaded],
    found: list[matching.Match],
) -> _Fired | Outcome | None:
    by_id = {item.automation.id: item.automation for item in loaded}
    expired = env.now - comment.commented_at >= PRIVATE_REPLY_LIMIT
    for match in found:
        automation = by_id[match.automation_id]
        if not await runs.in_scope(session, automation, comment.media_item_id):
            continue
        common: dict[str, Any] = {
            "contact_id": comment.contact_id,
            "now": env.now,
            "trigger_comment_id": comment.id,
        }
        if await _cooling(session, automation, comment.contact_id, env.now):
            await runs.insert_run(
                session,
                _run_row(automation, match.keyword, result=RunResult.SKIPPED_COOLDOWN, **common),
            )
            continue
        if expired:
            code, reason = EXPIRED
            await runs.insert_run(
                session,
                _run_row(
                    automation,
                    match.keyword,
                    result=RunResult.SKIPPED_EXPIRED,
                    error_code=code,
                    error_message=reason,
                    **common,
                ),
            )
            return None
        plan = _plan(automation)
        variant = None
        if plan.public:
            last = await runs.last_variant(session, automation.id, comment.media_item_id)
            variant = actions.choose_variant(len(automation.public_reply_texts), last)
        values = _run_row(
            automation,
            match.keyword,
            result=RunResult.QUEUED if plan.dm else RunResult.SENT,
            public_reply_variant=variant,
            **common,
        )
        if automation.action != AutomationAction.SEND_MESSAGE:
            values.update(
                result=RunResult.FAILED,
                error_code=AI_UNAVAILABLE[0],
                error_message=AI_UNAVAILABLE[1],
            )
        elif not plan.dm and not plan.public:
            values.update(
                result=RunResult.FAILED, error_code=NO_MESSAGE[0], error_message=NO_MESSAGE[1]
            )
        run = await runs.insert_run(session, values)
        if run is None:
            return Outcome.ALREADY_RAN
        automation.last_run_at = env.now
        await session.flush()
        return _Fired(automation, run.id, plan, variant)
    return None


async def _post_public_reply(
    env: _Env,
    acct: SocialAccount,
    comment: Comment,
    contact: Contact | None,
    fired: _Fired,
) -> None:
    """FR-AUT-14: one variation, posted now; the result is kept on the comment and the run."""
    from socialhood.services.connections import mark_needs_reconnect
    from socialhood.services.sending import BLOCKED_STATUSES, readable_error

    assert fired.variant is not None
    text = actions.public_reply(
        fired.automation, fired.variant, contact, username=comment.author_username
    )
    reply_id: str | None = None
    error: tuple[str, str] | None = None
    if acct.status in BLOCKED_STATUSES:
        error = (
            "account_needs_reconnect",
            readable_error("account_needs_reconnect", acct.platform, username=acct.username),
        )
    else:
        try:
            reply_id = await adapter_for(acct, env.deps).reply_to_comment(
                acct, comment.platform_comment_id, text
            )
        except PlatformError as failure:
            error = (failure.code, actions.platform_error_reason(failure, acct))
            log.info(
                "automation_public_reply_failed",
                run_id=str(fired.run_id),
                error_code=failure.code,
                platform_code=failure.platform_code,
            )
    async with env.sessionmaker() as session:
        run = await runs.lock(session, fired.run_id)
        stored = await comments_repo.lock(session, comment.id)
        if error is None and stored is not None:
            stored.our_reply_platform_id = reply_id
            stored.our_reply_text = text
            stored.our_replied_at = env.now
        if run is not None:
            results.record_public(
                run,
                reply_id=reply_id,
                error=error,
                dm_planned=fired.plan.dm,
            )
        if error is not None and error[0] == "account_needs_reconnect":
            fresh = await accounts.get(session, acct.id)
            if fresh is not None and fresh.status not in BLOCKED_STATUSES:
                await mark_needs_reconnect(
                    session, fresh, "Instagram stopped accepting this connection."
                )
        await session.commit()


async def _enqueue_drain(acct: SocialAccount) -> None:
    from socialhood.services.automations import queue

    await queue.enqueue_drain(acct.id, acct.workspace_id)
