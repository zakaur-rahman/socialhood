"""The Activity page's reads (GR-05): failures and runs across automations, sends, outbound
webhooks and accounts. Read-only and tenant-scoped (the session filter limits every table to the
current workspace). Each function returns one source newest first, at most ``limit`` rows after
``before`` (a keyset on (time, id)), so the feed can merge them. No payloads are selected."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import (
    Automation,
    AutomationRun,
    AutomationRunStep,
    RunResult,
    StepStatus,
)
from socialhood.models.broadcasts import Broadcast, BroadcastStatus
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.inbox import (
    Contact,
    Conversation,
    Direction,
    Message,
    MessageSource,
    MessageStatus,
)
from socialhood.models.integrations import DeliveryStatus, WebhookDelivery, WebhookEndpoint
from socialhood.models.orders import Order
from socialhood.models.sequences import RunStatus, Sequence, SequenceStepRun

Before = tuple[datetime, uuid.UUID]

# A run that did less than it should, or nothing: shown when "failures only" is on.
FAILURE_RESULTS = (
    RunResult.FAILED,
    RunResult.PARTIAL,
    RunResult.SKIPPED_EXPIRED,
    RunResult.SKIPPED_READ_ONLY,
)
MESSAGE_SOURCES = (
    MessageSource.AUTOMATION,
    MessageSource.HUMAN,
    MessageSource.AI_AUTO,
    MessageSource.BROADCAST,
)
ACCOUNT_PROBLEMS = (AccountStatus.NEEDS_RECONNECT, AccountStatus.ERROR)


def _after(query: Any, at: Any, row_id: Any, before: Before | None) -> Any:
    if before is None:
        return query
    return query.where(tuple_(at, row_id) < tuple_(before[0], before[1]))


def _newest(query: Any, at: Any, row_id: Any, limit: int) -> Any:
    return query.order_by(at.desc(), row_id.desc()).limit(limit)


async def runs(
    session: AsyncSession,
    *,
    before: Before | None,
    limit: int,
    failures_only: bool,
    automation_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
) -> list[Any]:
    query = (
        select(
            AutomationRun.id,
            AutomationRun.created_at.label("at"),
            AutomationRun.result,
            AutomationRun.error_code,
            AutomationRun.error_message,
            AutomationRun.automation_id,
            AutomationRun.conversation_id,
            Automation.name.label("automation_name"),
            Automation.social_account_id.label("account_id"),
            SocialAccount.platform,
            SocialAccount.username.label("account_username"),
            SocialAccount.display_name.label("account_display_name"),
            Contact.username.label("contact_username"),
            Contact.display_name.label("contact_display_name"),
        )
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .outerjoin(SocialAccount, SocialAccount.id == Automation.social_account_id)
        .outerjoin(Contact, Contact.id == AutomationRun.contact_id)
    )
    if failures_only:
        query = query.where(AutomationRun.result.in_(FAILURE_RESULTS))
    if automation_id is not None:
        query = query.where(AutomationRun.automation_id == automation_id)
    if account_id is not None:
        query = query.where(Automation.social_account_id == account_id)
    query = _after(query, AutomationRun.created_at, AutomationRun.id, before)
    query = _newest(query, AutomationRun.created_at, AutomationRun.id, limit)
    return list((await session.execute(query)).all())


async def failed_steps(
    session: AsyncSession,
    *,
    before: Before | None,
    limit: int,
    automation_id: uuid.UUID | None,
    account_id: uuid.UUID | None,
) -> list[Any]:
    """Flow steps that failed in a run that is not itself listed as failed (a later step; the
    first message's failure settles the run, which the run row already shows)."""
    query = (
        select(
            AutomationRunStep.id,
            AutomationRunStep.created_at.label("at"),
            AutomationRunStep.step_id,
            AutomationRunStep.kind,
            AutomationRunStep.detail,
            AutomationRun.automation_id,
            AutomationRun.conversation_id,
            Automation.name.label("automation_name"),
            Automation.social_account_id.label("account_id"),
            SocialAccount.platform,
            SocialAccount.username.label("account_username"),
            SocialAccount.display_name.label("account_display_name"),
            Contact.username.label("contact_username"),
            Contact.display_name.label("contact_display_name"),
        )
        .join(AutomationRun, AutomationRun.id == AutomationRunStep.run_id)
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .outerjoin(SocialAccount, SocialAccount.id == Automation.social_account_id)
        .outerjoin(Contact, Contact.id == AutomationRun.contact_id)
        .where(
            AutomationRunStep.status == StepStatus.FAILED,
            AutomationRun.result.not_in(FAILURE_RESULTS),
        )
    )
    if automation_id is not None:
        query = query.where(AutomationRun.automation_id == automation_id)
    if account_id is not None:
        query = query.where(Automation.social_account_id == account_id)
    query = _after(query, AutomationRunStep.created_at, AutomationRunStep.id, before)
    query = _newest(query, AutomationRunStep.created_at, AutomationRunStep.id, limit)
    return list((await session.execute(query)).all())


async def failed_messages(
    session: AsyncSession,
    *,
    before: Before | None,
    limit: int,
    account_id: uuid.UUID | None,
) -> list[Any]:
    """Outbound sends that failed and are not an automation run's (the run shows those)."""
    query = (
        select(
            Message.id,
            Message.occurred_at.label("at"),
            Message.source,
            Message.error_code,
            Message.error_message,
            Message.conversation_id,
            Message.social_account_id.label("account_id"),
            SocialAccount.platform,
            SocialAccount.username.label("account_username"),
            SocialAccount.display_name.label("account_display_name"),
            Contact.username.label("contact_username"),
            Contact.display_name.label("contact_display_name"),
        )
        .join(SocialAccount, SocialAccount.id == Message.social_account_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(
            Message.direction == Direction.OUTBOUND,
            Message.status == MessageStatus.FAILED,
            Message.source.in_(MESSAGE_SOURCES),
            Message.automation_run_id.is_(None),
            Message.deleted_at.is_(None),
        )
    )
    if account_id is not None:
        query = query.where(Message.social_account_id == account_id)
    query = _after(query, Message.occurred_at, Message.id, before)
    query = _newest(query, Message.occurred_at, Message.id, limit)
    return list((await session.execute(query)).all())


async def stopped_broadcasts(
    session: AsyncSession, *, before: Before | None, limit: int, account_id: uuid.UUID | None
) -> list[Any]:
    """Broadcasts that are paused, or failed to start, with the reason (GR-23)."""
    query = (
        select(
            Broadcast.id,
            Broadcast.updated_at.label("at"),
            Broadcast.name,
            Broadcast.status,
            Broadcast.paused_code,
            Broadcast.paused_reason,
            Broadcast.social_account_id.label("account_id"),
            SocialAccount.platform,
            SocialAccount.username.label("account_username"),
            SocialAccount.display_name.label("account_display_name"),
        )
        .join(SocialAccount, SocialAccount.id == Broadcast.social_account_id)
        .where(
            Broadcast.status.in_((BroadcastStatus.PAUSED, BroadcastStatus.FAILED)),
            Broadcast.paused_reason.is_not(None),
        )
    )
    if account_id is not None:
        query = query.where(Broadcast.social_account_id == account_id)
    query = _after(query, Broadcast.updated_at, Broadcast.id, before)
    query = _newest(query, Broadcast.updated_at, Broadcast.id, limit)
    return list((await session.execute(query)).all())


async def sequence_steps(
    session: AsyncSession,
    *,
    before: Before | None,
    limit: int,
    failures_only: bool,
    account_id: uuid.UUID | None,
) -> list[Any]:
    """What sequences did at each step: sent, skipped with the reason, failed (GR-24). With
    ``failures_only`` only the skipped and failed ones."""
    query = (
        select(
            SequenceStepRun.id,
            SequenceStepRun.ran_at.label("at"),
            SequenceStepRun.status,
            SequenceStepRun.position,
            SequenceStepRun.reason_code,
            SequenceStepRun.reason,
            SequenceStepRun.sequence_id,
            Sequence.name.label("sequence_name"),
            SequenceStepRun.social_account_id.label("account_id"),
            SocialAccount.platform,
            SocialAccount.username.label("account_username"),
            SocialAccount.display_name.label("account_display_name"),
            Contact.username.label("contact_username"),
            Contact.display_name.label("contact_display_name"),
        )
        .join(Sequence, Sequence.id == SequenceStepRun.sequence_id)
        .join(SocialAccount, SocialAccount.id == SequenceStepRun.social_account_id)
        .join(Contact, Contact.id == SequenceStepRun.contact_id)
    )
    if failures_only:
        query = query.where(SequenceStepRun.status != RunStatus.SENT)
    if account_id is not None:
        query = query.where(SequenceStepRun.social_account_id == account_id)
    query = _after(query, SequenceStepRun.ran_at, SequenceStepRun.id, before)
    query = _newest(query, SequenceStepRun.ran_at, SequenceStepRun.id, limit)
    return list((await session.execute(query)).all())


async def orders_settled(
    session: AsyncSession,
    *,
    before: Before | None,
    limit: int,
    failures_only: bool,
    account_id: uuid.UUID | None,
) -> list[Any]:
    """Orders that were paid (and since shipped or refunded), or expired without payment (GR-32).
    With ``failures_only`` only the expired ones."""
    at = func.coalesce(Order.paid_at, Order.updated_at)
    wanted = ("expired",) if failures_only else ("paid", "fulfilled", "refunded", "expired")
    query = (
        select(
            Order.id,
            at.label("at"),
            Order.number,
            Order.status,
            Order.currency,
            Order.total_minor,
            Contact.social_account_id.label("account_id"),
            SocialAccount.platform,
            SocialAccount.username.label("account_username"),
            SocialAccount.display_name.label("account_display_name"),
            Contact.username.label("contact_username"),
            Contact.display_name.label("contact_display_name"),
        )
        .join(Contact, Contact.id == Order.contact_id)
        .join(SocialAccount, SocialAccount.id == Contact.social_account_id)
        .where(Order.status.in_(wanted))
    )
    if account_id is not None:
        query = query.where(Contact.social_account_id == account_id)
    query = _after(query, at, Order.id, before)
    query = _newest(query, at, Order.id, limit)
    return list((await session.execute(query)).all())


async def failed_deliveries(
    session: AsyncSession, *, before: Before | None, limit: int
) -> list[Any]:
    """Outbound webhook deliveries that ran out of attempts (GR-04). No payload: the feed shows
    the endpoint's name or host."""
    query = (
        select(
            WebhookDelivery.id,
            WebhookDelivery.created_at.label("at"),
            WebhookDelivery.event_type,
            WebhookDelivery.error,
            WebhookDelivery.response_code,
            WebhookDelivery.endpoint_id,
            WebhookEndpoint.url.label("endpoint_url"),
            WebhookEndpoint.description.label("endpoint_description"),
            WebhookEndpoint.status.label("endpoint_status"),
        )
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(WebhookDelivery.status == DeliveryStatus.FAILED)
    )
    query = _after(query, WebhookDelivery.created_at, WebhookDelivery.id, before)
    query = _newest(query, WebhookDelivery.created_at, WebhookDelivery.id, limit)
    return list((await session.execute(query)).all())


async def broken_accounts(
    session: AsyncSession, *, before: Before | None, limit: int, account_id: uuid.UUID | None
) -> list[Any]:
    """Accounts that need reconnecting or are in error now. There is no status history: the row
    stands for the account's current state, at the time it last changed."""
    query = select(
        SocialAccount.id,
        SocialAccount.updated_at.label("at"),
        SocialAccount.status,
        SocialAccount.last_error,
        SocialAccount.platform,
        SocialAccount.username.label("account_username"),
        SocialAccount.display_name.label("account_display_name"),
    ).where(
        SocialAccount.status.in_(ACCOUNT_PROBLEMS),
        SocialAccount.deletion_requested_at.is_(None),
    )
    if account_id is not None:
        query = query.where(SocialAccount.id == account_id)
    query = _after(query, SocialAccount.updated_at, SocialAccount.id, before)
    query = _newest(query, SocialAccount.updated_at, SocialAccount.id, limit)
    return list((await session.execute(query)).all())


async def failing_automations(
    session: AsyncSession, *, since: datetime, at_least: int, limit: int
) -> list[Any]:
    """Automations with ``at_least`` failed or partial runs since ``since``, across workspaces
    (the alert job opens tenant_bypass_scope), with their most common error code."""
    count = func.count().label("failures")
    query = (
        select(
            AutomationRun.workspace_id,
            AutomationRun.automation_id,
            Automation.name.label("automation_name"),
            SocialAccount.platform,
            count,
            func.mode().within_group(AutomationRun.error_code).label("common_code"),
        )
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .outerjoin(SocialAccount, SocialAccount.id == Automation.social_account_id)
        .where(
            AutomationRun.created_at >= since,
            AutomationRun.result.in_((RunResult.FAILED, RunResult.PARTIAL)),
        )
        .group_by(
            AutomationRun.workspace_id,
            AutomationRun.automation_id,
            Automation.name,
            SocialAccount.platform,
        )
        .having(count >= at_least)
        .order_by(count.desc())
        .limit(limit)
    )
    return list((await session.execute(query)).all())
