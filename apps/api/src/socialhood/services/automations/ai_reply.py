"""AI replies in automations (T5.8; FR-AUT-01, FR-AUT-11, TR-AI-06, F-11 runtime).

An ``ai_reply`` automation answers the matched DM or comment with a reply drafted like an inbox
suggestion (services/suggestions/drafting): the suggest prompt with the business's instructions
in {automation_instructions} ("Instructions from the business for this reply: …"), 2 credits
(``automation_ai_reply``). The reply goes out like the message action, with the disclosure line
(the draft is trimmed to leave room for it): a DM through the send pipeline, or a comment's
private reply through the account's queue. It is sent without a person reading it, so it may
quote only knowledge and brand settings (the output filter).

When the draft cannot answer from knowledge, or the filter blocks it, the automation sends
nothing and escalates: the run is ``escalated`` (reason out_of_knowledge or output_blocked), the
conversation needs a human, the owners and admins are notified, and the question is recorded as
a knowledge gap. A failed call, used-up credits or a plan without AI replies fail the run with
the reason; nothing is sent. The plan is checked again when the automation runs.

DMs (``answer_dm``): the runtime records the run as ``queued`` and marks the trigger message
automation_handled (so the inbox AI leaves it alone, FR-AUT-07) and commits before the model is
called, so no row lock is held during the call; a retried job finds the queued run and resumes.
The draft is kept as a reply_suggestions row linked to the run (``sent``, or ``dismissed`` when
it was not sent; never ``pending``).

Comments (``draft_for_comment``): the private-reply queue drafts each queued run of an AI
automation just before claiming it, outside any transaction (services/automations/queue). A
comment has no conversation message to hang a suggestion row on, so none is stored; the usage
event records the call. Escalating a commenter without a conversation only notifies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai.metering import QuotaExceeded
from socialhood.ai.provider import AIError
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError
from socialhood.models.ai import ReplySuggestion, SuggestionStatus
from socialhood.models.automations import Automation, AutomationRun, Comment, RunResult
from socialhood.models.inbox import Conversation, Message
from socialhood.models.media import MediaItem
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime import events
from socialhood.repositories import automation_runs as runs
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import inbox, social_accounts
from socialhood.repositories import ingest as ingest_rows
from socialhood.services.automations import actions, render, results
from socialhood.services.notifications import notify_admins
from socialhood.services.suggestions import drafting, knowledge_port
from socialhood.services.suggestions.auto import REASON_COPY, escalate

log = get_logger(__name__)

FEATURE: Literal["automation_ai_reply"] = "automation_ai_reply"
CAPTION_CHARS = 300
NO_CREDITS = ("ai_credits_exhausted", "AI credits are used up, so this automation sent nothing.")
NOT_ON_PLAN = (
    "entitlement_required",
    "AI replies in automations are part of Pro, so this automation sent nothing.",
)


def _ai_failed(error: AIError) -> tuple[str, str]:
    return ("ai_error", f"The AI couldn't draft a reply ({error.code}), so nothing was sent.")


@dataclass(frozen=True)
class Drafted:
    """A drafted reply: ``text`` to send (with the disclosure line), or an ``escalation``
    reason, or an ``error`` (code, reason) when there is no draft."""

    text: str | None = None
    escalation: str | None = None
    error: tuple[str, str] | None = None
    draft: drafting.Draft | None = None

    @property
    def not_sent_reason(self) -> str:
        copy = REASON_COPY.get(self.escalation, REASON_COPY[None])
        missing = self.draft.missing_info if self.draft is not None else None
        return f"Not sent: {copy}" + (f" ({missing})." if missing else ".")


def drafting_run(earlier: list[AutomationRun]) -> AutomationRun | None:
    """A DM run whose AI reply is still being drafted (queued, nothing sent yet)."""
    return next(
        (
            r
            for r in earlier
            if r.result == RunResult.QUEUED
            and r.trigger_message_id is not None
            and r.private_reply_message_id is None
        ),
        None,
    )


def _reserve(platform: str, disclosure: str | None) -> int:
    from socialhood.services.sending import text_size

    return text_size(platform, render.with_disclosure("", disclosure)) if disclosure else 0


async def _draft(
    sessionmaker: async_sessionmaker[AsyncSession],
    request: drafting.DraftRequest,
    *,
    brand: drafting.Brand,
    disclosure: str | None,
) -> Drafted:
    try:
        result = await drafting.draft(sessionmaker, request, brand=brand)
    except QuotaExceeded:
        return Drafted(error=NO_CREDITS)
    except AIError as error:
        log.warning("automation_ai_reply_failed", error_code=error.code, ref=str(request.ref_id))
        return Drafted(error=_ai_failed(error))
    if result.can_answer and result.reply:
        return Drafted(text=render.with_disclosure(result.reply, disclosure), draft=result)
    reason = "output_blocked" if result.blocked is not None else "out_of_knowledge"
    return Drafted(escalation=reason, draft=result)


# ---------------------------------------------------------------- DMs


async def answer_dm(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    run_id: uuid.UUID,
    now: datetime,
) -> RunResult | None:
    """Draft and send (or escalate) a queued DM run's AI reply; returns the run's result."""
    async with sessionmaker() as session:
        run = await runs.get(session, run_id)
        if run is None or drafting_run([run]) is None:
            return None
        automation = await runs.get_automation(session, run.automation_id)
        msg = (
            await inbox.get_message(session, run.trigger_message_id)
            if run.trigger_message_id
            else None
        )
        conv = await inbox.get_conversation(session, msg.conversation_id) if msg else None
        if automation is None or msg is None or conv is None:
            return None
        allowed = entitlement(await current_plan(session), "ai_reply_automations")
        disclosure = await actions.disclosure(session)
        brand = await drafting.load_brand(session)
        request = drafting.DraftRequest(
            workspace_id=run.workspace_id,
            feature=FEATURE,
            platform=conv.platform,
            lines=await drafting.conversation_lines(session, msg),
            query=await drafting.retrieval_query(session, msg),
            ref_type="automation_run",
            ref_id=run.id,
            language=await drafting.message_language(session, msg.id),
            instructions=automation.ai_instructions,
            reserve=_reserve(conv.platform, disclosure),
        )
    drafted = (
        await _draft(sessionmaker, request, brand=brand, disclosure=disclosure)
        if allowed
        else Drafted(error=NOT_ON_PLAN)
    )
    return await _settle_dm(sessionmaker, redis, deps, run_id, msg.id, drafted, now=now)


async def _settle_dm(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    run_id: uuid.UUID,
    message_id: uuid.UUID,
    drafted: Drafted,
    *,
    now: datetime,
) -> RunResult | None:
    from socialhood.services import sending  # sending → … → ingest → the runtime → this module

    async with sessionmaker() as session:
        msg = await inbox.get_message(session, message_id)
        if msg is None:
            return None
        # The conversation, then the run: the order ingest and the queue take.
        conv = await ingest_rows.lock_conversation(session, msg.conversation_id)
        run = await runs.lock(session, run_id)
        if conv is None or run is None or drafting_run([run]) is None:
            return None
        sent: Message | None = None
        if drafted.text is not None:
            try:
                sent = await sending.queue_outbound(
                    session,
                    conv,
                    source="automation",
                    client_id=actions.client_id_for(run.id),
                    text=drafted.text,
                    automation_run_id=run.id,
                    deps=deps,
                    now=now,
                )
            except ApiError as error:
                run.result = RunResult.FAILED
                run.error_code, run.error_message = error.code, actions.api_error_reason(error)
                msg.automation_handled = False  # nothing answered it: the inbox AI may
            else:
                run.result = RunResult.SENT
                run.private_reply_message_id = sent.id
        elif drafted.escalation is not None:
            run.result = RunResult.ESCALATED
            run.error_code, run.error_message = drafted.escalation, drafted.not_sent_reason
            await _escalate(session, conv, drafted, run, message_id=msg.id, now=now)
        else:
            assert drafted.error is not None
            run.result = RunResult.FAILED
            run.error_code, run.error_message = drafted.error
            msg.automation_handled = False  # nothing answered it: the inbox AI may
        if drafted.draft is not None:
            session.add(_suggestion_row(conv, msg, run, drafted.draft, sent))
        await session.flush()
        await events.commit_and_publish(session, redis)
        log.info("automation_ai_reply", run_id=str(run_id), result=str(run.result))
        return RunResult(run.result)


def _suggestion_row(
    conv: Conversation,
    msg: Message,
    run: AutomationRun,
    draft: drafting.Draft,
    sent: Message | None,
) -> ReplySuggestion:
    """The automation's draft, kept like a suggestion (never pending)."""
    return ReplySuggestion(
        conversation_id=conv.id,
        message_id=msg.id,
        status=SuggestionStatus.SENT if sent is not None else SuggestionStatus.DISMISSED,
        can_answer=draft.can_answer,
        reply_text=draft.reply,
        missing_info=draft.missing_info,
        missing_topic=draft.missing_topic,
        model_confidence=draft.confidence,
        top_similarity=draft.top_similarity,
        used_chunk_ids=draft.used_chunk_ids,
        sent_message_id=sent.id if sent is not None else None,
        automation_run_id=run.id,
        model=draft.model,
        prompt_version=draft.prompt_version,
        input_tokens=draft.input_tokens,
        output_tokens=draft.output_tokens,
        latency_ms=draft.latency_ms,
    )


