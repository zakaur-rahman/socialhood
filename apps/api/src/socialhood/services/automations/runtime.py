"""The automation runtime (T4.4, T4.8; F-11 runtime, F-12, FR-AUT-05…08, FR-AUT-14, FR-AUT-16,
FR-AUT-21, FR-AUT-22).

Entry points for ingest and comment intake, called in their transaction after the row exists:
- ``enqueue_for_message`` / ``enqueue_for_comment`` enqueue ``run_automation(kind, id)`` (key and
  lock ``automation:{kind}:{id}``) when the account has an active automation of that kind, or
  (DMs) when a tap-first opening waits for the contact's answer;
- ``contact_replied`` records FR-AUT-16's reply within 24 h of an automation DM.

Story triggers (GR-06, GR-07): a story reply and a story mention are DMs, so they take this path;
``dm_triggers`` picks the automations a message can start by its kind. A story reply starts story
reply and DM keyword automations together (keyword ones first, then those that answer anything,
each by priority); a story reply automation scoped to chosen stories passes over replies to other
stories. A reply that is only the heart (a story like) starts story reply automations never. A
story mention starts story mention automations only, and never answers a waiting question. A story
reply automation with the heart on sends Instagram's heart sticker ahead of its message (its
failure never stops the DM).

Entry triggers (GR-08, GR-09): a DM that is the first message after an entry link or an ad
(services/automations/entry) also starts ``entry_link`` and ``ad_click`` automations, ahead of the
keyword ones: an entry link starts the automation its link points at, an ad click any ad or its
chosen ads. A story mention is never an entry.

Live comments (GR-10): a comment on a Live broadcast is answered by comment automations whose
``comment_surface`` is ``live`` or ``both`` (posts-only ones pass it over, and Live comments
ignore post scopes). A private reply works only while the Live is on air, and Instagram sends no
"Live ended" event: a Live comment older than ``LIVE_REPLY_WINDOW`` when it is matched records a
``skipped_expired`` run with the code ``live_ended`` and nothing is sent. The private-reply queue
sends Live-only automations' runs ahead of everything else and expires the ones it could not send
in time the same way (services/automations/queue).

Conversation starters (GR-11): a postback whose payload is one of the account's ice breakers
starts ice breaker automations only, and only the one its starter maps to (services/ice_breakers);
it answers no waiting question. A starter set to answer with AI starts nothing here: the message
is not marked handled, so the inbox AI answers it like any customer message.

Welcome and default reply (GR-12): an ordinary DM (not a story reply or mention, not a button,
quick reply or ice breaker tap) can also start the two fallbacks, only when no keyword or other
automation took it. A keyword that matched but was on cooldown still counts as having matched, so
a repeated question gets no default reply. The welcome (``first_message``) needs the contact to
have no earlier customer message to this account; the default reply needs AI off for the
conversation (its override, else the account's mode). If both apply, the welcome answers and the
default reply does not. Each obeys its own cooldown per contact.

Business hours (GR-22): an automation may require ``inside`` or ``outside`` hours
(``hours_condition``); one that doesn't hold passes over the message or comment like a scope
mismatch does (an account with no hours is always inside). After the automations, a DM that none
answered (no match, or every match skipped) gets the away message when the account is closed, once
per closed window and never on top of an automation, a flow answer or an Auto-mode reply
(services/business_hours). The order is: a waiting answer, then automations (keyword, welcome and
default reply), then the away message, then nothing else.

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
sends nothing. On an account that is read-only after a downgrade (FR-BIL-07; the downgrade pauses
its automations, this guards the rest) the first match that isn't cooling down records a
``skipped_read_only`` run with the plan's reason instead, and nothing is sent.

- DM: the message (personal fields, disclosure line, image, link buttons) goes through
  services/sending.queue_outbound with source ``automation``, linked to the run; the trigger
  message is marked ``automation_handled`` so the AI leaves it alone (FR-AUT-07). The run is
  ``sent`` at hand-over and follows the send (services/automations/results).
- Comment: the run is recorded ``queued`` and committed before anything is sent. The public reply
  variation is posted at once (FR-AUT-14; its failure never stops the DM, FR-AUT-08) and the
  private reply waits in the account's queue (services/automations/queue, TR-JOB-07). A
  public-reply-only automation never DMs. A reply in a comment thread triggers keyword
  automations only: "any comment" automations answer top-level comments.

AI replies (T5.8, services/automations/ai_reply): a DM's run is recorded ``queued`` with the
trigger marked automation_handled and committed, then the reply is drafted and sent (``sent``) or
the conversation escalated (``escalated``); a retried job resumes a run left queued. A comment's
run is queued like any private reply and the queue drafts it before sending.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.entitlements import read_only_error
from socialhood.errors import ApiError
from socialhood.models.automations import (
    Automation,
    AutomationAction,
    AutomationRun,
    Comment,
    CommentSurface,
    HoursCondition,
    PostScope,
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
from socialhood.repositories import ingest as ingest_rows
from socialhood.repositories import social_accounts as accounts
from socialhood.services import business_hours, ice_breakers
from socialhood.services.automations import (
    actions,
    ai_reply,
    engine,
    entry,
    flows,
    matching,
    results,
)

log = get_logger(__name__)

Kind = Literal["dm", "comment", "nudge", "flow"]

DM_TRIGGERS = ("dm_keyword",)
STORY_REPLY_TRIGGERS = ("story_reply", "dm_keyword")
STORY_MENTION_TRIGGERS = ("story_mention",)
ICE_BREAKER_TRIGGERS = ("ice_breaker",)
FALLBACK_TRIGGERS = matching.FALLBACK_TRIGGERS  # GR-12
HEART = "\u2764\ufe0f"  # a story like arrives as the heart sticker, stored as its emoji
COMMENT_TRIGGERS = ("comment_keyword", "comment_any")
THREAD_REPLY_TRIGGERS = ("comment_keyword",)
START_DELAY_S = 1.0  # the caller commits after enqueueing; well before AI analysis (4 s)
NOT_FOUND_RETRIES = 5
NOT_FOUND_DELAY_S = 1.0
REPLY_WINDOW = timedelta(hours=24)  # FR-AUT-16
PRIVATE_REPLY_LIMIT = timedelta(days=7)  # FR-AUT-10
EXPIRED = ("expired", "Instagram's 7-day limit passed")
LIVE_ENDED = actions.LIVE_ENDED  # GR-10
LIVE_REPLY_WINDOW = actions.LIVE_REPLY_WINDOW
NO_MESSAGE = actions.NO_MESSAGE
READ_ONLY = "read_only"  # a skipped_read_only run's error_code (FR-BIL-07)


class Outcome(StrEnum):
    MISSING = "missing"  # the trigger row is not visible (yet)
    IGNORED = "ignored"  # not a customer message, or its account is gone
    NO_MATCH = "no_match"
    ALREADY_RAN = "already_ran"
    SKIPPED = "skipped"  # every match was on cooldown, out of scope or expired
    FIRED = "fired"
    ANSWERED = "answered"  # the DM answered a tap-first opening (FR-AUT-21)


# ---------------------------------------------------------------- entry points


def story_id_of(msg: Message) -> str | None:
    """The story a story reply answers (its attachment's platform id), when we kept it."""
    for attachment in msg.attachments or []:
        if attachment.get("type") == "story" and attachment.get("media_id"):
            return str(attachment["media_id"])
    return None


def is_story_like(msg: Message) -> bool:
    """A story reply that is just the heart: someone liked the story, which is no reply."""
    return msg.kind == "story_reply" and (msg.text or "").strip() == HEART


def is_ordinary_dm(msg: Message) -> bool:
    """A message the welcome and default reply may answer: not a story reply or mention, and not
    a tap on a button, quick reply or ice breaker (those answer something we sent)."""
    return (
        msg.kind not in ("story_mention", "story_reply")
        and not msg.postback_payload
        and not msg.quick_reply_payload
    )


def dm_triggers(msg: Message) -> tuple[str, ...]:
    """The triggers a customer DM can start, by what the message is. The welcome and default
    reply are listed for ordinary DMs; ``_match_dm`` keeps them only when they apply."""
    if ice_breakers.is_tap(msg.postback_payload):  # GR-11: a tapped conversation starter
        return ICE_BREAKER_TRIGGERS
    if msg.kind == "story_mention":
        return STORY_MENTION_TRIGGERS
    if msg.kind == "story_reply":
        return DM_TRIGGERS if is_story_like(msg) else STORY_REPLY_TRIGGERS
    return (*DM_TRIGGERS, *FALLBACK_TRIGGERS) if is_ordinary_dm(msg) else DM_TRIGGERS


def in_story_scope(automation: Automation, msg: Message) -> bool:
    """A story reply automation answers any story, or only its chosen ones (GR-06). A reply whose
    story we could not read matches only the any-story ones."""
    if automation.trigger != "story_reply" or automation.post_scope != PostScope.SELECTED:
        return True
    story_id = story_id_of(msg)
    return story_id is not None and story_id in (automation.story_ids or [])


def on_surface(automation: Automation, comment: Comment) -> bool:
    """A comment automation listens on posts, on Lives, or on both (GR-10)."""
    if comment.is_live:
        return automation.comment_surface in (CommentSurface.LIVE, CommentSurface.BOTH)
    return automation.comment_surface in (CommentSurface.POSTS, CommentSurface.BOTH)


async def enqueue_for_message(
    session: AsyncSession, message: Message, *, contact_id: uuid.UUID | None = None
) -> bool:
    """A new inbound customer DM (not an echo, not backfill) from ``contact_id``."""
    from socialhood.services.automations.answers import ANSWER_WINDOW

    since = datetime.now(UTC) - ANSWER_WINDOW
    answers_opening = contact_id is not None and (
        await runs.has_awaiting(session, contact_id, since=since)
        or await runs.has_flow_waiting(session, contact_id, since=since)  # GR-03
    )
    triggers = dm_triggers(message)
    if message.kind != "story_mention":
        # Whether the message is an entry is checked in the run.
        triggers = (*triggers, *matching.ENTRY_TRIGGERS)
    if (
        not answers_opening
        and not await runs.has_active(session, message.social_account_id, triggers)
        and not await business_hours.away_possible(session, message.social_account_id)  # GR-22
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
    handlers = {"dm": _run_dm, "comment": _run_comment, "nudge": _run_nudge, "flow": _run_flow}
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


async def _read_only_reason(session: AsyncSession, acct: SocialAccount | None) -> str | None:
    """FR-BIL-07: why the account can't send on this plan (the 402's detail), or None."""
    if acct is None:
        return None
    error = await read_only_error(session, acct)
    return None if error is None else actions.api_error_reason(error)


def _skipped_read_only(
    automation: Automation, keyword: str, reason: str, **common: Any
) -> dict[str, Any]:
    return _run_row(
        automation,
        keyword,
        result=RunResult.SKIPPED_READ_ONLY,
        error_code=READ_ONLY,
        error_message=reason,
        **common,
    )


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
        earlier = await runs.event_runs(session, message_id=msg.id)
        drafting = ai_reply.drafting_run(earlier)
        answer = None
        flow_answer = None
        if drafting is None:
            if msg.automation_handled or earlier:
                return Outcome.ALREADY_RAN
            # An answer to a waiting flow step (GR-03) or tap-first opening (FR-AUT-21) comes
            # before any keyword.
            # A mention answers no question, and neither does a tapped conversation starter.
            if msg.kind != "story_mention" and not ice_breakers.is_tap(msg.postback_payload):
                flow_answer = await engine.find_answer(session, msg, contact.id, now=env.now)
                if flow_answer is None:
                    answer = await answers.find(session, msg, contact.id, now=env.now)
            if flow_answer is None and answer is None:
                outcome = await _match_dm(session, env, msg, conv, contact)
                if outcome in (Outcome.NO_MATCH, Outcome.SKIPPED):
                    return await _away(session, env, msg, conv, contact, outcome)
                return outcome
    if flow_answer is not None:
        await engine.answer(
            env.sessionmaker,
            env.redis,
            env.deps,
            message_id=message_id,
            conversation_id=conv.id,
            found=flow_answer,
            now=env.now,
        )
        return Outcome.ANSWERED
    if drafting is not None:
        # A retry of a run whose AI reply was being drafted (T5.8): finish it.
        await ai_reply.answer_dm(
            env.sessionmaker, env.redis, env.deps, run_id=drafting.id, now=env.now
        )
        return Outcome.FIRED
    assert answer is not None
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
    triggers = dm_triggers(msg)
    came_from = None
    if msg.kind != "story_mention":
        came_from = await entry.of_message(session, msg, conv)
        if came_from is not None:
            triggers = (*triggers, came_from.trigger)
    loaded = await runs.candidates(session, msg.social_account_id, triggers, now=env.now)
    if ice_breakers.is_tap(msg.postback_payload):
        # GR-11: only the automation the tapped starter maps to. A starter that answers with AI,
        # or whose automation is gone, leaves the message to the inbox AI.
        starter = await ice_breakers.tapped(session, msg.social_account_id, msg.postback_payload)
        loaded = [
            item for item in loaded if starter and item.automation.id == starter.automation_id
        ]
    loaded = await _applicable(session, loaded, msg, conv, contact, env.now)
    found = matching.matches(msg.text or "", [item.candidate for item in loaded])
    if not found:
        return Outcome.NO_MATCH
    read_only = await _read_only_reason(session, await accounts.get(session, msg.social_account_id))
    by_id = {item.automation.id: item.automation for item in loaded}
    others_matched = False  # a keyword or any-reply automation matched, whatever came of it
    for match in found:
        automation = by_id[match.automation_id]
        if automation.trigger in FALLBACK_TRIGGERS:
            if others_matched:
                break  # a fallback answers only a DM nothing else matched
        else:
            others_matched = True
        if not in_story_scope(automation, msg):
            continue
        if came_from is not None and not entry.in_scope(automation, came_from):
            continue
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
        if read_only is not None:
            await runs.insert_run(
                session, _skipped_read_only(automation, match.keyword, read_only, **common)
            )
            break
        ai = automation.action == AutomationAction.AI_REPLY
        flow = await _flow_values(session, automation, comment=False)
        if flow is None:
            continue  # its saved flow is gone (never: the row is kept while it points at it)
        run = await runs.insert_run(
            session,
            _run_row(
                automation,
                match.keyword,
                # An AI reply's run waits while the reply is drafted (T5.8).
                result=RunResult.QUEUED if ai else RunResult.SENT,
                conversation_id=conv.id,
                **common,
                **flow,
            ),
        )
        if run is None:  # another worker ran this event first
            await session.rollback()
            return Outcome.ALREADY_RAN
        automation.last_run_at = env.now
        await _send_heart(session, env, automation, run, conv)
        if ai:
            return await _answer_with_ai(session, env, automation, run, msg)
        if engine.is_flow_run(run):
            await engine.start_dm(session, env.deps, automation, run, msg, now=env.now)
        else:
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


async def _away(
    session: AsyncSession,
    env: _Env,
    msg: Message,
    conv: Conversation,
    contact: Contact,
    outcome: Outcome,
) -> Outcome:
    """GR-22: nothing answered this DM, so the away message goes if the account is closed and it
    hasn't been sent in this closed window. The conversation is locked while it is checked and
    marked, so two messages in a row send it once."""
    if not business_hours.away_applies(msg) or not await business_hours.away_possible(
        session, msg.social_account_id
    ):
        return outcome
    locked = await ingest_rows.lock_conversation(session, conv.id)
    if locked is None:
        return outcome
    sent = await business_hours.send_away(
        session,
        env.deps,
        locked,
        contact,
        msg,
        ai_mode=await _ai_mode(session, locked),
        now=env.now,
    )
    if not sent:
        await session.rollback()
        return outcome
    await session.flush()
    await events.commit_and_publish(session, env.redis)
    log.info("away_message_sent", conversation_id=str(conv.id), message_id=str(msg.id))
    return Outcome.FIRED


async def _applicable(
    session: AsyncSession,
    loaded: list[runs.Loaded],
    msg: Message,
    conv: Conversation,
    contact: Contact,
    now: datetime,
) -> list[runs.Loaded]:
    """GR-12: drop the welcome unless this is the contact's first DM to the account, and the
    default reply unless AI is off for the conversation. Looked up only when one is loaded.
    GR-22: drop an automation whose hours condition doesn't hold."""
    loaded = await _in_hours(session, loaded, msg.social_account_id, now)
    welcome = any(item.automation.trigger == "first_message" for item in loaded)
    default = any(item.automation.trigger == "default_reply" for item in loaded)
    drop: set[str] = set()
    if welcome and await inbox.has_earlier_inbound_dm(session, msg, contact.id):
        drop.add("first_message")
    if default and await _ai_mode(session, conv) != "off":
        drop.add("default_reply")
    return [item for item in loaded if item.automation.trigger not in drop]


async def _in_hours(
    session: AsyncSession, loaded: list[runs.Loaded], account_id: uuid.UUID, now: datetime
) -> list[runs.Loaded]:
    """GR-22: the automations whose hours condition holds right now (read only when one has a
    condition)."""
    if not any(item.automation.hours_condition for item in loaded):
        return loaded
    inside = await business_hours.is_open_now(session, account_id, now)
    return [item for item in loaded if hours_hold(item.automation, inside)]


def hours_hold(automation: Automation, inside: bool) -> bool:
    """Whether the automation's "inside hours" / "outside hours" condition holds."""
    condition = automation.hours_condition
    return condition is None or (condition == HoursCondition.INSIDE) == inside


async def _ai_mode(session: AsyncSession, conv: Conversation) -> str:
    """The conversation's effective AI mode: its override, else the account's. A pause
    (``ai_paused_until``) does not turn the AI off, so a paused conversation gets no default
    reply: a person is handling it."""
    if conv.ai_mode_override:
        return conv.ai_mode_override
    acct = await accounts.get(session, conv.social_account_id)
    return acct.ai_mode if acct is not None else "off"


async def _send_heart(
    session: AsyncSession,
    env: _Env,
    automation: Automation,
    run: AutomationRun,
    conv: Conversation,
) -> None:
    """GR-06: the heart sticker for a story reply, queued ahead of the run's message. It is not
    linked to the run, so its outcome never changes the run's result; a refusal (the account is
    blocked, the window closed) only goes to the log."""
    from socialhood.services import sending  # sending → … → ingest → this module

    if automation.trigger != "story_reply" or not automation.story_heart:
        return
    try:
        await sending.queue_outbound(
            session,
            conv,
            source="automation",
            client_id=actions.client_id_for(run.id, "heart"),
            sticker="like_heart",
            deps=env.deps,
            now=env.now,
        )
    except ApiError as error:
        log.info("automation_heart_skipped", run_id=str(run.id), reason=error.code)


async def _answer_with_ai(
    session: AsyncSession, env: _Env, automation: Automation, run: AutomationRun, msg: Message
) -> Outcome:
    """T5.8: the run (queued) and automation_handled are committed first, so no lock is held
    while the reply is drafted; then services/automations/ai_reply sends or escalates."""
    msg.automation_handled = True  # FR-AUT-07: the inbox AI leaves it alone
    await session.flush()
    await events.commit_and_publish(session, env.redis)
    result = await ai_reply.answer_dm(
        env.sessionmaker, env.redis, env.deps, run_id=run.id, now=env.now
    )
    log.info(
        "automation_fired",
        automation_id=str(automation.id),
        run_id=str(run.id),
        result=str(result),
    )
    return Outcome.FIRED


async def _flow_values(
    session: AsyncSession, automation: Automation, *, comment: bool
) -> dict[str, Any] | None:
    """A flow run's columns (GR-03; none for an automation on its message settings); None when
    its saved flow can't be loaded."""
    if automation.flow_version is None:
        return {}
    try:
        g = await engine.graph_for(session, automation.id, automation.flow_version)
    except (KeyError, flows.FlowError):
        log.warning("automation_flow_missing", automation_id=str(automation.id))
        return None
    return engine.start_values(automation, g, comment=comment)


# ---- flows (GR-03)


async def _run_flow(env: _Env, run_id: uuid.UUID) -> Outcome:
    outcome = await engine.resume(env.sessionmaker, env.redis, env.deps, run_id=run_id, now=env.now)
    return {
        "missing": Outcome.MISSING,
        "ignored": Outcome.ALREADY_RAN,
        "advanced": Outcome.FIRED,
        "done": Outcome.FIRED,
    }[outcome]


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
    if automation.action == AutomationAction.AI_REPLY:  # the queue drafts the DM (T5.8)
        return _Plan(
            dm=automation.surge_order != SurgeOrder.PUBLIC_ONLY,
            public=bool(automation.public_reply_texts),
        )
    if automation.action != AutomationAction.SEND_MESSAGE:
        return _Plan(dm=False, public=False)
    # A flow (GR-03) always starts a comment's with its message (flows.activation_errors).
    has_dm = automation.flow_version is not None or bool(
        automation.message_text and automation.message_text.strip()
    )
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
        loaded = await _in_hours(session, loaded, acct.id, env.now)  # GR-22
        found = matching.matches(comment.text, [item.candidate for item in loaded])
        if not found:
            return Outcome.NO_MATCH
        contact = (
            await inbox.get_contact(session, comment.contact_id) if comment.contact_id else None
        )
        read_only = await _read_only_reason(session, acct)
        fired = await _first_passing(session, env, comment, contact, loaded, found, read_only)
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
    read_only: str | None,
) -> _Fired | Outcome | None:
    by_id = {item.automation.id: item.automation for item in loaded}
    expired = env.now - comment.commented_at >= PRIVATE_REPLY_LIMIT
    live_late = comment.is_live and env.now - comment.commented_at > LIVE_REPLY_WINDOW
    for match in found:
        automation = by_id[match.automation_id]
        if not on_surface(automation, comment):
            continue
        if not comment.is_live and not await runs.in_scope(
            session, automation, comment.media_item_id
        ):
            continue  # a Live has no post scope
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
        if expired or live_late:
            code, reason = LIVE_ENDED if live_late else EXPIRED
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
        if read_only is not None:
            await runs.insert_run(
                session, _skipped_read_only(automation, match.keyword, read_only, **common)
            )
            return None
        flow = await _flow_values(session, automation, comment=True)
        if flow is None:
            continue
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
            **(flow if plan.dm else {}),
        )
        if not plan.dm and not plan.public:
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
