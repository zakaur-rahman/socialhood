"""The account's private-reply queue (T4.6; FR-AUT-10, TR-JOB-07).

A comment automation's match records its run as ``queued`` and enqueues
``drain_private_replies(account_id)`` (key and lock ``prq:{account_id}``, so one drain runs per
account at a time). Each drain:

1. marks queued runs whose comment is past Instagram's 7-day limit ``skipped_expired`` with the
   reason "Instagram's 7-day limit passed", so none is attempted after 7 days;
2. settles the queued runs of automations now set to public reply only, which never DM;
3. sends queued private replies while the account's IG_PRIVATE_REPLY bucket gives tokens
   (platforms/buckets: never more than 750 in any hour), taking the account's automations in turn
   and each automation's runs in its order (oldest or newest first), a batch at a time;
4. says when to drain again while sendable runs remain: when the bucket has a batch of tokens,
   or at once after a full pass; the job re-defers itself for then.

AI replies (T5.8): an AI automation's runs are taken one at a time: a token, then the reply is
drafted outside any transaction (services/automations/ai_reply), then the run is claimed and sent
like the others. A draft that cannot answer escalates and settles the run instead; at most 10
drafts per pass.

A paused automation holds its runs (they still expire); one whose run window ended keeps sending
what matched inside it. A reconnect-needed account holds the whole queue. Each private reply is
stored as an outbound message (source ``automation``) in the commenter's conversation, created if
needed, inserted as ``sending`` and committed before the call (so a run is never sent twice, and
an early echo finds the message, C-011), and linked from the run and
``comments.private_reply_message_id``. A temporary platform error puts the run back in the queue;
any other failure settles it (services/automations/results).

DMs and other sends use their own buckets and jobs, and other accounts their own queues, so a
surge on one account delays nothing else.

Tap first (T4.8, FR-AUT-21): an automation set to confirm first sends its opening as the private
reply, with one quick reply whose payload names the run (``shr:{run_id}``); once sent, the run
waits for the commenter's answer (``awaiting_reply``, services/automations/answers). Meta
documents private replies with text only, so an opening Instagram refuses (a validation refusal)
is sent again at once as text, whose default copy asks them to reply instead; the stored message
then shows no quick reply.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.models.automations import (
    Automation,
    AutomationAction,
    AutomationRun,
    AutomationStatus,
    Comment,
    RunResult,
    SurgeOrder,
)
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import (
    Contact,
    Conversation,
    Direction,
    Message,
    MessageKind,
    MessageSource,
    MessageStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import OutboundMessage, PlatformAdapter, SendResult
from socialhood.platforms.buckets import (
    PRIVATE_REPLY_BURST,
    SPECS,
    Bucket,
    TokenBuckets,
)
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.platforms.registry import adapter_for
from socialhood.realtime import events
from socialhood.repositories import automation_runs as runs
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import ingest as rows
from socialhood.repositories import messages as messages_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations import actions, results, stats
from socialhood.services.inbox_views import conversation_touch

log = get_logger(__name__)

PRIVATE_REPLY_LIMIT = timedelta(days=7)
EXPIRED = ("expired", "Instagram's 7-day limit passed")
NO_CONTACT = ("nothing_to_send", "The commenter is unknown, so no DM could be sent.")
MAX_SENDS = 50  # private replies per drain run
MAX_AI_DRAFTS = 10  # AI replies drafted per drain run (each is a model call, T5.8)
BATCH = PRIVATE_REPLY_BURST  # claimed and settled together, one transaction each
HOLD_RETRY_S = 600.0  # a held queue (paused automation, account to reconnect) looks again
RETRY_AFTER_S = 60.0  # after a temporary platform error or a Valkey outage
RATE_PER_S = SPECS[Bucket.IG_PRIVATE_REPLY].per_second
BATCH_MARGIN_S = 0.01  # so the batch's last token has surely refilled


@dataclass(frozen=True)
class DrainResult:
    sent: int = 0
    failed: int = 0
    expired: int = 0
    settled: int = 0  # public-reply-only runs settled without a DM
    escalated: int = 0  # AI replies not sent: escalated, or the draft failed (T5.8)
    remaining: int = 0  # queued runs the queue will still send
    next_in_s: float | None = None  # when to drain again; None: nothing left to do


# ---------------------------------------------------------------- the ETA (FR-AUT-10)


async def account_queue(
    session: AsyncSession, social_account_id: uuid.UUID, *, now: datetime | None = None
) -> tuple[int, int | None]:
    """(waiting, eta_minutes) for the account: private replies the queue will send, and how
    long that takes at the bucket's rate (about 750 an hour). ETA is None when none wait."""
    waiting = await runs.waiting(session, social_account_id, now=now or datetime.now(UTC))
    if not waiting:
        return 0, None
    return waiting, stats.eta_minutes(waiting)


