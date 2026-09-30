"""Which workspace a Dodo event belongs to (T8.3; TR-WH-05). A cross-workspace lookup before any
workspace is known, so it lives in webhooks/, where the tenant bypass is allowed (TR-TEN-04).

Order: the ``metadata.workspace_id`` the checkout set (TR-BIL-01), if that workspace exists and
isn't being deleted; else the workspace whose subscriptions.dodo_subscription_id matches the
event's ``subscription_id`` (subscription and payment events both carry it); else None
(ignored). Both come from a signed event, and only our checkout sets the metadata.
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