async def _escalate(
    session: AsyncSession,
    conv: Conversation | None,
    drafted: Drafted,
    run: AutomationRun,
    *,
    message_id: uuid.UUID | None,
    now: datetime,
) -> None:
    """ "Needs you" on the conversation (or only a notification without one) and the gap."""
    draft = drafted.draft
    if conv is not None:
        await escalate(
            session,
            conv,
            drafted.escalation,
            message_id=message_id,
            now=now,
            dedupe_key=f"automation_escalated:{run.id}",
        )
    else:
        await notify_admins(
            session,
            type="ai_escalated",
            severity="warning",
            title="An automation needs you",
            body=f"The AI reply wasn't sent: {REASON_COPY.get(drafted.escalation)}.",
            link=f"/automations/{run.automation_id}",
            dedupe_key=f"automation_escalated:{run.id}",
        )
    if draft is not None and draft.missing_topic:
        await knowledge_port.record_knowledge_gap(session, draft.missing_topic, message_id, now)


# ---------------------------------------------------------------- comments (private replies)


@dataclass(frozen=True)
class CommentDraft:
    text: str | None = None  # the private reply to send, with the disclosure line
    settled: bool = False  # escalated or failed instead; nothing to send


def _comment_line(comment: Comment, caption: str | None) -> drafting.Line:
    text = comment.text.strip()
    if caption and caption.strip():
        short = " ".join(caption.split())[:CAPTION_CHARS]
        text = f"{text}\n(a comment on the post: {short})"
    return drafting.Line("customer", text, target=True)


