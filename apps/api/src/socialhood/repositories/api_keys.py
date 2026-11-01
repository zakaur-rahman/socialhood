"""API key queries that span every workspace (C-167): the keys about to expire, for the daily
notice (jobs/tasks/api_keys.py). Run in tenant_bypass_scope; the notice itself is written per
workspace (services/api_keys.notify_expiring)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.api_keys import ApiKey


async def expiring_unnoticed(
    session: AsyncSession, now: datetime, until: datetime, *, limit: int
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Unrevoked keys that expire after ``now`` and by ``until`` and whose owners weren't told
    yet, as (key id, workspace id)."""
    rows = await session.execute(
        select(ApiKey.id, ApiKey.workspace_id)
        .where(
            ApiKey.revoked_at.is_(None),
            ApiKey.expiry_notified_at.is_(None),
            ApiKey.expires_at > now,
            ApiKey.expires_at <= until,
        )
        .order_by(ApiKey.expires_at, ApiKey.id)
        .limit(limit)
    )
    return [(key_id, workspace_id) for key_id, workspace_id in rows.all()]
