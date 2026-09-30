"""Which workspace a Dodo event belongs to (T8.3; TR-WH-05). A cross-workspace lookup before any
workspace is known, so it lives in webhooks/, where the tenant bypass is allowed (TR-TEN-04).

Order: the ``metadata.workspace_id`` the checkout set (TR-BIL-01), if that workspace exists and
isn't being deleted; else the workspace whose subscriptions.dodo_subscription_id matches the
event's ``subscription_id`` (subscription and payment events both carry it); else None
(ignored). Both come from a signed event, and only our checkout sets the metadata.

An ignored event that reports a live subscription of a deleted or deleting workspace names an
orphan (``orphaned_subscription``), which the handler cancels in Dodo (C-060).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.models.billing import Subscription
from socialhood.models.identity import Workspace, WorkspaceStatus


def _uuid(value: Any) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def resolve_workspace(session: AsyncSession, payload: Mapping[str, Any]) -> uuid.UUID | None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None
    metadata = data.get("metadata")
    wanted = _uuid(metadata.get("workspace_id")) if isinstance(metadata, Mapping) else None
    if wanted is not None:
        status = await session.scalar(select(Workspace.status).where(Workspace.id == wanted))
        if status == WorkspaceStatus.ACTIVE:
            return wanted
    subscription_id = data.get("subscription_id")
    if not isinstance(subscription_id, str) or not subscription_id:
        return None
    with tenant_bypass_scope():
        found = await session.scalar(
            select(Subscription.workspace_id)
            .join(Workspace, Workspace.id == Subscription.workspace_id)
            .where(
                Subscription.dodo_subscription_id == subscription_id,
                Workspace.status == WorkspaceStatus.ACTIVE,
            )
        )
    return found


# Dodo statuses in which the subscription bills, or can bill again.
LIVE_DODO_STATUSES = frozenset({"active", "on_hold", "paused", "past_due"})


async def orphaned_subscription(session: AsyncSession, payload: Mapping[str, Any]) -> str | None:
    """The subscription id when a subscription.* event reports a live subscription whose
    workspace is gone or being deleted, else None. That happens when a checkout is paid after its
    workspace was deleted (the grant is ignored, so the purge never learns of it), or when an event
    arrives for a subscription the purge hasn't cancelled yet. Call it only when
    ``resolve_workspace`` found nothing. Only our checkout sets ``metadata.workspace_id``, so an
    unknown id there is one of ours whose workspace was purged; an event with neither that nor a
    stored subscription id is not ours and is left alone."""
    if not str(payload.get("type", "")).startswith("subscription."):
        return None
    data = payload.get("data")
    if not isinstance(data, Mapping) or data.get("status") not in LIVE_DODO_STATUSES:
        return None
    subscription_id = data.get("subscription_id")
    if not isinstance(subscription_id, str) or not subscription_id:
        return None
    metadata = data.get("metadata")
    wanted = _uuid(metadata.get("workspace_id")) if isinstance(metadata, Mapping) else None
    if wanted is not None:
        status = await session.scalar(select(Workspace.status).where(Workspace.id == wanted))
        return subscription_id if status != WorkspaceStatus.ACTIVE else None
    with tenant_bypass_scope():
        status = await session.scalar(
            select(Workspace.status)
            .join(Subscription, Subscription.workspace_id == Workspace.id)
            .where(Subscription.dodo_subscription_id == subscription_id)
        )
    return subscription_id if status == WorkspaceStatus.DELETING else None
