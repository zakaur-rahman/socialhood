"""Meta data-deletion requests (not tenant-scoped)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.platform import DataDeletionRequest, DeletionStatus


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
