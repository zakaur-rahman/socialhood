"""Weekly posting times and the queue (FR-PUB-09, UX-SCR-14, C-043).

An account's posting times are weekly local times in the workspace time zone. A time is free when
no scheduled or publishing post of the account is within 30 minutes of it (SLOT_BUSY_WITHIN), and
usable when it is at least 5 minutes away (MIN_SCHEDULE_LEAD). A post has one ``publish_at``, so
Add to queue takes the earliest time that is a free posting time of every selected account within
8 weeks (C-043). Changing the times never moves posts already scheduled.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import MIN_SCHEDULE_LEAD, SLOT_BUSY_WITHIN
from socialhood.platforms.deps import PlatformDeps
from socialhood.repositories import scheduled_posts as repo
from socialhood.schemas.publishing import PostingSlot, PostingSlots, PostingSlotsUpdate
from socialhood.services.scheduled_posts import rules
from socialhood.services.scheduled_posts.views import can_publish

QUEUE_HORIZON = timedelta(weeks=8)  # C-043: Add to queue looks this far ahead
NEXT_FREE_COUNT = 5  # UX-SCR-14: "the next 5 free times"


def zone(name: str) -> ZoneInfo:
    """The workspace's zone; UTC when the stored name is not a known IANA zone."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def occurrences(
    slots: Sequence[tuple[int, time]], tz: ZoneInfo, *, start: datetime, end: datetime
) -> list[datetime]:
    """The instants (UTC) in [start, end) at which the weekly times fall, soonest first."""
    by_weekday: dict[int, list[time]] = defaultdict(list)
    for weekday, at in slots:
        by_weekday[weekday].append(at)
    found: set[datetime] = set()
    day = start.astimezone(tz).date() - timedelta(days=1)
    last = end.astimezone(tz).date() + timedelta(days=1)
    while day <= last:
        for at in by_weekday.get(day.weekday(), ()):
            instant = datetime.combine(day, at, tzinfo=tz).astimezone(UTC)
            if start <= instant < end:
                found.add(instant)
        day += timedelta(days=1)
    return sorted(found)


def is_free(at: datetime, busy: Sequence[datetime]) -> bool:
    return all(abs(other - at) >= SLOT_BUSY_WITHIN for other in busy)


async def free_times(
    session: AsyncSession,
    account_ids: Sequence[uuid.UUID],
    *,
    timezone: str,
    start: datetime,
    end: datetime,
    exclude_post_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, list[datetime]]:
    """Each account's free posting times in [start, end), soonest first. ``exclude_post_id``'s
    own time doesn't make a slot busy (the post being queued)."""
    tz = zone(timezone)
    weekly: dict[uuid.UUID, list[tuple[int, time]]] = defaultdict(list)
    for slot in await repo.slots_for(session, account_ids):
        weekly[slot.social_account_id].append((slot.weekday, slot.local_time))
    planned = await repo.planned(
        session,
        [a for a in account_ids if weekly.get(a)],
        start=start - SLOT_BUSY_WITHIN,
        end=end + SLOT_BUSY_WITHIN,
    )
    busy: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    for row in planned:
        if not row.published and row.scheduled_post_id != exclude_post_id:
            busy[row.social_account_id].append(row.at)
    return {
        account_id: [
            at
            for at in occurrences(weekly.get(account_id, []), tz, start=start, end=end)
            if is_free(at, busy[account_id])
        ]
        for account_id in account_ids
    }


async def next_free(
    session: AsyncSession,
    account_ids: Sequence[uuid.UUID],
    *,
    timezone: str,
    now: datetime,
    count: int = NEXT_FREE_COUNT,
) -> dict[uuid.UUID, list[datetime]]:
    """Each account's next ``count`` usable free times (Add to queue's preview)."""
    free = await free_times(
        session,
        account_ids,
        timezone=timezone,
        start=now + MIN_SCHEDULE_LEAD,
        end=now + QUEUE_HORIZON,
    )
    return {account_id: times[:count] for account_id, times in free.items()}


async def queue_time(
    session: AsyncSession,
    accounts: Sequence[SocialAccount],
    *,
    timezone: str,
    now: datetime,
    post_id: uuid.UUID,
) -> datetime:
    """Add to queue: the earliest time within 8 weeks that is a free posting time of every
    account (C-043). 422 on ``targets`` without accounts or without a shared free time, on
    ``targets.{i}`` for an account without posting times."""
    if not accounts:
        raise ApiError(
            "validation_error", errors=[FieldError("targets", "Choose at least one account.")]
        )
    ids = [a.id for a in accounts]
    with_slots = {s.social_account_id for s in await repo.slots_for(session, ids)}
    missing = [
        FieldError(
            f"targets.{i}",
            f"Add posting times for {rules.handle(a.username, a.display_name)} first.",
        )
        for i, a in enumerate(accounts)
        if a.id not in with_slots
    ]
    if missing:
        raise ApiError("validation_error", errors=missing)
    free = await free_times(
        session,
        ids,
        timezone=timezone,
        start=now + MIN_SCHEDULE_LEAD,
        end=now + QUEUE_HORIZON,
        exclude_post_id=post_id,
    )
    others = [set(free[a]) for a in ids[1:]]
    for at in free[ids[0]]:
        if all(at in times for times in others):
            return at
    message = (
        "There's no free posting time in the next 8 weeks. Add posting times or pick a time."
        if len(ids) == 1
        else "These accounts share no free posting time in the next 8 weeks. Pick a time instead."
    )
    raise ApiError("validation_error", errors=[FieldError("targets", message)])


# ---------------------------------------------------------------- the routes' work


async def _account_or_404(session: AsyncSession, account_id: uuid.UUID) -> SocialAccount:
    account = (await repo.accounts_by_id(session, [account_id])).get(account_id)
    if account is None:
        raise ApiError("not_found")
    return account


async def posting_slots(
    session: AsyncSession, account_id: uuid.UUID, *, timezone: str, now: datetime
) -> PostingSlots:
    """GET …/posting-slots: the weekly times and the next 5 free times (UX-SCR-14)."""
    await _account_or_404(session, account_id)
    slots = await repo.slots_for(session, [account_id])
    upcoming = await next_free(session, [account_id], timezone=timezone, now=now)
    return PostingSlots(
        social_account_id=account_id,
        timezone=zone(timezone).key,
        slots=[PostingSlot(weekday=s.weekday, local_time=s.local_time) for s in slots],
        next_free_at=upcoming[account_id],
    )


async def replace_posting_slots(
    session: AsyncSession,
    account_id: uuid.UUID,
    body: PostingSlotsUpdate,
    *,
    deps: PlatformDeps,
    timezone: str,
    now: datetime,
) -> PostingSlots:
    """PUT …/posting-slots: the account's weekly times become the body's (duplicates collapse).
    409 capability_unavailable for an account that can't publish; 422 on
    ``slots.{i}.local_time`` for a time with seconds or a time zone."""
    account = await _account_or_404(session, account_id)
    if not can_publish(account, deps):
        raise ApiError("capability_unavailable", "This account can't publish posts.")
    errors = [
        FieldError(f"slots.{i}.local_time", "Use a time in whole minutes, like 18:00.")
        for i, slot in enumerate(body.slots)
        if slot.local_time.second or slot.local_time.microsecond or slot.local_time.tzinfo
    ]
    if errors:
        raise ApiError("validation_error", errors=errors)
    await repo.replace_slots(
        session, account_id, [(slot.weekday, slot.local_time) for slot in body.slots]
    )
    return await posting_slots(session, account_id, timezone=timezone, now=now)
