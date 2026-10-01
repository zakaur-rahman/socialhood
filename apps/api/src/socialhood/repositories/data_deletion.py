"""Meta data-deletion requests (not tenant-scoped).

A request's status: received (pending) → processing (its accounts are disconnected and their
purges queued) → completed (none of the platform user's accounts is left); failed while a purge
is being retried, back to processing when the retry starts.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.platform import DataDeletionRequest, DeletionStatus

OPEN = (DeletionStatus.RECEIVED, DeletionStatus.PROCESSING, DeletionStatus.FAILED)


async def get_by_code(session: AsyncSession, code: str) -> DataDeletionRequest | None:
    result = await session.scalars(
        select(DataDeletionRequest).where(DataDeletionRequest.confirmation_code == code)
    )
    return result.one_or_none()


async def set_status(session: AsyncSession, code: str, status: DeletionStatus) -> None:
    values: dict[str, object] = {"status": status}
    if status is DeletionStatus.COMPLETED:
        values["completed_at"] = datetime.now(UTC)
    await session.execute(
        update(DataDeletionRequest)
        .where(DataDeletionRequest.confirmation_code == code)
        .values(**values)
    )


async def open_requests(
    session: AsyncSession,
    platform_user_ids: Collection[str] | None = None,
    *,
    statuses: Collection[DeletionStatus] = OPEN,
) -> list[DataDeletionRequest]:
    """Requests not completed yet, oldest first; for these platform users when given."""
    query = select(DataDeletionRequest).where(DataDeletionRequest.status.in_(list(statuses)))
    if platform_user_ids is not None:
        if not platform_user_ids:
            return []
        query = query.where(DataDeletionRequest.platform_user_id.in_(list(platform_user_ids)))
    result = await session.scalars(query.order_by(DataDeletionRequest.created_at))
    return list(result.all())


async def move(
    session: AsyncSession,
    platform_user_ids: Collection[str],
    *,
    from_status: DeletionStatus,
    to_status: DeletionStatus,
) -> int:
    """The platform users' requests in ``from_status`` go to ``to_status``; returns how many."""
    if not platform_user_ids:
        return 0
    result = await session.execute(
        update(DataDeletionRequest)
        .where(
            DataDeletionRequest.platform_user_id.in_(list(platform_user_ids)),
            DataDeletionRequest.status == from_status,
        )
        .values(status=to_status)
        .returning(DataDeletionRequest.id)
    )
    return len(result.all())
