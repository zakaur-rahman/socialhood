"""Business hours and away messages (GR-22): a weekly schedule in the workspace time zone."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

AutoModeName = Literal["always", "out_of_hours"]
# 00:00 to 23:59; "24:00" is allowed as a closing time (midnight at the end of the day).
TimeOfDay = Annotated[str, Field(pattern=r"^(?:(?:[01]\d|2[0-3]):[0-5]\d|24:00)$", max_length=5)]


class TimeRange(RequestModel, ResponseModel):
    """Open from ``start`` until ``end`` (the end itself is closed), 24-hour clock."""

    start: TimeOfDay
    end: TimeOfDay


class DaySchedule(RequestModel, ResponseModel):
    """``day`` is 0 (Monday) to 6 (Sunday). No ranges: closed all day. Ranges don't overlap; a
    range doesn't cross midnight (open late: end at 24:00, then start the next day at 00:00)."""

    day: int = Field(ge=0, le=6)
    # Required (no default) so the request and response shapes are one schema in OpenAPI.
    ranges: list[TimeRange] = Field(max_length=6)


class BusinessHoursUpdate(RequestModel):
    """The whole schedule. ``enabled`` with no ranges is refused. ``away_message`` is sent once
    per closed window when ``away_enabled`` (it may use ``{first_name}`` like a saved reply).
    ``auto_mode``: Auto mode answers always (today's behaviour) or only while closed."""

    enabled: bool
    days: list[DaySchedule] = Field(default_factory=list, max_length=7)
    away_enabled: bool = False
    away_message: str | None = Field(default=None, max_length=1000)
    auto_mode: AutoModeName = "always"


class BusinessHours(ResponseModel):
    """A schedule with all seven days (a closed day has no ranges). ``configured`` is false until
    one was saved. ``open_now`` is null while it is off."""

    social_account_id: uuid.UUID | None = None
    configured: bool
    enabled: bool
    days: list[DaySchedule]
    away_enabled: bool
    away_message: str | None = None
    auto_mode: AutoModeName
    open_now: bool | None = None


class AccountBusinessHours(ResponseModel):
    """An account and its own schedule, when it has one (``override``); otherwise the
    workspace's applies."""

    social_account_id: uuid.UUID
    platform: str
    username: str | None = None
    display_name: str | None = None
    override: BusinessHours | None = None


class BusinessHoursOverview(ResponseModel):
    timezone: str
    workspace: BusinessHours
    accounts: list[AccountBusinessHours]