async def automation_waiting(session: AsyncSession, automation_id: uuid.UUID) -> int:
    """QueueInfo.waiting for one automation: its private replies still queued."""
    return await runs.queued_for(session, automation_id)


# ---------------------------------------------------------------- the job


async def enqueue_drain(
    account_id: uuid.UUID, workspace_id: uuid.UUID, *, delay_s: float = 0.0
) -> bool:
    """Queue a drain for the account (at most one waiting and one running). Also for the API:
    call it when a paused automation with queued runs is resumed."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.automations import drain_private_replies

    key = f"prq:{account_id}"
    return await enqueue(
        drain_private_replies,
        key=key,
        lock=key,
        delay_s=delay_s,
        workspace_id=str(workspace_id),
        account_id=str(account_id),
    )


async def run_drain(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
) -> DrainResult:
    """The drain_private_replies job: drain, then re-defer while runs remain."""
    result = await drain(sessionmaker, redis, deps, account_id=account_id)
    if result.next_in_s is not None:
        await enqueue_drain(account_id, workspace_id, delay_s=result.next_in_s)
    if result.sent or result.failed or result.expired or result.settled:
        log.info(
            "private_replies_drained",
            account_id=str(account_id),
            sent=result.sent,
            failed=result.failed,
            expired=result.expired,
            settled=result.settled,
            remaining=result.remaining,
        )
    return result


# ---------------------------------------------------------------- one pass


def _sends(automation: Automation, now: datetime) -> bool:
    """Mirrors ``runs.sendable``: active, or its run window ended; never public reply only."""
    if automation.surge_order == SurgeOrder.PUBLIC_ONLY:
        return False
    ended = automation.ends_at is not None and automation.ends_at <= now
    return automation.status == AutomationStatus.ACTIVE or ended


@dataclass(frozen=True)
class _Pass:
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    buckets: TokenBuckets
    adapter: PlatformAdapter
    acct: SocialAccount
    now: datetime
    disclosure: str | None
    drafts: dict[uuid.UUID, str] = field(default_factory=dict)  # AI replies to send (T5.8)


@dataclass
class _Tally:
    sent: int = 0
    failed: int = 0
    escalated: int = 0  # AI replies settled without a DM
    drafted: int = 0  # AI drafts made in this pass
    wait: float | None = None  # the bucket is empty for this long
    retry_in: float | None = None  # a temporary platform error
    blocked: bool = False  # the account needs reconnecting


async def drain(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    account_id: uuid.UUID,
    now: datetime | None = None,
    max_sends: int = MAX_SENDS,
) -> DrainResult:
    """One pass over the account's queue (see the module docstring). ``now`` also drives the
    bucket, so tests can simulate hours."""
    from socialhood.services.sending import BLOCKED_STATUSES

    now = now or datetime.now(UTC)
    cutoff = now - PRIVATE_REPLY_LIMIT
    async with sessionmaker() as session:
        acct = await accounts.get(session, account_id)
        if acct is None:
            return DrainResult()
        queued = await runs.queued_automations(session, acct.id)
        code, reason = EXPIRED
        expired = await runs.expire_queued(
            session,
            acct.id,
            [a.id for a in queued],
            commented_before=cutoff,
            code=code,
            message=reason,
        )
        settled = 0
        for automation in queued:
            if automation.surge_order == SurgeOrder.PUBLIC_ONLY:
                settled += await _settle_public_only(session, automation, acct.id, cutoff)
        disclosure = await actions.disclosure(session)
        await session.commit()
    ai = [a for a in queued if _sends(a, now) and a.action == AutomationAction.AI_REPLY]
    sendable = [a for a in queued if _sends(a, now) and a.action != AutomationAction.AI_REPLY]
    held = any(not _sends(a, now) and a.surge_order != SurgeOrder.PUBLIC_ONLY for a in queued)

    adapter: PlatformAdapter | None = None
    if acct.status not in BLOCKED_STATUSES:
        try:
            adapter = adapter_for(acct, deps)
        except PlatformError as error:
            log.warning("private_replies_held", account_id=str(acct.id), error_code=error.code)

    tally = _Tally()
    if adapter is not None:
        run = _Pass(sessionmaker, redis, TokenBuckets(redis), adapter, acct, now, disclosure)
        while (sendable or ai) and _done(tally) < max_sends:
            limit = min(BATCH, max_sends - _done(tally))
            if sendable:
                claimed = await _claim(run, sendable, limit, tally)
                if claimed:
                    await _send_batch(run, claimed, tally)
            for automation in list(ai):
                if _stopped(tally) or tally.drafted >= MAX_AI_DRAFTS:
                    break
                if not await _drain_ai(run, automation, limit, tally):
                    ai.remove(automation)
            if _stopped(tally) or tally.drafted >= MAX_AI_DRAFTS:
                break

    async with sessionmaker() as session:
        remaining = await runs.waiting(session, acct.id, now=now, unclaimed=True)
    return DrainResult(
        sent=tally.sent,
        failed=tally.failed,
        expired=expired,
        settled=settled,
        escalated=tally.escalated,
        remaining=remaining,
        next_in_s=_next_in(
            remaining=remaining,
            held=held,
            blocked=adapter is None,
            wait=tally.wait,
            retry_in=tally.retry_in,
            progressed=_done(tally) > 0,
        ),
    )


def _done(tally: _Tally) -> int:
    return tally.sent + tally.failed + tally.escalated


def _stopped(tally: _Tally) -> bool:
    return tally.wait is not None or tally.retry_in is not None or tally.blocked


def _next_in(
    *,
    remaining: int,
    held: bool,
    blocked: bool,
    wait: float | None,
    retry_in: float | None,
    progressed: bool,
) -> float | None:
    """When to drain again: None once nothing is queued; slowly while runs are held."""
    if not remaining or blocked:
        return HOLD_RETRY_S if held or remaining else None
    if retry_in is not None:
        return retry_in
    if wait is not None:
        # Come back when a batch of tokens is there rather than for each one.
        batch = min(remaining, PRIVATE_REPLY_BURST)
        return wait + (batch - 1) / RATE_PER_S + BATCH_MARGIN_S
    return 0.0 if progressed else RETRY_AFTER_S


async def _settle_public_only(
    session: AsyncSession, automation: Automation, account_id: uuid.UUID, cutoff: datetime
) -> int:
    count = 0
    while batch := await runs.claim(
        session, automation, account_id, commented_after=cutoff, limit=500
    ):
        for queued in batch:
            results.finish_comment_run(queued, "skipped")
        await session.flush()
        count += len(batch)
    return count


# ---------------------------------------------------------------- a batch of private replies


@dataclass
class _Claimed:
    run_id: uuid.UUID
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    comment_id: uuid.UUID
    comment_ref: str
    contact: Contact
    message: OutboundMessage
    outcome: SendResult | PlatformError | None = field(default=None)  # None: not attempted
    opening: bool = False  # tap first: the opening, with its quick reply (FR-AUT-21)
    text_only: bool = False  # Instagram refused the quick reply; the opening went as text


def _in_turn(lists: Sequence[tuple[Automation, list[AutomationRun]]]) -> list[AutomationRun]:
    """The automations' runs taken one from each in turn (FR-AUT-10: they share the queue)."""
    order: list[AutomationRun] = []
    depth = max((len(items) for _, items in lists), default=0)
    for i in range(depth):
        order.extend(items[i] for _, items in lists if i < len(items))
    return order


