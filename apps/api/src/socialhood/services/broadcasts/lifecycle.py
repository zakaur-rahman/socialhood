"""A broadcast's status changes (GR-23). Nothing here commits.

draft -> scheduled or sending -> paused (by the owner, or by the product with a plain reason) ->
sending again -> completed; cancelled from any state that has not finished; failed when it could
not start. A pause records a short ``paused_code`` (``member``, ``quality``, ``limit``, ``plan``,
``account``, ``disabled``) and a sentence for the page; a pause the product made tells the
workspace's owners and admins once.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.broadcasts import Broadcast, BroadcastStatus
from socialhood.observability.logging import get_logger
from socialhood.services.notifications import notify_admins

log = get_logger(__name__)

RUNNING = (BroadcastStatus.SENDING,)
OPEN = (BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED, BroadcastStatus.PAUSED)
ACTIVE = (BroadcastStatus.SCHEDULED, BroadcastStatus.SENDING, BroadcastStatus.PAUSED)


async def pause(
    session: AsyncSession,
    broadcast: Broadcast,
    *,
    code: str,
    reason: str,
    notify: bool = True,
) -> None:
    """Pause a sending broadcast. A second pause with the same code changes nothing."""
    if broadcast.status != BroadcastStatus.SENDING:
        return
    broadcast.status = BroadcastStatus.PAUSED
    broadcast.paused_code = code
    broadcast.paused_reason = reason
    await session.flush()
    log.info("broadcast_paused", broadcast_id=str(broadcast.id), pause=code)
    if notify:
        await notify_admins(
            session,
            type="broadcast_paused",
            severity="warning",
            title=f"{broadcast.name} was paused",
            body=reason,
            link=f"/broadcasts/{broadcast.id}",
            # One notice per cause per hour: a pause, a resume and the same pause again soon after
            # is one notice, not three.
            dedupe_key=f"broadcast_paused:{broadcast.id}:{code}:{datetime.now(UTC):%Y%m%d%H}",
        )


async def pause_running_for_account(
    session: AsyncSession, account_id: uuid.UUID, *, code: str, reason: str
) -> list[uuid.UUID]:
    """Pause every sending broadcast of one number; returns their ids."""
    rows = (
        await session.scalars(
            select(Broadcast)
            .where(
                Broadcast.social_account_id == account_id,
                Broadcast.status == BroadcastStatus.SENDING,
            )
            .with_for_update()
        )
    ).all()
    for broadcast in rows:
        await pause(session, broadcast, code=code, reason=reason)
    return [b.id for b in rows]


def resume(broadcast: Broadcast) -> None:
    broadcast.status = BroadcastStatus.SENDING
    broadcast.paused_code = None
    broadcast.paused_reason = None


def complete(broadcast: Broadcast, now: datetime) -> None:
    broadcast.status = BroadcastStatus.COMPLETED
    broadcast.completed_at = now


async def fail(
    session: AsyncSession, broadcast: Broadcast, reason: str, now: datetime, code: str = "failed"
) -> None:
    """The broadcast could not start (a scheduled one finds out when its time comes)."""
    broadcast.status = BroadcastStatus.FAILED
    broadcast.paused_code = code
    broadcast.paused_reason = reason
    broadcast.completed_at = now
    await session.flush()
    await notify_admins(
        session,
        type="broadcast_paused",
        severity="warning",
        title=f"{broadcast.name} couldn't start",
        body=reason,
        link=f"/broadcasts/{broadcast.id}",
        dedupe_key=f"broadcast_failed:{broadcast.id}",
    )
