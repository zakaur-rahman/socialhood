"""When a sequence step is due (GR-24). Pure: the clock and the schedule are passed in.

A step waits ``delay_seconds`` from the contact's entry (``entry``) or from when the step before
it ran, sent or skipped (``previous``). The first step always counts from entry. A step that is
held to business hours waits for the next opening: ``next_open_at``.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from socialhood.services.business_hours import Hours, is_open, zone_of

LOOK_AHEAD_DAYS = 8


def due_at(
    *,
    delay_seconds: int,
    delay_from: str,
    position: int,
    enrolled_at: datetime,
    previous_ran_at: datetime,
) -> datetime:
    """When the step at ``position`` is due."""
    anchor = enrolled_at if position == 0 or delay_from == "entry" else previous_ran_at
    return anchor + timedelta(seconds=delay_seconds)


def next_open_at(hours: Hours, at: datetime) -> datetime | None:
    """``at`` if the schedule is open then, else the start of the next open range within
    ``LOOK_AHEAD_DAYS`` days; None if it never opens in that time."""
    if is_open(hours, at):
        return at
    zone = zone_of(hours.timezone)
    local = (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(zone)
    candidates: list[datetime] = []
    for ahead in range(LOOK_AHEAD_DAYS + 1):
        day = local.date() + timedelta(days=ahead)
        for start, _ in hours.days[day.weekday()]:
            opens = datetime.combine(day, time(start // 60, start % 60), tzinfo=zone)
            if opens > local:
                candidates.append(opens)
    return min(candidates).astimezone(UTC) if candidates else None