async def _claim(
    run: _Pass, sendable: list[Automation], limit: int, tally: _Tally
) -> list[_Claimed]:
    """Lock up to ``limit`` runs (in turn across automations), take as many tokens, and store
    each one's message as ``sending``. Automations with nothing left leave ``sendable``."""
    acct, now = run.acct, run.now
    async with run.sessionmaker() as session:
        lists: list[tuple[Automation, list[AutomationRun]]] = []
        for automation in list(sendable):
            batch = await runs.claim(
                session,
                automation,
                acct.id,
                commented_after=now - PRIVATE_REPLY_LIMIT,
                limit=limit,
            )
            if batch:
                lists.append((automation, batch))
            else:
                sendable.remove(automation)
        order = _in_turn(lists)[:limit]
        if not order:
            return []
        taken, wait = await _take(run, len(order))
        if wait > 0:  # the bucket is empty now: this is the pass's last batch
            tally.wait = wait
        chosen = order[:taken]
        if not chosen:
            await session.rollback()
            return []
        by_automation = {a.id: a for a, _ in lists}
        claimed = await _prepare(session, run, chosen, by_automation, tally)
        await session.commit()
        return claimed


async def _take(run: _Pass, count: int) -> tuple[int, float]:
    try:
        return await run.buckets.take_many(
            Bucket.IG_PRIVATE_REPLY, str(run.acct.id), count, now=run.now.timestamp()
        )
    except Exception:
        log.warning("token_bucket_unavailable", bucket=str(Bucket.IG_PRIVATE_REPLY))
        return 0, RETRY_AFTER_S  # never send past the hourly limit blind


