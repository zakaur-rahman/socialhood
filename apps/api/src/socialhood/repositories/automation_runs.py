"""Automation runs and the runtime's lookups (T4.4, T4.6; F-11 runtime, FR-AUT-05, FR-AUT-10,
FR-AUT-16, TR-JOB-07). Tenant-scoped: reads are filtered by the session's workspace, inserts are
stamped with it, and bulk updates go through ``scoped_update``.

The private-reply queue is the account's runs with result ``queued``, found through their trigger
comment (a run keeps the account it matched on even if its automation moves to another). A run is
claimed by linking its private-reply message, so a claimed run is never sent twice.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Text,
    Uuid,
    and_,
    column,
    exists,
    func,
    or_,
    select,
    values,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.automations import (
    Automation,
    AutomationKeyword,
    AutomationPost,
    AutomationRun,
    AutomationStatus,
    Comment,
    PostScope,
    RunResult,
    SurgeOrder,
)
from socialhood.models.inbox import Contact, Conversation, Message, MessageStatus
from socialhood.repositories.base import scoped_delete, scoped_update
from socialhood.repositories.messages import NOT_YET_SENT
from socialhood.services.automations.matching import Candidate, MatchModeName, TriggerName

_FRESH = {"populate_existing": True}

# Runs that reached (or are reaching) the contact count toward the cooldown (FR-AUT-05); a
# failed or skipped run does not.
COOLDOWN_RESULTS = (RunResult.QUEUED, RunResult.SENT, RunResult.PARTIAL, RunResult.ESCALATED)
DELIVERED = (MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ)


@dataclass(frozen=True)
class Loaded:
    automation: Automation
    candidate: Candidate


# ---------------------------------------------------------------- matching


def _in_window(now: datetime) -> ColumnElement[bool]:
    """FR-AUT-17: the runtime ignores automations outside their run window."""
    return and_(
        or_(Automation.starts_at.is_(None), Automation.starts_at <= now),
        or_(Automation.ends_at.is_(None), Automation.ends_at > now),
    )


async def has_active(
    session: AsyncSession, social_account_id: uuid.UUID, triggers: Sequence[str]
) -> bool:
    """Whether the account has any active automation of these trigger types."""
    found = await session.scalar(
        select(Automation.id)
        .where(
            Automation.social_account_id == social_account_id,
            Automation.status == AutomationStatus.ACTIVE,
            Automation.trigger.in_(triggers),
        )
        .limit(1)
    )
    return found is not None


async def candidates(
    session: AsyncSession,
    social_account_id: uuid.UUID,
    triggers: Sequence[str],
    *,
    now: datetime,
) -> list[Loaded]:
    """The account's active automations of these trigger types inside their run window, with
    their normalised keywords (ix_automations_runtime). Only this account's: another account's
    (or workspace's) keyword never matches (FR-AUT-06)."""
    automations = list(
        (
            await session.scalars(
                select(Automation).where(
                    Automation.social_account_id == social_account_id,
                    Automation.status == AutomationStatus.ACTIVE,
                    Automation.trigger.in_(triggers),
                    _in_window(now),
                )
            )
        ).all()
    )
    if not automations:
        return []
    keywords: dict[uuid.UUID, list[str]] = {a.id: [] for a in automations}
    rows = await session.execute(
        select(AutomationKeyword.automation_id, AutomationKeyword.keyword_normalized)
        .where(AutomationKeyword.automation_id.in_(list(keywords)))
        .order_by(AutomationKeyword.created_at, AutomationKeyword.id)
    )
    for automation_id, keyword in rows.all():
        keywords[automation_id].append(keyword)
    return [
        Loaded(
            automation=a,
            candidate=Candidate(
                id=a.id,
                trigger=_trigger(a.trigger),
                match_mode=_mode(a.match_mode),
                keywords=tuple(keywords[a.id]),
                priority=a.priority,
                created_at=a.created_at,
            ),
        )
        for a in automations
    ]


def _trigger(value: str | None) -> TriggerName:
    if value == "comment_any":
        return "comment_any"
    return "comment_keyword" if value == "comment_keyword" else "dm_keyword"


def _mode(value: str) -> MatchModeName:
    return "exact" if value == "exact" else "contains" if value == "contains" else "word"


async def event_runs(
    session: AsyncSession,
    *,
    message_id: uuid.UUID | None = None,
    comment_id: uuid.UUID | None = None,
) -> list[AutomationRun]:
    """Every run recorded for one trigger event."""
    condition = (
        AutomationRun.trigger_message_id == message_id
        if message_id is not None
        else AutomationRun.trigger_comment_id == comment_id
    )
    return list((await session.scalars(select(AutomationRun).where(condition))).all())


async def on_cooldown(
    session: AsyncSession, automation_id: uuid.UUID, contact_id: uuid.UUID, *, since: datetime
) -> bool:
    """A run of this automation reached the contact since ``since`` (the cooldown index)."""
    found = await session.scalar(
        select(AutomationRun.id)
        .where(
            AutomationRun.automation_id == automation_id,
            AutomationRun.contact_id == contact_id,
            AutomationRun.created_at >= since,
            AutomationRun.result.in_(COOLDOWN_RESULTS),
        )
        .limit(1)
    )
    return found is not None


async def in_scope(session: AsyncSession, automation: Automation, media_item_id: uuid.UUID) -> bool:
    """FR-AUT-01, FR-AUT-18: all posts, or the posts linked to the automation (selected ones, or
    the next post once T4.7 links it)."""
    if automation.post_scope == PostScope.ALL:
        return True
    found = await session.scalar(
        select(AutomationPost.id)
        .where(
            AutomationPost.automation_id == automation.id,
            AutomationPost.media_item_id == media_item_id,
        )
        .limit(1)
    )
    return found is not None


async def last_variant(
    session: AsyncSession, automation_id: uuid.UUID, media_item_id: uuid.UUID
) -> int | None:
    """The public reply variation this automation used last on this post (FR-AUT-14)."""
    value = await session.scalar(
        select(AutomationRun.public_reply_variant)
        .join(Comment, Comment.id == AutomationRun.trigger_comment_id)
        .where(
            AutomationRun.automation_id == automation_id,
            Comment.media_item_id == media_item_id,
            AutomationRun.public_reply_variant.is_not(None),
        )
        .order_by(AutomationRun.created_at.desc(), AutomationRun.id.desc())
        .limit(1)
    )
    return None if value is None else int(value)


async def insert_run(session: AsyncSession, values: dict[str, Any]) -> AutomationRun | None:
    """One run per automation and trigger event (the partial unique indexes); None when this
    automation already has a run for the event."""
    statement = (
        insert(AutomationRun)
        .values(workspace_id=require_workspace(), **values)
        .on_conflict_do_nothing()
        .returning(AutomationRun)
    )
    return (await session.scalars(statement, execution_options=_FRESH)).one_or_none()


async def get(session: AsyncSession, run_id: uuid.UUID) -> AutomationRun | None:
    return (
        await session.scalars(select(AutomationRun).where(AutomationRun.id == run_id))
    ).one_or_none()


async def lock(session: AsyncSession, run_id: uuid.UUID) -> AutomationRun | None:
    return (
        await session.scalars(
            select(AutomationRun).where(AutomationRun.id == run_id).with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def get_automation(session: AsyncSession, automation_id: uuid.UUID) -> Automation | None:
    return (
        await session.scalars(select(Automation).where(Automation.id == automation_id))
    ).one_or_none()


# ---------------------------------------------------------------- replies (FR-AUT-16)


async def mark_contact_replied(
    session: AsyncSession, contact_id: uuid.UUID, *, at: datetime, window: timedelta
) -> int:
    """The contact wrote at ``at``: runs whose DM or private reply reached them in the 24 h
    before get ``contact_replied_at`` (only the first reply counts)."""
    sent_before = (
        select(Message.id)
        .where(
            Message.workspace_id == require_workspace(),
            Message.status.in_(DELIVERED),
            Message.occurred_at <= at,
            Message.occurred_at > at - window,
        )
        .scalar_subquery()
    )
    result = await session.execute(
        scoped_update(AutomationRun, contact_id=contact_id)
        .where(
            AutomationRun.contact_replied_at.is_(None),
            AutomationRun.private_reply_message_id.in_(sent_before),
        )
        .values(contact_replied_at=at)
        .returning(AutomationRun.id)
    )
    return len(result.all())


# ---------------------------------------------------------------- the private-reply queue


def _on_account(
    social_account_id: uuid.UUID,
    *,
    commented_before: datetime | None = None,
    commented_after: datetime | None = None,
) -> ColumnElement[bool]:
    """The run's comment is on this account (and older or newer than a time): an EXISTS probe
    per run, so queries walk the queued-runs index instead of every comment of the account."""
    conditions = [
        Comment.id == AutomationRun.trigger_comment_id,
        Comment.social_account_id == social_account_id,
    ]
    if commented_before is not None:
        conditions.append(Comment.commented_at < commented_before)
    if commented_after is not None:
        conditions.append(Comment.commented_at >= commented_after)
    return exists().where(*conditions)


def _unclaimed() -> ColumnElement[bool]:
    return and_(
        AutomationRun.result == RunResult.QUEUED,
        AutomationRun.private_reply_message_id.is_(None),
    )


async def queued_automations(
    session: AsyncSession, social_account_id: uuid.UUID
) -> list[Automation]:
    """Automations with unclaimed queued runs on this account, in priority order."""
    waiting_runs = exists().where(
        AutomationRun.automation_id == Automation.id,
        _unclaimed(),
        _on_account(social_account_id),
    )
    result = await session.scalars(
        select(Automation)
        .where(waiting_runs)
        .order_by(Automation.priority, Automation.created_at, Automation.id)
    )
    return list(result.all())


async def expire_queued(
    session: AsyncSession,
    social_account_id: uuid.UUID,
    automation_ids: Sequence[uuid.UUID],
    *,
    commented_before: datetime,
    code: str,
    message: str,
) -> int:
    """Queued runs whose comment is past Instagram's 7-day limit become skipped_expired. A run
    is created after its comment, so only runs older than the limit are looked at; a comment
    matched when already almost 7 days old is never sent (``claim``) and is marked once its run
    is that old too."""
    if not automation_ids:
        return 0
    result = await session.execute(
        scoped_update(AutomationRun, result=RunResult.QUEUED)
        .where(
            AutomationRun.automation_id.in_(list(automation_ids)),
            AutomationRun.private_reply_message_id.is_(None),
            AutomationRun.created_at < commented_before,
            _on_account(social_account_id, commented_before=commented_before),
        )
        .values(result=RunResult.SKIPPED_EXPIRED, error_code=code, error_message=message)
        .returning(AutomationRun.id)
    )
    return len(result.all())


async def claim(
    session: AsyncSession,
    automation: Automation,
    social_account_id: uuid.UUID,
    *,
    commented_after: datetime,
    limit: int = 1,
) -> list[AutomationRun]:
    """Lock the automation's next unclaimed queued runs in its surge order (oldest or newest
    first), skipping rows another worker holds and comments past the 7-day limit."""
    newest_first = automation.surge_order == SurgeOrder.NEWEST_FIRST
    order = (
        (AutomationRun.created_at.desc(), AutomationRun.id.desc())
        if newest_first
        else (AutomationRun.created_at, AutomationRun.id)
    )
    result = await session.scalars(
        select(AutomationRun)
        .where(
            AutomationRun.automation_id == automation.id,
            _unclaimed(),
            _on_account(social_account_id, commented_after=commented_after),
        )
        .order_by(*order)
        .limit(limit)
        .with_for_update(skip_locked=True, of=AutomationRun),
        execution_options=_FRESH,
    )
    return list(result.all())


def sendable(now: datetime) -> ColumnElement[bool]:
    """Automations whose queued runs are sent: active ones, and ones whose run window has
    ended (matches made inside the window still get their DM). A paused one holds its queue;
    public-reply-only ones never DM."""
    return and_(
        or_(
            Automation.status == AutomationStatus.ACTIVE,
            and_(Automation.ends_at.is_not(None), Automation.ends_at <= now),
        ),
        Automation.surge_order != SurgeOrder.PUBLIC_ONLY,
    )


async def waiting(
    session: AsyncSession,
    social_account_id: uuid.UUID,
    *,
    now: datetime,
    unclaimed: bool = False,
    expires_after: timedelta = timedelta(days=7),
) -> int:
    """Queued private replies of the account that the queue will still send (FR-AUT-10's ETA):
    sendable automations, comments inside the 7-day limit; with ``unclaimed``, only those no
    drain has started sending."""
    conditions = [
        AutomationRun.result == RunResult.QUEUED,
        _on_account(social_account_id, commented_after=now - expires_after),
        sendable(now),
    ]
    if unclaimed:
        conditions.append(AutomationRun.private_reply_message_id.is_(None))
    count = await session.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .where(*conditions)
    )
    return int(count or 0)


async def waiting_by_account(
    session: AsyncSession, *, now: datetime, expires_after: timedelta = timedelta(days=7)
) -> dict[uuid.UUID, int]:
    """``waiting`` for every account of the workspace in one query (the automations list and
    summary): queued runs of sendable automations whose comment is inside the 7-day limit."""
    rows = await session.execute(
        select(Comment.social_account_id, func.count())
        .select_from(AutomationRun)
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .join(Comment, Comment.id == AutomationRun.trigger_comment_id)
        .where(
            AutomationRun.result == RunResult.QUEUED,
            Comment.commented_at >= now - expires_after,
            sendable(now),
        )
        .group_by(Comment.social_account_id)
    )
    return {account_id: int(count) for account_id, count in rows.all()}


async def automation_names(
    session: AsyncSession, run_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID, str]]:
    """The automation (id, name) behind each run, for "Automation · {name}" on its messages."""
    if not run_ids:
        return {}
    rows = await session.execute(
        select(AutomationRun.id, Automation.id, Automation.name)
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .where(AutomationRun.id.in_(set(run_ids)))
    )
    return {run_id: (automation_id, name) for run_id, automation_id, name in rows.all()}


async def queued_for(session: AsyncSession, automation_id: uuid.UUID) -> int:
    """The automation's runs waiting in the private-reply queue (ix_automation_runs_queued)."""
    count = await session.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(
            AutomationRun.automation_id == automation_id,
            AutomationRun.result == RunResult.QUEUED,
        )
    )
    return int(count or 0)


