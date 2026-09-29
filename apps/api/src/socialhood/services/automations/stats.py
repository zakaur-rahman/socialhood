"""Automation figures (T4.3; FR-AUT-03, FR-AUT-10, FR-AUT-16; UX-SCR-02, UX-SCR-12), all read
from automation_runs so they agree with the run log.

- runs: every firing in the period, whatever its result (the run log lists them all).
- DMs sent: runs whose private reply (or DM) message reached the platform (sent, delivered, read).
- public replies: runs that posted a public reply.
- replied within 24 h: runs whose contact wrote back within 24 hours of the DM
  (``contact_replied_at``, set by ingest).
- failures: runs where the DM or the public reply failed (failed, partial).
- skipped: by reason; the runtime never loads automations outside their run window, so
  "outside window" has no runs and stays 0.
- queued now: runs waiting in the account's private-reply queue (TR-JOB-07).

Days are the workspace's calendar days, oldest first, the last one being today.

The queue ETA is waiting ÷ 750 per hour over the whole account queue (FR-AUT-10). The runtime's
private-reply queue (T4.6) owns that figure; ``queued_counts`` computes it here the same way.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import ColumnElement, Date, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import Automation, AutomationRun, AutomationStatus, RunResult
from socialhood.models.inbox import Message
from socialhood.schemas.automations import (
    AutomationListStats,
    AutomationsSummary,
    AutomationStats,
    DailyRuns,
    QueueInfo,
    SkippedCounts,
    SurgeOrderName,
)

PRIVATE_REPLIES_PER_HOUR = 750  # Instagram's cap per account (FR-AUT-10)
LIST_DAYS = 7
SENT_STATUSES = ("sent", "delivered", "read")
FAILED_RESULTS = (RunResult.FAILED, RunResult.PARTIAL)
_ZONE_KEY = re.compile(r"[A-Za-z0-9_+\-]+(?:/[A-Za-z0-9_+\-]+)*")


def eta_minutes(waiting: int) -> int | None:
    """Minutes until ``waiting`` private replies are sent at 750 per hour; None when none wait."""
    if waiting <= 0:
        return None
    return math.ceil(waiting * 60 / PRIVATE_REPLIES_PER_HOUR)


@dataclass(frozen=True)
class Period:
    days: list[date]  # oldest first; the last is today in the workspace's timezone
    since: datetime  # the first day's start, in UTC
    timezone: str


def period(timezone: str, days: int, now: datetime) -> Period:
    try:
        zone = ZoneInfo(timezone) if _ZONE_KEY.fullmatch(timezone) else None
    except (ZoneInfoNotFoundError, ValueError):
        zone = None
    if zone is None:
        zone, timezone = ZoneInfo("UTC"), "UTC"
    today = now.astimezone(zone).date()
    first = today - timedelta(days=days - 1)
    since = datetime.combine(first, time.min, tzinfo=zone).astimezone(UTC)
    return Period([first + timedelta(days=i) for i in range(days)], since, timezone)


def _local_day(p: Period) -> ColumnElement[date]:
    """The run's calendar day in the workspace's timezone. The zone is written into the SQL (a
    checked IANA key) so the grouped and selected expressions are identical."""
    zone: ColumnElement[str] = literal_column(f"'{p.timezone}'")
    return cast(func.timezone(zone, AutomationRun.created_at), Date)


# ---------------------------------------------------------------- the private-reply queue


@dataclass
class QueueCounts:
    by_automation: dict[uuid.UUID, int] = field(default_factory=dict)
    by_account: dict[uuid.UUID, int] = field(default_factory=dict)

    def info(self, automation: Automation) -> QueueInfo:
        waiting = self.by_automation.get(automation.id, 0)
        account_waiting = (
            self.by_account.get(automation.social_account_id, 0)
            if automation.social_account_id
            else 0
        )
        order: SurgeOrderName = automation.surge_order  # type: ignore[assignment]
        return QueueInfo(
            waiting=waiting,
            eta_minutes=eta_minutes(max(account_waiting, waiting)) if waiting else None,
            order=order,
        )

    @property
    def total(self) -> int:
        return sum(self.by_account.values())

    @property
    def longest_eta_minutes(self) -> int | None:
        return eta_minutes(max(self.by_account.values(), default=0))


async def queued_counts(session: AsyncSession) -> QueueCounts:
    """Queued runs per automation and per account, for the whole workspace."""
    rows = await session.execute(
        select(AutomationRun.automation_id, Automation.social_account_id, func.count())
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .where(AutomationRun.result == RunResult.QUEUED)
        .group_by(AutomationRun.automation_id, Automation.social_account_id)
    )
    counts = QueueCounts()
    for automation_id, account_id, count in rows.all():
        counts.by_automation[automation_id] = int(count)
        if account_id is not None:
            counts.by_account[account_id] = counts.by_account.get(account_id, 0) + int(count)
    return counts


# ---------------------------------------------------------------- the list (FR-AUT-03)


async def list_stats(
    session: AsyncSession, automations: Sequence[Automation], *, timezone: str, now: datetime
) -> dict[uuid.UUID, AutomationListStats]:
    """Runs in the last 7 days, per day (oldest first), and the time of the last run."""
    p = period(timezone, LIST_DAYS, now)
    ids = [a.id for a in automations]
    daily: dict[uuid.UUID, dict[date, int]] = defaultdict(dict)
    last: dict[uuid.UUID, datetime] = {}
    if ids:
        day = _local_day(p)
        rows = await session.execute(
            select(AutomationRun.automation_id, day, func.count())
            .where(AutomationRun.automation_id.in_(ids), AutomationRun.created_at >= p.since)
            .group_by(AutomationRun.automation_id, day)
        )
        for automation_id, on, count in rows.all():
            daily[automation_id][on] = int(count)
        latest = await session.execute(
            select(AutomationRun.automation_id, func.max(AutomationRun.created_at))
            .where(AutomationRun.automation_id.in_(ids))
            .group_by(AutomationRun.automation_id)
        )
        last = {automation_id: at for automation_id, at in latest.all() if at}
    out: dict[uuid.UUID, AutomationListStats] = {}
    for a in automations:
        series = [daily[a.id].get(d, 0) for d in p.days]
        times = [t for t in (a.last_run_at, last.get(a.id)) if t is not None]
        out[a.id] = AutomationListStats(
            runs_7d=sum(series), daily_7d=series, last_run_at=max(times) if times else None
        )
    return out


# ---------------------------------------------------------------- one automation (FR-AUT-16)


async def automation_stats(
    session: AsyncSession,
    automation: Automation,
    *,
    days: Literal[7, 30],
    timezone: str,
    now: datetime,
) -> AutomationStats:
    p = period(timezone, days, now)
    run = AutomationRun
    in_period = (run.automation_id == automation.id, run.created_at >= p.since)
    totals = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(Message.status.in_(SENT_STATUSES)),
                func.count().filter(run.public_reply_platform_id.is_not(None)),
                func.count().filter(run.contact_replied_at.is_not(None)),
                func.count().filter(run.result.in_(FAILED_RESULTS)),
                func.count().filter(run.result == RunResult.SKIPPED_COOLDOWN),
                func.count().filter(run.result == RunResult.SKIPPED_EXPIRED),
            )
            .select_from(run)
            .outerjoin(Message, Message.id == run.private_reply_message_id)
            .where(*in_period)
        )
    ).one()
    runs, dms, public, replied, failures, cooldown, expired = (int(v or 0) for v in totals)
    day = _local_day(p)
    per_day = await session.execute(
        select(day, func.count(), func.count().filter(run.result.in_(FAILED_RESULTS)))
        .where(*in_period)
        .group_by(day)
    )
    by_day = {on: (int(n), int(f)) for on, n, f in per_day.all()}
    queued = await session.scalar(
        select(func.count())
        .select_from(run)
        .where(run.automation_id == automation.id, run.result == RunResult.QUEUED)
    )
    return AutomationStats(
        days=days,
        runs=runs,
        dms_sent=dms,
        public_replies=public,
        replied_24h=replied,
        failures=failures,
        skipped=SkippedCounts(cooldown=cooldown, expired=expired, outside_window=0),
        queued_now=int(queued or 0),
        daily=[
            DailyRuns(date=d, runs=by_day.get(d, (0, 0))[0], failures=by_day.get(d, (0, 0))[1])
            for d in p.days
        ],
    )


# ---------------------------------------------------------------- the figures strip (UX-SCR-02)


async def summary(session: AsyncSession, *, timezone: str, now: datetime) -> AutomationsSummary:
    p = period(timezone, LIST_DAYS, now)
    active = await session.scalar(
        select(func.count())
        .select_from(Automation)
        .where(Automation.status == AutomationStatus.ACTIVE)
    )
    runs, dms = (
        await session.execute(
            select(func.count(), func.count().filter(Message.status.in_(SENT_STATUSES)))
            .select_from(AutomationRun)
            .outerjoin(Message, Message.id == AutomationRun.private_reply_message_id)
            .where(AutomationRun.created_at >= p.since)
        )
    ).one()
    queue = await queued_counts(session)
    return AutomationsSummary(
        active=int(active or 0),
        runs_7d=int(runs or 0),
        dms_sent_7d=int(dms or 0),
        waiting=queue.total,
        longest_eta_minutes=queue.longest_eta_minutes,
    )
