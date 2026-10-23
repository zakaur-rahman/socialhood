"""Business hours and away messages (GR-22).

The pure part (no database; ``at`` is passed in):
- ``Hours`` is a weekly schedule in a time zone: for each weekday (Monday 0) the open ranges, in
  minutes after midnight. A range runs from its start up to, not including, its end; ``end`` may
  be 24:00. Times are wall-clock in the zone, so 09:00 stays 09:00 across a daylight saving
  change.
- ``is_open(hours, at)`` says whether ``at`` falls in a range; ``closed_since(hours, at)`` is when
  the current closed window began (the end of the last range before ``at``, with ranges that
  touch, like 09:00 to 17:00 then 17:00 to 24:00 then 00:00 to 02:00 the next day, counted as
  one), or None while open. A schedule never open in the last week gives the earliest time.

Rules:
- A workspace has one schedule; an account may have its own, which replaces the workspace's for
  that account (``enabled`` off on the account's row: it has no hours and is always open). No
  schedule, or one that is off, means always open: nothing below changes today's behaviour.
- Ranges can't overlap on a day (touching is fine), can't cross midnight, and an enabled schedule
  needs at least one range.
- **Auto mode** (``auto_mode``): ``always`` is today's behaviour. ``out_of_hours`` makes the
  auto-reply policy (ai/policy, check 1) skip while the account is open, so the suggestion is left
  for a person.
- **Away message:** a customer DM that no automation answered, while the account is closed, gets
  the away message once per closed window (``conversations.away_sent_at`` is compared with
  ``closed_since``). It is skipped for a conversation the AI will answer in Auto mode, and for
  messages that are not a person writing: a story mention or like, a button or quick reply tap.
  It is sent as an automation message with the automation disclosure line, filled like a saved
  reply.
- **Automations** may require ``inside`` or ``outside`` hours (``automations.hours_condition``);
  an account with no hours is always inside.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.identity import Workspace
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.models.replies import AutoMode, BusinessHours
from socialhood.schemas.business_hours import (
    AccountBusinessHours,
    AutoModeName,
    BusinessHoursOverview,
    BusinessHoursUpdate,
    DaySchedule,
)
from socialhood.schemas.business_hours import BusinessHours as BusinessHoursOut
from socialhood.services import saved_replies

if TYPE_CHECKING:
    from socialhood.platforms.deps import PlatformDeps

MINUTES_PER_DAY = 1440
LOOKBACK_DAYS = 8  # a week of ranges, and the day before it
NEVER = datetime.min.replace(tzinfo=UTC)
MAX_RANGES = 6

COPY = {
    "start_midnight": "An opening time can't be 24:00. Use 00:00.",
    "order": "Closing time must be after opening time.",
    "overlap": "This overlaps another range on the same day.",
    "twice": "This day is listed twice.",
    "none": "Add at least one opening time, or turn business hours off.",
    "away": "Write the message to send when you're closed.",
}


@dataclass(frozen=True)
class Hours:
    timezone: str
    # Monday first; each day's (start, end) minutes after midnight, sorted, end up to 1440.
    days: tuple[tuple[tuple[int, int], ...], ...]


def zone_of(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def minutes_of(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def text_of(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hours_from_schedule(schedule: Sequence[object], timezone: str) -> Hours:
    """The stored schedule (a list of {day, ranges}) as ``Hours``."""
    days: list[list[tuple[int, int]]] = [[] for _ in range(7)]
    for entry in schedule:
        parsed = DaySchedule.model_validate(entry)
        days[parsed.day] = sorted((minutes_of(r.start), minutes_of(r.end)) for r in parsed.ranges)
    return Hours(timezone, tuple(tuple(day) for day in days))


def is_open(hours: Hours, at: datetime) -> bool:
    """Whether ``at`` is inside an open range, by the wall clock in the schedule's zone."""
    local = _local(hours, at)
    minute = local.hour * 60 + local.minute
    return any(start <= minute < end for start, end in hours.days[local.weekday()])


def closed_since(hours: Hours, at: datetime) -> datetime | None:
    """When the closed window ``at`` is in began, or None while open (see the module docstring)."""
    if is_open(hours, at):
        return None
    zone = zone_of(hours.timezone)
    local = _local(hours, at).replace(tzinfo=None)
    spans: list[tuple[datetime, datetime]] = []
    for back in range(LOOKBACK_DAYS, -1, -1):
        day = local.date() - timedelta(days=back)
        midnight = datetime.combine(day, time.min)
        spans += [
            (midnight + timedelta(minutes=start), midnight + timedelta(minutes=end))
            for start, end in hours.days[day.weekday()]
        ]
    ends = [end for end in _merged(sorted(spans)) if end <= local]
    return max(ends).replace(tzinfo=zone).astimezone(UTC) if ends else NEVER