async def _prepare(
    session: AsyncSession,
    run: _Pass,
    chosen: list[AutomationRun],
    by_automation: dict[uuid.UUID, Automation],
    tally: _Tally,
) -> list[_Claimed]:
    acct = run.acct
    comments = {
        c.id: c
        for c in await comments_repo.get_many(
            session, [q.trigger_comment_id for q in chosen if q.trigger_comment_id]
        )
    }
    contacts = {
        c.id: c
        for c in await runs.contacts_by_id(
            session, [c.contact_id for c in comments.values() if c.contact_id]
        )
    }
    ready: list[tuple[AutomationRun, Comment, Contact, OutboundMessage]] = []
    for queued in chosen:
        automation = by_automation[queued.automation_id]
        comment = comments.get(queued.trigger_comment_id) if queued.trigger_comment_id else None
        contact = await _commenter(session, acct, comment, contacts)
        if comment is None or contact is None:
            tally.failed += _give_up(queued, NO_CONTACT)
            continue
        outbound: OutboundMessage | None
        if automation.action == AutomationAction.AI_REPLY:
            text = run.drafts.pop(queued.id, None)
            if text is None:
                continue  # not drafted yet: it stays queued for _drain_ai (T5.8)
            outbound = OutboundMessage(text=text)
        else:
            outbound = _private_reply(automation, queued, comment, contact, run.disclosure)
        if outbound is None:
            tally.failed += _give_up(queued, actions.NO_MESSAGE)
            continue
        ready.append((queued, comment, contact, outbound))

    conversations = {
        c.contact_id: c
        for c in await runs.lock_conversations_of(
            session, acct.id, list({contact.id for _, _, contact, _ in ready})
        )
    }
    staged: list[tuple[AutomationRun, Comment, Contact, Message, OutboundMessage]] = []
    for queued, comment, contact, outbound in ready:
        conv = conversations.get(contact.id)
        if conv is None:
            conv, _ = await rows.get_or_create_conversation(
                session, social_account_id=acct.id, contact_id=contact.id, platform=acct.platform
            )
            conversations[contact.id] = conv
        msg = Message(
            conversation_id=conv.id,
            social_account_id=acct.id,
            direction=Direction.OUTBOUND,
            source=MessageSource.AUTOMATION,
            kind=MessageKind.TEXT,
            text=outbound.text,
            attachments=[],
            buttons=[{"title": b.title, "url": b.url} for b in outbound.buttons],
            quick_replies=[
                {"title": q.title, "payload": q.payload} for q in outbound.quick_replies
            ],
            occurred_at=run.now,
            client_id=actions.client_id_for(queued.id),
            status=MessageStatus.SENDING,
            attempts=1,
            automation_run_id=queued.id,
            reactions=[],
        )
        session.add(msg)
        staged.append((queued, comment, contact, msg, outbound))
    await session.flush()
    claimed: list[_Claimed] = []
    for queued, comment, contact, msg, outbound in staged:
        queued.private_reply_message_id = msg.id
        queued.conversation_id = msg.conversation_id
        queued.contact_id = queued.contact_id or contact.id
        claimed.append(
            _Claimed(
                run_id=queued.id,
                message_id=msg.id,
                conversation_id=msg.conversation_id,
                comment_id=comment.id,
                comment_ref=comment.platform_comment_id,
                contact=contact,
                message=outbound,
                opening=bool(outbound.quick_replies),
            )
        )
    await session.flush()
    return claimed


