"""Leads (GR-18): moving a contact's stage, the stage counts and conversions, and the setting for
when a lead goes cold. A lead is a contact: its list is the contacts list with a ``stage``
filter."""

from __future__ import annotations

import datetime as dt

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.contacts import LeadStageName


class LeadStageUpdate(RequestModel):
    stage: LeadStageName
    note: str | None = Field(default=None, max_length=300)  # why; shown in the history


class LeadStageCount(ResponseModel):
    stage: LeadStageName
    count: int


class LeadWeek(ResponseModel):
    """Leads that reached a stage in the week starting ``week_start`` (a Monday, UTC)."""

    week_start: dt.date
    qualified: int
    won: int


class LeadSummary(ResponseModel):
    stages: list[LeadStageCount]  # every stage, in pipeline order, zero when empty
    cold: int  # open leads (qualified or follow up) that have gone cold
    weeks: list[LeadWeek]  # the last 8 weeks, oldest first
    cold_after_days: int


class LeadSettings(ResponseModel):
    cold_after_days: int


class LeadSettingsPatch(RequestModel):
    cold_after_days: int = Field(ge=1, le=90)
