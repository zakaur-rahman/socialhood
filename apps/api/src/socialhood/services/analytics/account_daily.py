"""Daily account metrics (T6.5; FR-ANL-01): what snapshot_account_day does for one account and day.

One account_daily_metrics row per account per day, the day being the workspace's calendar day.
Instagram keeps account insights for 90 days only, so these rows are the long-term history.

- The hourly snapshot_account_daily tick queues yesterday's row for each account once it is
  02:00 or later in the workspace time zone and the row is missing (the job catalogue's "02:00
  in the workspace timezone", catching up after downtime).
- The row holds followers_count read now (from the account fields; the only reliable follower
  history, known without the insights scope) and, with Capability.ACCOUNT_INSIGHTS, that day's
  account insights ({} without it).
- Account insights lag up to 48 h, and unlike post insights they can be read for a past day. So
  the run that writes day D also re-reads day D-2's insights and updates that row (its followers
  stay as read). Values Instagram does not return this time keep their earlier reading.

Captured once: the row is inserted with ON CONFLICT DO NOTHING, and the D-2 re-read happens only
in the run that wrote D, so a re-run or a second worker changes nothing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.analytics import AccountDailyMetric
from socialhood.models.identity import Workspace
from socialhood.observability.logging import get_logger
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.repositories import analytics as repo
from socialhood.services.analytics.common import zone
from socialhood.services.analytics.snapshots import measured_account

log = get_logger(__name__)

DAILY_AT = time(2, 0)  # the local time a day's row becomes due (job catalogue)
SETTLE_AFTER_DAYS = 2  # Instagram's insights lag up to 48 h


def due_day(timezone: str, now: datetime) -> date:
    """The latest local day whose row is due now: yesterday from 02:00 local, else the day
    before."""
    local = now.astimezone(zone(timezone))
    shifted = datetime.combine(local.date(), local.time()) - timedelta(
        hours=DAILY_AT.hour, minutes=DAILY_AT.minute
    )
    return shifted.date() - timedelta(days=1)


async def _stored(
    session: AsyncSession, account_id: uuid.UUID, day: date
) -> AccountDailyMetric | None:
    return (
        await session.scalars(
            select(AccountDailyMetric).where(
                AccountDailyMetric.social_account_id == account_id, AccountDailyMetric.date == day
            )
        )
    ).one_or_none()


async def snapshot_account_day(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    day: date,
    now: datetime | None = None,
) -> bool | None:
    """Write the account's row for ``day``. True when written, False when it already existed,
    None when the account has nothing to measure or the platform refused it."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        loaded = await measured_account(sessionmaker, deps, account_id)
        if loaded is None:
            return None
        acct, adapter = loaded
        async with sessionmaker() as session:
            workspace = await session.get(Workspace, workspace_id)
            existing = await _stored(session, acct.id, day)
        if existing is not None:
            return False
        tz = zone(workspace.timezone if workspace else "UTC").key
        with_insights = Capability.ACCOUNT_INSIGHTS in adapter.capabilities_for(acct)
        try:
            read = await adapter.get_account_insights(acct, day, tz=tz)
        except PlatformError as error:
            if error.retryable:
                raise
            log.warning("account_day_skipped", account_id=str(acct.id), error_code=error.code)
            return None
        async with sessionmaker() as session:
            inserted = await repo.insert_account_day(
                session,
                social_account_id=acct.id,
                day=day,
                followers_count=read.followers_count,
                metrics=read.metrics() if with_insights else {},
                captured_at=now,
            )
            await session.commit()
        if inserted and with_insights:
            await _settle(sessionmaker, deps, acct.id, day - timedelta(days=SETTLE_AFTER_DAYS), tz)
    log.info("account_day", account_id=str(account_id), day=day.isoformat(), written=inserted)
    return inserted


async def _settle(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    account_id: uuid.UUID,
    day: date,
    tz: str,
) -> None:
    """Re-read a stored day's insights once the lag has passed (best effort: a failure keeps the
    first reading)."""
    loaded = await measured_account(sessionmaker, deps, account_id)
    async with sessionmaker() as session:
        row = await _stored(session, account_id, day)
    if loaded is None or row is None:
        return
    acct, adapter = loaded
    try:
        read = await adapter.get_account_insights(acct, day, tz=tz)
    except PlatformError as error:
        log.info("account_day_settle_failed", account_id=str(account_id), error_code=error.code)
        return
    settled = {**row.metrics, **read.metrics()}
    if settled != row.metrics:
        async with sessionmaker() as session:
            await repo.set_account_day_metrics(session, account_id, day, settled)
            await session.commit()