def _private_reply(
    automation: Automation,
    queued: AutomationRun,
    comment: Comment,
    contact: Contact,
    disclosure: str | None,
) -> OutboundMessage | None:
    """The private reply: the tap-first opening with its quick reply (FR-AUT-21), or the
    message with its link buttons. None when there is nothing to send."""
    if actions.opens_first(automation):
        opening = actions.render_opening(
            automation, contact, username=comment.author_username, disclosure_line=disclosure
        )
        if opening is not None:
            return OutboundMessage(
                text=opening, quick_replies=(actions.opening_quick_reply(automation, queued.id),)
            )
    text = actions.render_message(
        automation, contact, username=comment.author_username, disclosure_line=disclosure
    )
    if text is None:
        return None
    return OutboundMessage(text=text, buttons=actions.buttons(automation))


async def _commenter(
    session: AsyncSession,
    acct: SocialAccount,
    comment: Comment | None,
    contacts: dict[uuid.UUID, Contact],
) -> Contact | None:
    if comment is None:
        return None
    if comment.contact_id in contacts:
        return contacts[comment.contact_id]
    if not comment.author_platform_user_id:
        return None
    contact, _ = await rows.get_or_create_contact(
        session,
        social_account_id=acct.id,
        platform_user_id=comment.author_platform_user_id,
        first_seen_at=comment.commented_at,
    )
    contacts[contact.id] = contact
    return contact


# ---------------------------------------------------------------- AI replies (T5.8)


async def _drain_ai(run: _Pass, automation: Automation, limit: int, tally: _Tally) -> bool:
    """An AI automation's queued private replies, one at a time: take a token, draft the reply
    outside any transaction (services/automations/ai_reply; an escalation or a failed draft
    settles the run there), then claim the run and send it like any private reply. False when
    the automation has none left."""
    from socialhood.services.automations import ai_reply

    async with run.sessionmaker() as session:
        peeked = await runs.claim(
            session,
            automation,
            run.acct.id,
            commented_after=run.now - PRIVATE_REPLY_LIMIT,
            limit=max(1, min(limit, MAX_AI_DRAFTS - tally.drafted)),
        )
        ids = [q.id for q in peeked]
        await session.rollback()
    if not ids:
        return False
    for run_id in ids:
        taken, wait = await _take(run, 1)
        if not taken:
            tally.wait = wait
            return True
        if wait > 0:
            tally.wait = wait  # the bucket's last token: this is the pass's last send
        tally.drafted += 1
        drafted = await ai_reply.draft_for_comment(
            run.sessionmaker, run.redis, run_id=run_id, disclosure=run.disclosure, now=run.now
        )
        if drafted.settled:
            tally.escalated += 1
        elif drafted.text is not None:
            run.drafts[run_id] = drafted.text
            claimed = await _claim_drafted(run, automation, run_id, tally)
            if claimed:
                await _send_batch(run, claimed, tally)
        if _stopped(tally) or tally.drafted >= MAX_AI_DRAFTS:
            return True
    return True


