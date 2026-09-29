"""The content calendar (FR-PUB-08, FR-PUB-09, FR-SMS-02, UX-SCR-04; C-043).

``from`` and ``to`` are dates in the workspace time zone, both included, at most 42 days. Layers:
posts with a time in the range (drafts with a time included, drawn muted), scheduled DMs sending in
the range (canceled ones left out) and free posting times from now to the end of the range. The
``accounts`` block feeds the right rail: posts published in the last 24 hours against the
publishing limit, and the next free posting time. ``account_ids`` narrows every part.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.publishing import CALENDAR_MAX_DAYS, MIN_SCHEDULE_LEAD
from socialhood.platforms.deps import PlatformDeps
from socialhood.repositories import scheduled_posts as repo
from socialhood.repositories import social_accounts
from socialhood.repositories.scheduled import ScheduledRow
from socialhood.schemas.publishing import (
    Calendar,
    CalendarAccount,
    CalendarLayer,
    CalendarMessage,
    CalendarSlot,
)
from socialhood.services.scheduled import scheduled_out
from socialhood.services.scheduled_posts import slots, views

ALL_LAYERS: tuple[CalendarLayer, ...] = ("posts", "messages", "slots")
MAX_POSTS = 1000  # a busy six weeks; more than any grid can show
MAX_MESSAGES = 1000
DAY = timedelta(hours=24)


def _range(start: date, end: date) -> None:
    if end < start:
        raise ApiError(
            "validation_error",
            errors=[FieldError("to", "Pick an end date on or after the start date.")],
        )
    if (end - start).days + 1 > CALENDAR_MAX_DAYS:
        raise ApiError(
            "validation_error",
            errors=[FieldError("to", f"Show at most {CALENDAR_MAX_DAYS} days at a time.")],
        )


def _publishing_accounts(
    accounts: Sequence[SocialAccount],
    account_ids: Sequence[uuid.UUID] | None,
    deps: PlatformDeps,
) -> list[SocialAccount]:
    """Connected accounts that can publish, narrowed to ``account_ids`` when given."""
    wanted = set(account_ids or [])
    return [
        a
        for a in accounts
        if a.status != AccountStatus.DISCONNECTED
        and views.can_publish(a, deps)
        and (not wanted or a.id in wanted)
    ]


async def calendar(
    session: AsyncSession,
    *,
    start_day: date,
    end_day: date,
    account_ids: Sequence[uuid.UUID] | None,
    layers: Sequence[CalendarLayer] | None,
    deps: PlatformDeps,
    timezone: str,
    now: datetime,
) -> Calendar:
    _range(start_day, end_day)
    tz = slots.zone(timezone)
    start = datetime.combine(start_day, time(0), tzinfo=tz)
    end = datetime.combine(end_day + timedelta(days=1), time(0), tzinfo=tz)
    wanted = set(layers or ALL_LAYERS)
    accounts = _publishing_accounts(await social_accounts.list_all(session), account_ids, deps)
    ids = [a.id for a in accounts]

    posts = []
    if "posts" in wanted:
        rows = await repo.in_range(
            session, start=start, end=end, account_ids=account_ids, limit=MAX_POSTS
        )
        posts = await views.summaries(session, rows)

    messages = []
    if "messages" in wanted:
        for row in await repo.scheduled_messages(
            session, start=start, end=end, account_ids=account_ids, limit=MAX_MESSAGES
        ):
            out = scheduled_out(ScheduledRow(row.scheduled, row.platform, row.contact))
            messages.append(
                CalendarMessage(**out.model_dump(), social_account_id=row.social_account_id)
            )

    free_slots: list[CalendarSlot] = []
    if "slots" in wanted and end > now + MIN_SCHEDULE_LEAD:
        free = await slots.free_times(
            session,
            ids,
            timezone=timezone,
            start=max(start, now + MIN_SCHEDULE_LEAD),
            end=end,
        )
        order = {account_id: i for i, account_id in enumerate(ids)}
        free_slots = sorted(
            (
                CalendarSlot(social_account_id=account_id, at=at)
                for account_id, times in free.items()
                for at in times
            ),
            key=lambda s: (s.at, order[s.social_account_id]),
        )

    published = await repo.published_counts(session, ids, since=now - DAY)
    upcoming = await slots.next_free(session, ids, timezone=timezone, now=now, count=1)
    return Calendar(
        timezone=tz.key,
        start=start_day,
        end=end_day,
        posts=posts,
        messages=messages,
        slots=free_slots,
        accounts=[
            CalendarAccount(
                social_account_id=a.id,
                published_24h=published.get(a.id, 0),
                publishing_limit=views.PUBLISHING_LIMIT,
                next_free_at=next(iter(upcoming.get(a.id, [])), None),
            )
            for a in accounts
        ],
    )
