"""Retention deletes for purge_expired (§5.9, TR-WH-07, TR-OPS-04, TR-AGT-08).

Each function deletes at most ``limit`` rows past their retention and returns how many went, so the
job deletes in short batches and commits between them. The time-based ones span every workspace
(a retention period is the same for all); the message history ones name the workspace.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from socialhood.models.agent import FINAL_RUN_STATUSES, AgentRun
from socialhood.models.billing import AiUsageEvent, Subscription
from socialhood.models.identity import Workspace, WorkspaceStatus
from socialhood.models.inbox import Conversation, Message
from socialhood.models.notifications import Notification
from socialhood.models.platform import WebhookEvent


async def _delete(
    session: AsyncSession, key: InstrumentedAttribute[Any], limit: int, *where: ColumnElement[bool]
) -> int:
    batch = select(key).where(*where).limit(limit)
    statement = (
        delete(key.class_)
        .where(key.in_(batch))
        .returning(key)
        .execution_options(synchronize_session=False)  # nothing loaded to keep in step
    )
    return len((await session.execute(statement)).all())


async def webhook_events_before(session: AsyncSession, cutoff: datetime, *, limit: int) -> int:
    """TR-WH-07 and TR-OPS-04: stored events, the failed ones (the dead-letter set) included."""
    return await _delete(session, WebhookEvent.id, limit, WebhookEvent.received_at < cutoff)


async def notifications_before(session: AsyncSession, cutoff: datetime, *, limit: int) -> int:
    return await _delete(session, Notification.id, limit, Notification.created_at < cutoff)


async def ai_usage_events_before(session: AsyncSession, cutoff: datetime, *, limit: int) -> int:
    return await _delete(session, AiUsageEvent.id, limit, AiUsageEvent.created_at < cutoff)


async def agent_runs_before(session: AsyncSession, cutoff: datetime, *, limit: int) -> int:
    """TR-AGT-08: finished runs with their steps and approvals (ON DELETE CASCADE); a run still
    going is left alone however old."""
    return await _delete(
        session,
        AgentRun.id,
        limit,
        AgentRun.created_at < cutoff,
        AgentRun.status.in_([status.value for status in FINAL_RUN_STATUSES]),
    )


async def workspaces_on_plans(session: AsyncSession, plans: Collection[str]) -> list[uuid.UUID]:
    """Active workspaces on these plans (no subscription row reads as Free, like
    billing/plans.current_plan). Reads subscriptions across workspaces: the caller (in jobs/)
    opens the tenant bypass (TR-TEN-04)."""
    result = await session.scalars(
        select(Workspace.id)
        .outerjoin(Subscription, Subscription.workspace_id == Workspace.id)
        .where(
            func.coalesce(Subscription.plan, "free").in_(list(plans)),
            Workspace.status == WorkspaceStatus.ACTIVE,
        )
        .order_by(Workspace.id)
    )
    return list(result.all())


async def messages_before(
    session: AsyncSession, workspace_id: uuid.UUID, cutoff: datetime, *, limit: int
) -> int:
    """§5.9: a workspace's messages older than its plan's history; their analyses, suggestions
    and decisions go with them (ON DELETE CASCADE)."""
    return await _delete(
        session,
        Message.id,
        limit,
        Message.workspace_id == workspace_id,
        Message.occurred_at < cutoff,
    )


async def empty_conversations(
    session: AsyncSession, workspace_id: uuid.UUID, cutoff: datetime, *, limit: int
) -> int:
    """§5.9: conversations left without messages once their history expired. One whose last
    activity is newer than the cutoff is kept (a thread that has only just started)."""
    return await _delete(
        session,
        Conversation.id,
        limit,
        Conversation.workspace_id == workspace_id,
        func.coalesce(Conversation.last_message_at, Conversation.created_at) < cutoff,
        ~exists().where(Message.conversation_id == Conversation.id),
    )
