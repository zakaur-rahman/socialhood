"""Sequence reads and writes (GR-24). Tenant-scoped through the session, except ``due``, which the
sweeper calls inside ``tenant_bypass_scope`` to find work across workspaces."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.inbox import Contact
from socialhood.models.sequences import (
    EnrolmentStatus,
    RunStatus,
    Sequence,
    SequenceEnrolment,
    SequenceStatus,
    SequenceStep,
    SequenceStepRun,
)
from socialhood.repositories.base import scoped_update


async def get(
    session: AsyncSession, sequence_id: uuid.UUID, *, lock: bool = False
) -> Sequence | None:
    query = select(Sequence).where(Sequence.id == sequence_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(query)


async def steps_of(session: AsyncSession, sequence_id: uuid.UUID) -> list[SequenceStep]:
    rows = await session.scalars(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .order_by(SequenceStep.position)
    )
    return list(rows.all())


async def step_counts(session: AsyncSession, sequence_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not sequence_ids:
        return {}
    rows = await session.execute(
        select(SequenceStep.sequence_id, func.count())
        .where(SequenceStep.sequence_id.in_(sequence_ids))
        .group_by(SequenceStep.sequence_id)
    )
    return {sequence_id: int(n) for sequence_id, n in rows.all()}


async def enrolment_counts(
    session: AsyncSession, sequence_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    """Enrolments per sequence by status."""
    if not sequence_ids:
        return {}
    rows = await session.execute(
        select(SequenceEnrolment.sequence_id, SequenceEnrolment.status, func.count())
        .where(SequenceEnrolment.sequence_id.in_(sequence_ids))
        .group_by(SequenceEnrolment.sequence_id, SequenceEnrolment.status)
    )
    counts: dict[uuid.UUID, dict[str, int]] = {}
    for sequence_id, status, n in rows.all():
        counts.setdefault(sequence_id, {})[status] = int(n)
    return counts


async def active_count(session: AsyncSession, *, excluding: uuid.UUID | None = None) -> int:
    query = (
        select(func.count()).select_from(Sequence).where(Sequence.status == SequenceStatus.ACTIVE)
    )
    if excluding is not None:
        query = query.where(Sequence.id != excluding)
    return int(await session.scalar(query) or 0)


async def active_for_entry(
    session: AsyncSession, account_id: uuid.UUID, entry_type: str
) -> list[Sequence]:
    rows = await session.scalars(
        select(Sequence)
        .where(
            Sequence.status == SequenceStatus.ACTIVE,
            Sequence.social_account_id == account_id,
            Sequence.entry_type == entry_type,
        )
        .order_by(Sequence.created_at, Sequence.id)
    )
    return list(rows.all())


async def first_step(session: AsyncSession, sequence_id: uuid.UUID) -> SequenceStep | None:
    return await session.scalar(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .order_by(SequenceStep.position)
        .limit(1)
    )


async def has_enrolment(
    session: AsyncSession, sequence_id: uuid.UUID, contact_id: uuid.UUID, *, active_only: bool
) -> bool:
    query = select(SequenceEnrolment.id).where(
        SequenceEnrolment.sequence_id == sequence_id, SequenceEnrolment.contact_id == contact_id
    )
    if active_only:
        query = query.where(SequenceEnrolment.status == EnrolmentStatus.ACTIVE)
    return await session.scalar(query.limit(1)) is not None


async def stop_matching(
    session: AsyncSession,
    contact_id: uuid.UUID,
    *,
    reason: str,
    detail: str | None,
    now: datetime,
    sequence_ids: Any,
) -> int:
    """Stop the contact's active enrolments in the sequences ``sequence_ids`` selects (a column
    subquery); returns how many."""
    result = await session.execute(
        scoped_update(SequenceEnrolment, contact_id=contact_id, status=EnrolmentStatus.ACTIVE)
        .where(SequenceEnrolment.sequence_id.in_(sequence_ids))
        .values(
            status=EnrolmentStatus.STOPPED,
            stop_reason=reason,
            stop_detail=detail,
            finished_at=now,
            next_due_at=None,
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def get_enrolment(
    session: AsyncSession, enrolment_id: uuid.UUID, *, lock: bool = False, skip_locked: bool = False
) -> SequenceEnrolment | None:
    query = select(SequenceEnrolment).where(SequenceEnrolment.id == enrolment_id)
    if lock:
        query = query.with_for_update(skip_locked=skip_locked).execution_options(
            populate_existing=True
        )
    return await session.scalar(query)


async def due(
    session: AsyncSession, now: datetime, limit: int
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(workspace, enrolment) of the active enrolments whose step is due, oldest first, in
    sequences that are active on accounts that can send. Call inside ``tenant_bypass_scope``."""
    rows = await session.execute(
        select(SequenceEnrolment.workspace_id, SequenceEnrolment.id)
        .join(Sequence, Sequence.id == SequenceEnrolment.sequence_id)
        .join(SocialAccount, SocialAccount.id == SequenceEnrolment.social_account_id)
        .where(
            SequenceEnrolment.status == EnrolmentStatus.ACTIVE,
            SequenceEnrolment.next_due_at <= now,
            Sequence.status == SequenceStatus.ACTIVE,
            SocialAccount.status == AccountStatus.ACTIVE,
        )
        .order_by(SequenceEnrolment.next_due_at, SequenceEnrolment.id)
        .limit(limit)
    )
    return [(workspace_id, enrolment_id) for workspace_id, enrolment_id in rows.all()]


async def step_run(
    session: AsyncSession, enrolment_id: uuid.UUID, position: int
) -> SequenceStepRun | None:
    return await session.scalar(
        select(SequenceStepRun).where(
            SequenceStepRun.enrolment_id == enrolment_id, SequenceStepRun.position == position
        )
    )


async def template_send_times(
    session: AsyncSession, account_id: uuid.UUID, since: datetime
) -> list[datetime]:
    """When sequences handed a WhatsApp template to the send queue on one number since ``since``:
    they count against the number's daily limit with broadcasts."""
    rows = await session.scalars(
        select(SequenceStepRun.ran_at).where(
            SequenceStepRun.social_account_id == account_id,
            SequenceStepRun.status == RunStatus.SENT,
            SequenceStepRun.sent_as == "template",
            SequenceStepRun.ran_at >= since,
        )
    )
    return list(rows.all())


async def stop_all_of_sequence(
    session: AsyncSession, sequence_id: uuid.UUID, *, reason: str, now: datetime
) -> int:
    result = await session.execute(
        scoped_update(
            SequenceEnrolment, sequence_id=sequence_id, status=EnrolmentStatus.ACTIVE
        ).values(
            status=EnrolmentStatus.STOPPED,
            stop_reason=reason,
            finished_at=now,
            next_due_at=None,
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def contact_of(session: AsyncSession, contact_id: uuid.UUID) -> Contact | None:
    return await session.scalar(select(Contact).where(Contact.id == contact_id))
