"""What every analytics read shares (TR-AGT-05): the view (time zone, clock, capabilities), the
workspace's calendar days as date ranges, and loading a post or account of the current workspace
(404 otherwise)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import SocialAccount
from socialhood.models.media import MediaItem
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.repositories import social_accounts as accounts

DEFAULT_RANGE_DAYS = 30

Capabilities = Callable[[SocialAccount], frozenset[Capability]]


def capabilities_from(deps: PlatformDeps) -> Capabilities:
    """What each account can do, from its adapter (TR-PL-11); nothing when it has none."""

    def of(acct: SocialAccount) -> frozenset[Capability]:
        try:
            return adapter_for(acct, deps).capabilities_for(acct)
        except PlatformError:
            return frozenset()

    return of


@dataclass(frozen=True)
class View:
    """What every analytics read needs besides the session (in the workspace's scope)."""

    timezone: str  # the workspace's IANA zone: ranges are its calendar days
    now: datetime
    capabilities: Capabilities  # tells whether an account has granted insights


def zone(timezone: str) -> ZoneInfo:
    """The workspace's zone; UTC when the stored name is not a known IANA zone."""
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


@dataclass(frozen=True)
class DateRange:
    since: date
    until: date
    start: datetime  # since at 00:00 local
    end: datetime  # the day after until at 00:00 local (exclusive)


def date_range(timezone: str, now: datetime, since: date | None, until: date | None) -> DateRange:
    """Local days ``since``..``until``, both included. Missing ends: the last 30 days up to today
    (or the 30 days up to ``until``, or ``since`` to today). ``since`` after ``until`` is 422."""
    tz = zone(timezone)
    today = now.astimezone(tz).date()
    if until is None:
        until = today if since is None else max(today, since)
    if since is None:
        since = until - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if since > until:
        raise ApiError(
            "validation_error",
            "The start date is after the end date.",
            errors=[FieldError("since", "Pick a start date on or before the end date.")],
        )
    return DateRange(
        since=since,
        until=until,
        start=datetime.combine(since, time.min, tzinfo=tz),
        end=datetime.combine(until + timedelta(days=1), time.min, tzinfo=tz),
    )


async def load_post(session: AsyncSession, post_id: uuid.UUID) -> MediaItem:
    """A post of the current workspace, or 404."""
    post = (await session.scalars(select(MediaItem).where(MediaItem.id == post_id))).one_or_none()
    if post is None:
        raise ApiError("not_found", "That post wasn't found.")
    return post


async def load_account(session: AsyncSession, account_id: uuid.UUID) -> SocialAccount:
    """A connected account of the current workspace, or 404."""
    acct = await accounts.get(session, account_id)
    if acct is None:
        raise ApiError("not_found", "That account wasn't found.")
    return acct