def _merged(spans: list[tuple[datetime, datetime]]) -> list[datetime]:
    """The end of each run of ranges that touch or overlap."""
    ends: list[datetime] = []
    current_end: datetime | None = None
    for start, end in spans:
        if current_end is not None and start <= current_end:
            current_end = max(current_end, end)
            continue
        if current_end is not None:
            ends.append(current_end)
        current_end = end
    if current_end is not None:
        ends.append(current_end)
    return ends


def _local(hours: Hours, at: datetime) -> datetime:
    return (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(zone_of(hours.timezone))


def check(update: BusinessHoursUpdate) -> list[FieldError]:
    """Each problem with a schedule, by field, so the form can mark it."""
    errors: list[FieldError] = []
    seen: set[int] = set()
    ranges = 0
    for i, day in enumerate(update.days):
        if day.day in seen:
            errors.append(FieldError(f"days.{i}.day", COPY["twice"]))
        seen.add(day.day)
        spans: list[tuple[int, int, int]] = []
        for r, span in enumerate(day.ranges):
            start, end = minutes_of(span.start), minutes_of(span.end)
            where = f"days.{i}.ranges.{r}"
            if start >= MINUTES_PER_DAY:
                errors.append(FieldError(f"{where}.start", COPY["start_midnight"]))
            elif end <= start:
                errors.append(FieldError(f"{where}.end", COPY["order"]))
            else:
                spans.append((start, end, r))
        spans.sort()
        for (_, end, _), (start, _, r) in pairwise(spans):
            if start < end:
                errors.append(FieldError(f"days.{i}.ranges.{r}.start", COPY["overlap"]))
        ranges += len(day.ranges)
    if update.enabled and ranges == 0 and not errors:
        errors.append(FieldError("days", COPY["none"]))
    if update.away_enabled and not (update.away_message or "").strip():
        errors.append(FieldError("away_message", COPY["away"]))
    return errors


def _stored(update: BusinessHoursUpdate) -> list[dict[str, object]]:
    """The schedule as stored: only days with ranges, in week order, ranges in time order."""
    out: list[dict[str, object]] = []
    for day in sorted(update.days, key=lambda d: d.day):
        if day.ranges:
            ordered = sorted(day.ranges, key=lambda r: minutes_of(r.start))
            out.append(
                {"day": day.day, "ranges": [{"start": r.start, "end": r.end} for r in ordered]}
            )
    return out


def _days_out(schedule: Sequence[object]) -> list[DaySchedule]:
    by_day = {d.day: d for d in (DaySchedule.model_validate(e) for e in schedule)}
    return [by_day.get(day) or DaySchedule(day=day, ranges=[]) for day in range(7)]


# ---------------------------------------------------------------- the stored settings


async def workspace_zone(session: AsyncSession) -> str:
    name = await session.scalar(
        select(Workspace.timezone).where(Workspace.id == require_workspace())
    )
    return name or "UTC"


@dataclass(frozen=True)
class Active:
    """The schedule that applies to an account and the settings stored with it."""

    row: BusinessHours
    hours: Hours


async def active(session: AsyncSession, account_id: uuid.UUID) -> Active | None:
    """The account's own schedule, else the workspace's; None when it has none or it is off."""
    rows = (
        await session.scalars(
            select(BusinessHours).where(
                or_(
                    BusinessHours.social_account_id == account_id,
                    BusinessHours.social_account_id.is_(None),
                )
            )
        )
    ).all()
    row = next((r for r in rows if r.social_account_id == account_id), None) or next(
        (r for r in rows if r.social_account_id is None), None
    )
    if row is None or not row.enabled:
        return None
    return Active(row, hours_from_schedule(row.schedule or [], await workspace_zone(session)))


async def is_open_now(session: AsyncSession, account_id: uuid.UUID, at: datetime) -> bool:
    """Whether the account is open at ``at``; true when it has no hours."""
    found = await active(session, account_id)
    return True if found is None else is_open(found.hours, at)


async def auto_blocked(session: AsyncSession, account_id: uuid.UUID, at: datetime) -> bool:
    """Whether the account's hours keep Auto mode quiet right now: its Auto setting is "only out
    of hours" and it is open."""
    found = await active(session, account_id)
    return (
        found is not None
        and found.row.auto_mode == AutoMode.OUT_OF_HOURS
        and is_open(found.hours, at)
    )


async def away_possible(session: AsyncSession, account_id: uuid.UUID) -> bool:
    """A cheap pre-check for the runtime: some schedule with an away message could apply."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    BusinessHours.enabled.is_(True),
                    BusinessHours.away_enabled.is_(True),
                    or_(
                        BusinessHours.social_account_id == account_id,
                        BusinessHours.social_account_id.is_(None),
                    ),
                )
            )
        )
    )


# ---------------------------------------------------------------- the API


def _view(
    row: BusinessHours | None, timezone: str, at: datetime, account_id: uuid.UUID | None
) -> BusinessHoursOut:
    if row is None:
        return BusinessHoursOut(
            social_account_id=account_id,
            configured=False,
            enabled=False,
            days=_days_out([]),
            away_enabled=False,
            auto_mode="always",
        )
    return BusinessHoursOut(
        social_account_id=row.social_account_id,
        configured=True,
        enabled=row.enabled,
        days=_days_out(row.schedule or []),
        away_enabled=row.away_enabled,
        away_message=row.away_message,
        auto_mode=cast(AutoModeName, row.auto_mode),
        open_now=is_open(hours_from_schedule(row.schedule or [], timezone), at)
        if row.enabled
        else None,
    )


async def overview(session: AsyncSession, *, now: datetime) -> BusinessHoursOverview:
    zone = await workspace_zone(session)
    rows = (await session.scalars(select(BusinessHours))).all()
    workspace = next((r for r in rows if r.social_account_id is None), None)
    own = {r.social_account_id: r for r in rows if r.social_account_id is not None}
    accounts = (
        await session.scalars(
            select(SocialAccount)
            .where(SocialAccount.status != AccountStatus.DISCONNECTED)
            .order_by(SocialAccount.platform, SocialAccount.created_at)
        )
    ).all()
    return BusinessHoursOverview(
        timezone=zone,
        workspace=_view(workspace, zone, now, None),
        accounts=[
            AccountBusinessHours(
                social_account_id=a.id,
                platform=a.platform,
                username=a.username,
                display_name=a.display_name,
                override=_view(own[a.id], zone, now, a.id) if a.id in own else None,
            )
            for a in accounts
        ],
    )


async def save(
    session: AsyncSession,
    update: BusinessHoursUpdate,
    *,
    account_id: uuid.UUID | None,
    now: datetime,
) -> BusinessHoursOut:
    """Replace the workspace's schedule, or the account's own. 422 names each field that doesn't
    fit; an account of another workspace is 404 (the caller checks it exists)."""
    errors = check(update)
    if errors:
        raise ApiError("validation_error", errors=errors)
    query = select(BusinessHours).where(
        BusinessHours.social_account_id.is_(None)
        if account_id is None
        else BusinessHours.social_account_id == account_id
    )
    row = await session.scalar(query)
    if row is None:
        row = BusinessHours(social_account_id=account_id)
        session.add(row)
    row.enabled = update.enabled
    row.schedule = _stored(update)
    row.away_enabled = update.away_enabled
    row.away_message = (update.away_message or "").strip() or None
    row.auto_mode = update.auto_mode
    await session.flush()
    await session.refresh(row)
    return _view(row, await workspace_zone(session), now, account_id)


async def remove_override(session: AsyncSession, account_id: uuid.UUID) -> None:
    """The account goes back to the workspace's schedule."""
    row = await session.scalar(
        select(BusinessHours).where(BusinessHours.social_account_id == account_id)
    )
    if row is not None:
        await session.delete(row)
        await session.flush()


# ---------------------------------------------------------------- the away message


def away_applies(msg: Message) -> bool:
    """A person writing: not a story mention or like, and not a tap on a button, quick reply or
    conversation starter (those answer something we sent)."""
    from socialhood.services.automations import runtime

    return (
        msg.kind != "story_mention"
        and not runtime.is_story_like(msg)
        and not msg.postback_payload
        and not msg.quick_reply_payload
    )


def client_id_for(message_id: uuid.UUID) -> uuid.UUID:
    from socialhood.services.automations import actions

    return uuid.uuid5(actions.CLIENT_ID_NAMESPACE, f"away:{message_id}")


async def send_away(
    session: AsyncSession,
    deps: PlatformDeps,
    conv: Conversation,
    contact: Contact | None,
    msg: Message,
    *,
    ai_mode: str,
    now: datetime,
) -> bool:
    """Send the away message for this customer message when it is due; true when it was queued.
    The caller has locked the conversation and commits."""
    from socialhood.services import sending
    from socialhood.services.automations import actions, render

    found = await active(session, conv.social_account_id)
    if found is None or not found.row.away_enabled or not (found.row.away_message or "").strip():
        return False
    since = closed_since(found.hours, now)
    if since is None:  # open
        return False
    if conv.away_sent_at is not None and conv.away_sent_at >= since:
        return False  # already told them in this closed window
    paused = conv.ai_paused_until is not None and conv.ai_paused_until > now
    if ai_mode == "auto" and not paused:
        return False  # the AI answers; see the module docstring
    text = render.with_disclosure(
        saved_replies.fill(found.row.away_message or "", saved_replies.contact_values(contact)),
        await actions.disclosure(session),
    )
    try:
        await sending.queue_outbound(
            session,
            conv,
            source="automation",
            client_id=client_id_for(msg.id),
            text=text,
            deps=deps,
            now=now,
        )
    except ApiError:
        return False  # blocked or window closed: nothing is sent, and it may be tried again
    conv.away_sent_at = now
    return True