async def draft_for_comment(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    *,
    run_id: uuid.UUID,
    disclosure: str | None,
    now: datetime,
) -> CommentDraft:
    """The private reply for a queued comment run of an AI automation, or the run settled
    (escalated or failed) instead. Nothing when the run no longer waits."""
    async with sessionmaker() as session:
        queued = await runs.get(session, run_id)
        if queued is None or queued.trigger_comment_id is None or not _waiting(queued):
            return CommentDraft()
        automation = await runs.get_automation(session, queued.automation_id)
        comment = await comments_repo.get(session, queued.trigger_comment_id)
        acct = await social_accounts.get(session, comment.social_account_id) if comment else None
        if automation is None or comment is None or acct is None:
            return CommentDraft()
        allowed = entitlement(await current_plan(session), "ai_reply_automations")
        caption = await session.scalar(
            select(MediaItem.caption).where(MediaItem.id == comment.media_item_id)
        )
        brand = await drafting.load_brand(session)
    request = drafting.DraftRequest(
        workspace_id=queued.workspace_id,
        feature=FEATURE,
        platform=acct.platform,
        lines=[_comment_line(comment, caption)],
        query=comment.text[: drafting.QUERY_CHARS],
        ref_type="automation_run",
        ref_id=run_id,
        instructions=automation.ai_instructions,
        reserve=_reserve(acct.platform, disclosure),
    )
    drafted = (
        await _draft(sessionmaker, request, brand=brand, disclosure=disclosure)
        if allowed
        else Drafted(error=NOT_ON_PLAN)
    )
    if drafted.text is not None:
        return CommentDraft(text=drafted.text)
    settled = await _settle_comment(
        sessionmaker, redis, automation, comment, run_id, drafted, now=now
    )
    return CommentDraft(settled=settled)


def _waiting(run: AutomationRun) -> bool:
    return (
        run.result == RunResult.QUEUED
        and run.trigger_comment_id is not None
        and run.private_reply_message_id is None
    )


async def _settle_comment(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    automation: Automation,
    comment: Comment,
    run_id: uuid.UUID,
    drafted: Drafted,
    *,
    now: datetime,
) -> bool:
    async with sessionmaker() as session:
        # The conversation (if any), then the run: the order ingest and the queue take.
        escalating = drafted.escalation is not None
        conv = await _commenter_conversation(session, comment) if escalating else None
        run = await runs.lock(session, run_id)
        if run is None or not _waiting(run):
            return False
        if escalating:
            public = results.public_error(run)
            reason = f"{results.PRIVATE_PREFIX}{drafted.not_sent_reason}"
            run.result = RunResult.ESCALATED
            run.error_code = drafted.escalation
            run.error_message = f"{public[1]} {reason}" if public else reason
            await _escalate(session, conv, drafted, run, message_id=None, now=now)
        else:
            code, message = drafted.error or NO_CREDITS
            results.finish_comment_run(run, "failed", error_code=code, error_message=message)
        await session.flush()
        await events.commit_and_publish(session, redis)
    log.info(
        "automation_ai_private_reply_settled",
        automation_id=str(automation.id),
        run_id=str(run_id),
        escalation=drafted.escalation,
    )
    return True


async def _commenter_conversation(session: AsyncSession, comment: Comment) -> Conversation | None:
    """The commenter's DM conversation with the account, locked, when there is one with
    messages (an empty one is not in the inbox)."""
    if comment.contact_id is None:
        return None
    for conv in await ingest_rows.conversations_for_contact(session, comment.contact_id):
        if conv.social_account_id == comment.social_account_id and conv.last_message_at:
            return await ingest_rows.lock_conversation(session, conv.id)
    return None