async def _claim_drafted(
    run: _Pass, automation: Automation, run_id: uuid.UUID, tally: _Tally
) -> list[_Claimed]:
    """Claim one drafted run (still queued and unclaimed) and store its reply as sending."""
    async with run.sessionmaker() as session:
        queued = await runs.lock(session, run_id)
        if (
            queued is None
            or queued.result != RunResult.QUEUED
            or queued.private_reply_message_id is not None
        ):
            run.drafts.pop(run_id, None)
            await session.rollback()
            return []
        claimed = await _prepare(session, run, [queued], {automation.id: automation}, tally)
        await session.commit()
        return claimed


def _give_up(queued: AutomationRun, reason: tuple[str, str]) -> int:
    results.finish_comment_run(queued, "failed", error_code=reason[0], error_message=reason[1])
    return 1


async def _send_batch(run: _Pass, claimed: list[_Claimed], tally: _Tally) -> None:
    """Send each claimed private reply, then settle them all in one transaction. A temporary
    error stops the batch; it and the replies not tried yet go back in the queue."""
    for item in claimed:
        item.outcome = await _private_reply_call(run, item, item.message)
        if isinstance(item.outcome, PlatformError) and _refused_quick_reply(item, item.outcome):
            # Meta documents private replies with text only: an opening refused for its quick
            # reply goes again as text, which asks them to reply instead (FR-AUT-21).
            log.info(
                "private_reply_quick_reply_refused",
                run_id=str(item.run_id),
                platform_code=item.outcome.platform_code,
            )
            item.text_only = True
            item.outcome = await _private_reply_call(
                run, item, replace(item.message, quick_replies=())
            )
        if isinstance(item.outcome, PlatformError) and (
            item.outcome.retryable or item.outcome.code == "account_needs_reconnect"
        ):
            break
    await _settle(run, claimed, tally)


async def _private_reply_call(
    run: _Pass, item: _Claimed, message: OutboundMessage
) -> SendResult | PlatformError:
    try:
        return await run.adapter.private_reply(run.acct, item.comment_ref, message)
    except PlatformError as error:
        return error
    except Exception:
        # Something unexpected after the call started: Instagram may have sent it.
        log.exception("private_reply_unexpected_error", run_id=str(item.run_id))
        return PlatformError(
            DELIVERY_UNKNOWN, retryable=False, message="The platform did not confirm the send"
        )


QUICK_REPLY_REFUSALS = frozenset({"platform_rejected"})


def _refused_quick_reply(item: _Claimed, error: PlatformError) -> bool:
    """Instagram refused a message that carried quick replies (a validation refusal, not a
    temporary error or an unknown outcome), and it has not been retried as text yet."""
    return (
        not error.retryable
        and error.code in QUICK_REPLY_REFUSALS
        and bool(item.message.quick_replies)
        and not item.text_only
    )


