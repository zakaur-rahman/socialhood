"""Browsers' Web Push subscriptions (push_subscriptions; §5.3, TR-FE-09, T8.6). User-scoped, not
tenant: every query here names the user, so a caller only ever touches its own devices."""

from __future__ import annotations

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import DateTime, case, delete, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.notifications import PushSubscription


async def upsert(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None,
) -> PushSubscription:
    """Register a browser, or refresh it: the endpoint is unique, so registering it again takes
    the new keys, clears its failures and disabled state, and gives it to ``user_id`` (the
    browser now belongs to whoever signed in on it)."""
    statement = (
        insert(PushSubscription)
        .values(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth, user_agent=user_agent)
        .on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            set_={
                "user_id": user_id,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": user_agent,
                "failure_count": 0,
                "disabled_at": None,
                "updated_at": func.now(),
            },
        )
        .returning(PushSubscription)
    )
    row: PushSubscription = (
        await session.scalars(statement, execution_options={"populate_existing": True})
    ).one()
    return row


async def trim(session: AsyncSession, user_id: uuid.UUID, *, keep: int) -> int:
    """Keep the user's ``keep`` most recently used browsers; delete the rest."""
    recent = (
        select(PushSubscription.id)
        .where(PushSubscription.user_id == user_id)
        .order_by(
            func.coalesce(PushSubscription.last_used_at, PushSubscription.updated_at).desc(),
            PushSubscription.id,
        )
        .limit(keep)
    )
    result = await session.execute(
        delete(PushSubscription)
        .where(PushSubscription.user_id == user_id, PushSubscription.id.not_in(recent))
        .returning(PushSubscription.id)
    )
    return len(result.all())


async def delete_for_user(session: AsyncSession, *, user_id: uuid.UUID, endpoint: str) -> bool:
    result = await session.execute(
        delete(PushSubscription)
        .where(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint)
        .returning(PushSubscription.id)
    )
    return result.first() is not None


async def enabled_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[PushSubscription]:
    return list(
        (
            await session.scalars(
                select(PushSubscription)
                .where(PushSubscription.user_id == user_id, PushSubscription.disabled_at.is_(None))
                .order_by(PushSubscription.created_at)
            )
        ).all()
    )


async def users_with_devices(
    session: AsyncSession, user_ids: Collection[uuid.UUID]
) -> set[uuid.UUID]:
    """Which of these users have at least one enabled browser."""
    if not user_ids:
        return set()
    rows = await session.scalars(
        select(PushSubscription.user_id)
        .where(PushSubscription.user_id.in_(list(user_ids)), PushSubscription.disabled_at.is_(None))
        .distinct()
    )
    return set(rows.all())


async def record_success(session: AsyncSession, ids: Collection[uuid.UUID], at: datetime) -> None:
    if ids:
        await session.execute(
            update(PushSubscription)
            .where(PushSubscription.id.in_(list(ids)))
            .values(failure_count=0, last_used_at=at)
        )


async def record_failure(
    session: AsyncSession, ids: Collection[uuid.UUID], at: datetime, *, disable_at: int
) -> list[uuid.UUID]:
    """One more failure each; a row reaching ``disable_at`` failures in a row is disabled.
    Returns the rows disabled now."""
    if not ids:
        return []
    count = PushSubscription.failure_count + 1
    result = await session.execute(
        update(PushSubscription)
        .where(PushSubscription.id.in_(list(ids)), PushSubscription.disabled_at.is_(None))
        .values(
            failure_count=count,
            disabled_at=case((count >= disable_at, literal(at, DateTime(timezone=True)))),
        )
        .returning(PushSubscription.id, PushSubscription.disabled_at)
    )
    return [row.id for row in result if row.disabled_at is not None]


async def delete_gone(session: AsyncSession, ids: Collection[uuid.UUID]) -> None:
    """The push service answered 404 or 410: the browser dropped the subscription."""
    if ids:
        await session.execute(delete(PushSubscription).where(PushSubscription.id.in_(list(ids))))