async def mark_replies_sent(
    session: AsyncSession, sent: Sequence[tuple[uuid.UUID, str | None]], *, at: datetime
) -> None:
    """A batch's private replies went out: (message id, platform id) each, in one statement.
    Like ``messages.mark_sent``, a message another path already confirmed is left alone."""
    if not sent:
        return
    rows = values(column("id", Uuid()), column("platform_id", Text()), name="sent_replies").data(
        [(message_id, platform_id) for message_id, platform_id in sent]
    )
    await session.execute(
        scoped_update(Message)
        .where(Message.id == rows.c.id, Message.status.in_(NOT_YET_SENT))
        .values(
            status=MessageStatus.SENT,
            sent_at=at,
            error_code=None,
            error_message=None,
            platform_message_id=func.coalesce(rows.c.platform_id, Message.platform_message_id),
        )
    )


async def release_claims(session: AsyncSession, message_ids: Sequence[uuid.UUID]) -> None:
    """Private replies that never reached the platform: delete their messages, which puts their
    runs back in the queue (``private_reply_message_id`` is ON DELETE SET NULL)."""
    if message_ids:
        await session.execute(scoped_delete(Message).where(Message.id.in_(list(message_ids))))


# ---------------------------------------------------------------- bulk reads for a queue batch


async def contacts_by_id(session: AsyncSession, contact_ids: Sequence[uuid.UUID]) -> list[Contact]:
    if not contact_ids:
        return []
    result = await session.scalars(select(Contact).where(Contact.id.in_(list(contact_ids))))
    return list(result.all())


