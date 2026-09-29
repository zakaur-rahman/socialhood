"""The time resolver (FR-AGT-05, TA.3; agent-architecture.html §4 Time resolver).

Turns the phrases a member uses into explicit values in the workspace's time zone before any tool
runs. The model passes the phrase; tools receive resolved values; the answer states them. Nothing
here calls a model: the same phrase, ``now`` and zone always give the same answer.

- Instants: "tomorrow 7 PM" → 2026-09-30T19:00+05:30 (stored and passed as UTC).
- Ranges, half-open [start, end): "last week" → Monday to Sunday of the previous ISO week; "this
  month" → the 1st to now; "the last 30 days" → now minus 30 days to now; "today", "yesterday",
  "this week", "last month", "since Monday", explicit dates ("12 Sep", "1-15 Sep 2026").
- Ages after publishing: "after 24 hours", "at 7 days" (compare posts at the same age, FR-ANL-01).

Ambiguous input (such as "next Friday" said on a Friday) is resolved by a documented rule,
returned in ``rule`` and stated in the answer. Phrases are English; the planner passes Hindi and
Hinglish times in English ("kal shaam 7 baje" → "tomorrow 7 PM").

The signatures below are the contract; TA.3 implements them with a table of phrases, time zones
and edge days (month ends, DST where the zone has it, week boundaries).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict


class _Resolved(BaseModel):
    model_config = ConfigDict(frozen=True)

    phrase: str  # as the model passed it
    rule: str | None = None  # the rule applied to an ambiguous phrase, in plain words


class ResolvedInstant(_Resolved):
    at: datetime  # UTC
    label: str  # in the workspace's zone for the answer, e.g. "Wed 30 Sep, 7:00 PM"


class ResolvedRange(_Resolved):
    start: datetime  # UTC, inclusive
    end: datetime  # UTC, exclusive
    label: str  # in the workspace's zone for the answer, e.g. "21-27 Sep 2026"


class ResolvedAge(_Resolved):
    age: timedelta  # time since publishing
    label: str  # e.g. "24 hours"


class TimeParseError(ValueError):
    """The phrase isn't a time, range or age this resolver understands; the tool reports it and
    the model asks the member (no guessing, FR-AGT-06)."""


def resolve_instant(phrase: str, *, now: datetime, tz: ZoneInfo) -> ResolvedInstant:
    """A point in time: "tomorrow 7 PM", "Friday 10 AM", "in 2 hours", "30 Sep 18:30"."""
    raise NotImplementedError("TA.3")


def resolve_range(phrase: str, *, now: datetime, tz: ZoneInfo) -> ResolvedRange:
    """A period: "last week", "this month", "the last 30 days", "yesterday", "1-15 Sep"."""
    raise NotImplementedError("TA.3")


def resolve_age(phrase: str) -> ResolvedAge:
    """An age after publishing: "after 24 hours", "at 7 days", "1 h"."""
    raise NotImplementedError("TA.3")