async def _settle(run: _Pass, claimed: list[_Claimed], tally: _Tally) -> None:
    from socialhood.services.connections import mark_needs_reconnect
    from socialhood.services.sending import BLOCKED_STATUSES

    acct, now = run.acct, run.now
    back = [
        c
        for c in claimed
        if c.outcome is None or (isinstance(c.outcome, PlatformError) and c.outcome.retryable)
    ]
    back_ids = {c.run_id for c in back}
    done = [c for c in claimed if c.run_id not in back_ids]
    sent = [c for c in done if isinstance(c.outcome, SendResult)]
    async with run.sessionmaker() as session:
        # Conversations first, in the order ingest locks them (an echo of one of these replies
        # takes its conversation, then the message, then the run).
        conversations = {
            c.id: c
            for c in await runs.lock_conversations(session, list({c.conversation_id for c in done}))
        }
        # Never reached Instagram: back in the queue (deleting the message clears the claim).
        await runs.release_claims(session, [c.message_id for c in back])
        await _mark_sent(session, sent, now)
        for item in done:
            if isinstance(item.outcome, PlatformError):
                await messages_repo.mark_failed(
                    session,
                    item.message_id,
                    code=item.outcome.code,
                    message=actions.platform_error_reason(item.outcome, acct),
                    only_from=(MessageStatus.SENDING,),
                )
        linked = {c.comment_id: c.message_id for c in sent}
        for comment in await comments_repo.lock_many(session, list(linked)):
            comment.private_reply_message_id = linked[comment.id]
        messages = {
            m.id: m for m in await runs.messages_by_id(session, [c.message_id for c in done])
        }
        for item in done:
            text_only = messages.get(item.message_id) if item.text_only else None
            if text_only is not None:
                text_only.quick_replies = []  # what went out: the opening as text
        by_run = {c.run_id: c for c in done}
        for settled in await runs.lock_many(session, [c.run_id for c in done]):
            reply_id = settled.private_reply_message_id
            msg = messages.get(reply_id) if reply_id else None
            if msg is not None:
                results.apply_message(settled, msg, opening=by_run[settled.id].opening)
        for item in done:
            msg, conv = messages.get(item.message_id), conversations.get(item.conversation_id)
            if msg is None or conv is None:
                continue
            _touch(conv, msg, now)
            events.queue_message(session, msg, created=True)
        await session.flush()
        contacts = {c.conversation_id: c.contact for c in done}
        for conv in conversations.values():
            await events.queue_conversation(session, conv, now=now, contact=contacts.get(conv.id))
        if any(
            isinstance(c.outcome, PlatformError) and c.outcome.code == "account_needs_reconnect"
            for c in done
        ):
            tally.blocked = True
            fresh = await accounts.get(session, acct.id)
            if fresh is not None and fresh.status not in BLOCKED_STATUSES:
                await mark_needs_reconnect(
                    session, fresh, "Instagram stopped accepting this connection."
                )
        await events.commit_and_publish(session, run.redis)
    tally.sent += len(sent)
    tally.failed += len(done) - len(sent)
    retry = next((c.outcome for c in back if isinstance(c.outcome, PlatformError)), None)
    if retry is not None:
        tally.retry_in = retry.retry_after_s or RETRY_AFTER_S
        log.info("private_reply_retry", error_code=retry.code, requeued=len(back))
    for item in done:
        if isinstance(item.outcome, PlatformError):
            log.info(
                "private_reply_failed",
                run_id=str(item.run_id),
                error_code=item.outcome.code,
                platform_code=item.outcome.platform_code,
            )


def _touch(conv: Conversation, msg: Message, now: datetime) -> None:
    """The private reply joins the conversation's last-message fields (never moving back)."""
    if conv.last_message_at is None or msg.occurred_at >= conv.last_message_at:
        for key, value in conversation_touch(msg).items():
            setattr(conv, key, value)
        conv.awaiting_reply = False
    if conv.last_outbound_at is None or now > conv.last_outbound_at:
        conv.last_outbound_at = now


async def _mark_sent(session: AsyncSession, sent: list[_Claimed], now: datetime) -> None:
    """Record the platform ids. An echo stored first as its own row holds the id (C-011): that
    reply stays sent without it."""
    ids = [
        (item.message_id, item.outcome.platform_message_id)
        for item in sent
        if isinstance(item.outcome, SendResult)
    ]
    try:
        async with session.begin_nested():
            await runs.mark_replies_sent(session, ids, at=now)
    except IntegrityError:
        for item in sent:
            assert isinstance(item.outcome, SendResult)
            try:
                async with session.begin_nested():
                    await messages_repo.mark_sent(
                        session,
                        item.message_id,
                        platform_message_id=item.outcome.platform_message_id,
                        at=now,
                    )
            except IntegrityError:
                log.warning("private_reply_echo_stored_first", message_id=str(item.message_id))
                await messages_repo.mark_sent(
                    session, item.message_id, platform_message_id=None, at=now
                )
