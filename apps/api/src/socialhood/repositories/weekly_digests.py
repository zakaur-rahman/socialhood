"""The once-a-week guard of the digest (weekly_digests; FR-NOT-04, T8.7). Claims and results run
in the workspace's scope; ``claimed_weeks`` is the job's cross-workspace pre-check."""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import date, datetime
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.notifications import DigestStatus, WeeklyDigest
from socialhood.repositories.base import scoped_update


async def claim(session: AsyncSession, week_start: date) -> uuid.UUID | None:
    """This workspace's row for the week, pending; None when the week was claimed already (the
    unique (workspace, week_start) waits for a concurrent claim to commit or roll back)."""
    statement = (
        insert(WeeklyDigest)
        .values(
            workspace_id=require_workspace(), week_start=week_start, status=DigestStatus.PENDING
        )
        .on_conflict_do_nothing(index_elements=[WeeklyDigest.workspace_id, WeeklyDigest.week_start])
        .returning(WeeklyDigest.id)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def finish(
    session: AsyncSession,
    digest_id: uuid.UUID,
    *,
    status: DigestStatus,
    recipients: int,
    stats: dict[str, Any] | None,
    sent_at: datetime | None,
    error: str | None = None,
) -> None:
    await session.execute(
        scoped_update(WeeklyDigest, id=digest_id).values(
            status=status, recipients=recipients, stats=stats, sent_at=sent_at, error=error
        )
    )


async def get_week(session: AsyncSession, week_start: date) -> WeeklyDigest | None:
    return (
        await session.scalars(select(WeeklyDigest).where(WeeklyDigest.week_start == week_start))
    ).one_or_none()


async def claimed_weeks(
    session: AsyncSession, pairs: Collection[tuple[uuid.UUID, date]]
) -> set[tuple[uuid.UUID, date]]:
    """Which (workspace, week_start) pairs already have a digest row (across workspaces: the
    caller holds the tenant bypass)."""
    if not pairs:
        return set()
    rows = await session.execute(
        select(WeeklyDigest.workspace_id, WeeklyDigest.week_start).where(
            tuple_(WeeklyDigest.workspace_id, WeeklyDigest.week_start).in_(list(pairs))
        )
    )
    return {(row.workspace_id, row.week_start) for row in rows}