async def lock_conversations_of(
    session: AsyncSession, social_account_id: uuid.UUID, contact_ids: Sequence[uuid.UUID]
) -> list[Conversation]:
    """The account's conversations with these contacts, locked (the caller creates missing
    ones)."""
    if not contact_ids:
        return []
    result = await session.scalars(
        select(Conversation)
        .where(
            Conversation.social_account_id == social_account_id,
            Conversation.contact_id.in_(list(contact_ids)),
        )
        .order_by(Conversation.id)
        .with_for_update(),
        execution_options=_FRESH,
    )
    return list(result.all())


async def lock_conversations(
    session: AsyncSession, conversation_ids: Sequence[uuid.UUID]
) -> list[Conversation]:
    if not conversation_ids:
        return []
    result = await session.scalars(
        select(Conversation)
        .where(Conversation.id.in_(list(conversation_ids)))
        .order_by(Conversation.id)
        .with_for_update(),
        execution_options=_FRESH,
    )
    return list(result.all())


async def messages_by_id(session: AsyncSession, message_ids: Sequence[uuid.UUID]) -> list[Message]:
    if not message_ids:
        return []
    result = await session.scalars(
        select(Message).where(Message.id.in_(list(message_ids))), execution_options=_FRESH
    )
    return list(result.all())


async def lock_many(session: AsyncSession, run_ids: Sequence[uuid.UUID]) -> list[AutomationRun]:
    if not run_ids:
        return []
    result = await session.scalars(
        select(AutomationRun)
        .where(AutomationRun.id.in_(list(run_ids)))
        .order_by(AutomationRun.id)
        .with_for_update(),
        execution_options=_FRESH,
    )
    return list(result.all())
