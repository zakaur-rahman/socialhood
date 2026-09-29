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

Rules (the ones a phrase needed come back in ``rule``, in plain words):

Instants (``resolve_instant``)
- A time alone ("7 PM") is its next occurrence: today while still ahead, else tomorrow. A day
  without a time ("tomorrow", "Friday evening") is refused so the member is asked for the time.
- "7 PM", "7:30 pm", "7.30 p.m.", "19:00", "noon", "midnight" (the end of the named day: 00:00
  the day after). A bare hour ("tomorrow 10", "at 7") is on the 24-hour clock (7 → 7:00 AM)
  unless "afternoon", "evening", "night" or "tonight" is said (then 1-11 are PM).
  "tonight", "this morning", "this evening" are today.
- Weekdays: "Friday", "on Friday", "coming Friday" → the next Friday, today included while the
  time is still ahead (else a week later); "this Friday" → the Friday of the current week (weeks
  run Monday to Sunday, ISO); "next Friday" → the first Friday after today (said on a Friday: a
  week from today); "last Friday" → the most recent Friday before today.
- A date without a year ("30 Sep 18:00") is the next such date: this year unless it has passed.
- "in 2 hours", "in 30 minutes" add elapsed time; "in 3 days", "in 2 weeks" keep the clock time
  (calendar days, which differ from 72 elapsed hours across a daylight-saving change).
- Daylight saving: a clock time that doesn't exist (the clocks go forward) moves forward by the
  gap (2:30 AM → 3:30 AM); one that happens twice (the clocks go back) is the first of the two.

Ranges (``resolve_range``). ``upcoming`` is for lists of what is coming (scheduled messages and
posts); everything that looks back (conversations, comments, analytics) leaves it False.
- Calendar periods: "today", "yesterday", "tomorrow", "this/last/next week" (Monday-Sunday, ISO;
  "last week" is the previous such week), "this/last/next weekend", "this/last/next month",
  "this/last year", a day ("12 Sep", "2026-09-12", "Monday"), a month ("September", "Sep 2026"),
  a span ("between 1 and 15 Sep", "1-15 Sep 2026", "from 28 Dec to 3 Jan", "Monday to
  Wednesday", both ends included). Looking back, a period that hasn't ended runs to now ("this
  month" → the 1st to now); ``upcoming`` keeps the whole period.
- Rolling: "the last 30 days", "past 24 hours", "last 3 months", "past week" (= the last 7 days),
  "next 7 days". Hours and minutes are elapsed time; days and weeks keep the clock time; months
  are calendar months (the same day N months earlier, or that month's last day).
- "since Monday", "since 1 Sep", "since last week", "since 9 AM": from that day's start (or the
  most recent such time) to now.
- A bare weekday: looking back, the most recent one (today included); ``upcoming``, the next one
  (today included). "this/next/last Monday" as for instants.
- A day, month or span without a year: looking back, the latest one that has started;
  ``upcoming``, the earliest one that hasn't ended.

Ages (``resolve_age``): "after 24 hours", "at 7 days", "24h", "1 h", "3 days", "a week"; a month
counts as 30 days.

Analytics count calendar days (``calendar_days``): a range that starts part-way through a day
begins on the next day (the last 30 days are the 30 days up to and including today), unless it
lies within one day.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
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


# ---------------------------------------------------------------- words

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_ABBR = tuple(name[:3] for name in MONTH_NAMES)

WEEKDAYS: dict[str, int] = {
    **{name.lower(): i for i, name in enumerate(DAY_NAMES)},
    **{name.lower()[:3]: i for i, name in enumerate(DAY_NAMES)},
    "tues": 1,
    "weds": 2,
    "thur": 3,
    "thurs": 3,
}
MONTHS: dict[str, int] = {
    **{name.lower(): i for i, name in enumerate(MONTH_NAMES, start=1)},
    **{name.lower()[:3]: i for i, name in enumerate(MONTH_NAMES, start=1)},
    "sept": 9,
}
NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "twenty-four": 24,
    "thirty": 30,
    "forty-five": 45,
    "forty-eight": 48,
    "sixty": 60,
    "seventy-two": 72,
    "ninety": 90,
}
UNITS: dict[str, str] = {
    **dict.fromkeys(("m", "min", "mins", "minute", "minutes"), "minute"),
    **dict.fromkeys(("h", "hr", "hrs", "hour", "hours"), "hour"),
    **dict.fromkeys(("d", "day", "days"), "day"),
    **dict.fromkeys(("w", "wk", "wks", "week", "weeks"), "week"),
    **dict.fromkeys(("mo", "month", "months"), "month"),
}


def _alternatives(words: dict[str, int] | dict[str, str]) -> str:
    return "|".join(sorted(map(re.escape, words), key=len, reverse=True))


_WEEKDAY_WORDS = _alternatives(WEEKDAYS)
_MONTH_WORDS = _alternatives(MONTHS)
_NUMBER = rf"(\d+(?:\.\d+)?|{_alternatives(NUMBER_WORDS)})"
_UNIT = rf"({_alternatives(UNITS)})"
_DURATION = re.compile(rf"^{_NUMBER}\s*{_UNIT}$")
_HALF_HOUR = re.compile(r"^(?:a )?half (?:an )?hour$")
_MAX_SPAN = timedelta(days=3660)  # nothing reaches further than ten years


# ---------------------------------------------------------------- labels


def clock(t: time | datetime) -> str:
    """ "7:00 PM"; noon is "12:00 PM" and midnight "12:00 AM"."""
    hour = t.hour % 12 or 12
    return f"{hour}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def day_label(d: date, *, year: bool = True) -> str:
    """ "Wed 30 Sep 2026", or without the year."""
    text = f"{DAY_ABBR[d.weekday()]} {d.day} {MONTH_ABBR[d.month - 1]}"
    return f"{text} {d.year}" if year else text


def instant_label(at: datetime, tz: ZoneInfo, now: datetime) -> str:
    """ "Wed 30 Sep, 7:00 PM"; the year is added when it isn't the current one."""
    local = at.astimezone(tz)
    this_year = now.astimezone(tz).year
    return f"{day_label(local.date(), year=local.year != this_year)}, {clock(local)}"


def span_label(first: date, last: date) -> str:
    """Whole days, both included: "Wed 30 Sep 2026", "21-27 Sep 2026", "28 Sep - 4 Oct 2026",
    "28 Dec 2026 - 3 Jan 2027"."""
    if first == last:
        return day_label(first)
    end = f"{last.day} {MONTH_ABBR[last.month - 1]} {last.year}"
    if (first.year, first.month) == (last.year, last.month):
        return f"{first.day}-{end}"
    if first.year == last.year:
        return f"{first.day} {MONTH_ABBR[first.month - 1]} - {end}"
    return f"{first.day} {MONTH_ABBR[first.month - 1]} {first.year} - {end}"


def range_label(start: datetime, end: datetime, tz: ZoneInfo) -> str:
    """A range as the answer states it, in the workspace's zone: whole days as a span, a period
    that runs to now as "1-30 Sep 2026, up to 2:15 PM", anything else by its two points."""
    first, last = start.astimezone(tz), end.astimezone(tz)
    if first.time() == time(0) and last.time() == time(0):
        return span_label(first.date(), last.date() - timedelta(days=1))
    if first.time() == time(0):
        return f"{span_label(first.date(), last.date())}, up to {clock(last)}"

    def point(local: datetime) -> str:
        return f"{local.day} {MONTH_ABBR[local.month - 1]} {local.year}, {clock(local)}"

    return f"{point(first)} - {point(last)}"


def age_label(age: timedelta) -> str:
    """ "30 minutes", "1 hour", "24 hours", "36 hours", "3 days", "7 days"."""
    seconds = int(age.total_seconds())
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    if seconds < 2 * 86400 or seconds % 86400:
        hours = seconds / 3600
        shown: float = int(hours) if hours == int(hours) else round(hours, 1)
        return f"{shown:g} hour{'s' if shown != 1 else ''}"
    return f"{seconds // 86400} days"


# ---------------------------------------------------------------- calendar helpers


def localize(d: date, t: time, tz: ZoneInfo) -> tuple[datetime, str | None]:
    """The UTC instant of a wall-clock time in ``tz``, with the daylight-saving rule used when
    that time doesn't exist or happens twice (module docstring)."""
    naive = datetime.combine(d, t)
    first = naive.replace(tzinfo=tz, fold=0).astimezone(UTC)
    back = first.astimezone(tz)
    if back.replace(tzinfo=None) != naive:
        return first, (
            f"{clock(t)} doesn't exist on {day_label(d)} (the clocks go forward), "
            f"so {clock(back)} is used"
        )
    if naive.replace(tzinfo=tz, fold=1).astimezone(UTC) != first:
        return first, (
            f"{clock(t)} happens twice on {day_label(d)} (the clocks go back); "
            "the first one is used"
        )
    return first, None


def _midnight(d: date, tz: ZoneInfo) -> datetime:
    return localize(d, time(0), tz)[0]


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _days_in_month(year: int, month: int) -> int:
    following = date(year + (month == 12), month % 12 + 1, 1)
    return (following - timedelta(days=1)).day


def _add_months(d: date, months: int) -> date:
    year, month = divmod(d.year * 12 + d.month - 1 + months, 12)
    return date(year, month + 1, min(d.day, _days_in_month(year, month + 1)))


def _make_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _checked_date(year: int, month: int, day: int) -> date:
    found = _make_date(year, month, day)
    if found is None:
        raise TimeParseError(f"{day} {MONTH_ABBR[month - 1]} {year} isn't a date.")
    return found


# ---------------------------------------------------------------- phrases


def _normalise(phrase: str) -> str:
    text = phrase.strip().lower()
    for dash in (chr(0x2013), chr(0x2014), chr(0x2212)):  # en and em dash, minus
        text = text.replace(dash, "-")
    text = text.replace(chr(0x2019), "'")  # a typographic apostrophe
    text = re.sub(r"(?<![a-z])([ap])\.\s?m\.?(?![a-z])", r"\1m", text)  # p.m. → pm
    text = text.replace(",", " ")
    text = re.sub(r"[!?]+$", "", text)
    text = re.sub(r"(?<=[a-z])\.$", "", text)
    return " ".join(text.split())


def _cut(text: str, match: re.Match[str]) -> str:
    return " ".join(f"{text[: match.start()]} {text[match.end() :]}".split())


_FILLER = re.compile(r"^(?:(?:at|on|by|for|the)\s+)+|(?:\s+(?:at|on))+$")


def _strip_filler(text: str) -> str:
    return _FILLER.sub("", text).strip()


@dataclass(frozen=True)
class _Duration:
    amount: float
    unit: str  # minute, hour, day, week, month

    def elapsed(self) -> timedelta:
        """As elapsed time; a month counts as 30 days."""
        per = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000}
        return timedelta(seconds=self.amount * per[self.unit])


def _duration(text: str) -> _Duration | None:
    """ "24h", "24 hours", "a day", "1.5 hours", "half an hour"; None when it isn't one."""
    if _HALF_HOUR.match(text):
        return _Duration(30, "minute")
    match = _DURATION.match(text)
    if match is None:
        return None
    word = match.group(1)
    amount = float(NUMBER_WORDS[word]) if word in NUMBER_WORDS else float(word)
    if amount <= 0:
        raise TimeParseError(f"“{text}” isn't a length of time I can use.")
    return _Duration(amount, UNITS[match.group(2)])


def _shift(at: datetime, tz: ZoneInfo, span: _Duration, sign: int) -> datetime:
    """``at`` plus or minus ``span``: elapsed time for hours and minutes, the same clock time
    for days, weeks and months (module docstring)."""
    if span.unit in ("minute", "hour"):
        return at + sign * span.elapsed()
    local = at.astimezone(tz).replace(tzinfo=None)
    if span.unit == "month":
        if span.amount != int(span.amount):
            raise TimeParseError("Use whole months, for example “the last 3 months”.")
        target = datetime.combine(_add_months(local.date(), sign * int(span.amount)), local.time())
    else:
        target = local + sign * timedelta(days=span.amount * (7 if span.unit == "week" else 1))
    return localize(target.date(), target.time(), tz)[0]


# ---------------------------------------------------------------- times of day


@dataclass(frozen=True)
class _Clock:
    hour: int
    minute: int
    next_day: bool = False  # midnight: 00:00 after the named day

    @property
    def wall(self) -> time:
        return time(self.hour, self.minute)


_TIME_12 = re.compile(r"(?<![\d:.])(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b")
_TIME_24 = re.compile(r"(?<![\d:.-])(\d{1,2})[:.](\d{2})(?![\d:.])")
_NAMED_TIME = re.compile(r"\b(noon|midday|midnight)\b")
_PART_OF_DAY = re.compile(r"\b(in the |this )?(morning|afternoon|evening|night|tonight)\b")
_PM_PARTS = frozenset({"afternoon", "evening", "night", "tonight"})


def _take_clock(text: str) -> tuple[_Clock | None, str]:
    """An explicit time of day in ``text``, and the text without it."""
    if match := _TIME_12.search(text):
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if not 1 <= hour <= 12 or minute > 59:
            raise TimeParseError(f"“{match.group(0)}” isn't a time.")
        return _Clock(hour % 12 + (12 if match.group(3) == "pm" else 0), minute), _cut(text, match)
    if match := _TIME_24.search(text):
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            raise TimeParseError(f"“{match.group(0)}” isn't a time.")
        return _Clock(hour, minute), _cut(text, match)
    if match := _NAMED_TIME.search(text):
        found = _Clock(0, 0, next_day=True) if match.group(1) == "midnight" else _Clock(12, 0)
        return found, _cut(text, match)
    return None, text


# ---------------------------------------------------------------- days


@dataclass(frozen=True)
class _DateSpec:
    day: int
    month: int | None  # None: a bare day number ("1" in "between 1 and 15 Sep")
    year: int | None


_DATE_DMY = re.compile(rf"^(\d{{1,2}})(?:st|nd|rd|th)?(?: of)? ({_MONTH_WORDS})\.?(?: (\d{{4}}))?$")
_DATE_MDY = re.compile(rf"^({_MONTH_WORDS})\.? (\d{{1,2}})(?:st|nd|rd|th)?(?: (\d{{4}}))?$")
_DATE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_BARE_DAY = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?$")
_MONTH_ONLY = re.compile(rf"^({_MONTH_WORDS})\.?(?: (\d{{4}}))?$")
_WEEKDAY_PHRASE = re.compile(rf"^(?:(this|next|coming|last|previous) )?({_WEEKDAY_WORDS})$")


def _date_spec(text: str) -> _DateSpec | None:
    if match := _DATE_ISO.match(text):
        return _DateSpec(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    if match := _DATE_DMY.match(text):
        year = int(match.group(3)) if match.group(3) else None
        return _DateSpec(int(match.group(1)), MONTHS[match.group(2)], year)
    if match := _DATE_MDY.match(text):
        year = int(match.group(3)) if match.group(3) else None
        return _DateSpec(int(match.group(2)), MONTHS[match.group(1)], year)
    return None


def _weekday(which: str | None, weekday: int, today: date, *, upcoming: bool) -> date:
    """The day a weekday phrase names; ``which`` is this, next, last, coming or None (bare)."""
    ahead = (weekday - today.weekday()) % 7
    behind = (today.weekday() - weekday) % 7
    if which == "this":
        return _week_start(today) + timedelta(days=weekday)
    if which == "next":
        return today + timedelta(days=ahead or 7)
    if which in ("last", "previous"):
        return today - timedelta(days=behind or 7)
    if which == "coming" or upcoming:
        return today + timedelta(days=ahead)
    return today - timedelta(days=behind)


def _weekday_rule(which: str | None, weekday: int, today: date, *, upcoming: bool) -> str | None:
    name = DAY_NAMES[weekday]
    if which == "this":
        return f"“this {name}” is the {name} of this week (Monday to Sunday)"
    if which == "next":
        rule = f"“next {name}” is the first {name} after today"
        return rule + (
            f" (said on a {name}: a week from today)" if today.weekday() == weekday else ""
        )
    if which in ("last", "previous"):
        return f"“last {name}” is the most recent {name} before today"
    if which == "coming":
        return None
    which_one = "next" if upcoming else "most recent"
    return f"“{name}” is the {which_one} {name}, today included"


# ---------------------------------------------------------------- instants


_RELATIVE_INSTANT = re.compile(r"^(?:in|after) (.+)$|^(.+?) (?:from now|later)$")
_NOW = frozenset({"now", "right now", "immediately", "asap"})
_BARE_HOUR = re.compile(r"^(.*?)\s*(?:\bat )?(\d{1,2})$")


@dataclass(frozen=True)
class _Day:
    day: date
    rule: str | None = None
    flexible: bool = False  # a bare weekday: a week later once its time has passed today


def _instant_day(text: str, today: date) -> _Day | None:
    """The day part of an instant; None when ``text`` isn't one."""
    if text == "today":
        return _Day(today)
    if text in ("tomorrow", "tmrw", "tmr"):
        return _Day(today + timedelta(days=1))
    if text in ("day after tomorrow", "overmorrow"):
        return _Day(today + timedelta(days=2))
    if text == "yesterday":
        return _Day(today - timedelta(days=1))
    if match := _WEEKDAY_PHRASE.match(text):
        which, weekday = match.group(1), WEEKDAYS[match.group(2)]
        return _Day(
            _weekday(which, weekday, today, upcoming=True),
            None
            if which in (None, "coming")
            else _weekday_rule(which, weekday, today, upcoming=True),
            flexible=which in (None, "coming"),
        )
    spec = _date_spec(text)
    if spec is None or spec.month is None:
        return None
    if spec.year is not None:
        return _Day(_checked_date(spec.year, spec.month, spec.day))
    for year in range(today.year, today.year + 9):
        found = _make_date(year, spec.month, spec.day)
        if found is not None and found >= today:
            if year == today.year:
                return _Day(found)
            return _Day(found, f"no year given, so the next {day_label(found)}")
    raise TimeParseError(f"{spec.day} {MONTH_ABBR[spec.month - 1]} isn't a date.")


def resolve_instant(phrase: str, *, now: datetime, tz: ZoneInfo) -> ResolvedInstant:
    """A point in time: "tomorrow 7 PM", "Friday 10 AM", "in 2 hours", "30 Sep 18:30"."""
    text = _normalise(phrase)
    unreadable = TimeParseError(f"I can't read “{phrase}” as a date and time.")
    if not text:
        raise TimeParseError("Say when, for example “tomorrow 10 AM”.")
    if text in _NOW:
        return ResolvedInstant(phrase=phrase, at=now, label=instant_label(now, tz, now))
    if relative := _RELATIVE_INSTANT.match(text):
        span = _duration(relative.group(1) or relative.group(2))
        if span is not None:
            at = _shift(now, tz, span, +1)
            return ResolvedInstant(phrase=phrase, at=at, label=instant_label(at, tz, now))

    today = now.astimezone(tz).date()
    rules: list[str] = []
    found, rest = _take_clock(text)
    part = None
    this_part = False  # "tonight", "this evening": today
    if match := _PART_OF_DAY.search(rest):
        part, rest = match.group(2), _cut(rest, match)
        this_part = match.group(1) == "this " or part == "tonight"
    rest = _strip_filler(rest)
    day = _instant_day(rest, today) if rest else None
    if rest and day is None:
        bare = _BARE_HOUR.match(rest) if found is None else None
        if bare is None:
            raise unreadable
        head = _strip_filler(bare.group(1))
        day = _instant_day(head, today) if head else None
        if head and day is None:
            raise unreadable
        hour = int(bare.group(2))
        if hour > 23:
            raise TimeParseError(f"“{hour}” isn't an hour.")
        if part in _PM_PARTS and 1 <= hour <= 11:
            hour += 12
        elif part is None:
            rules.append(f"“{hour}” is read on the 24-hour clock as {clock(time(hour))}")
        found = _Clock(hour, 0)
    if day is None and this_part:
        day = _Day(today)
    if found is None:
        if day is None and part is None:
            raise unreadable
        raise TimeParseError(f"Which time? For example “{rest or 'tomorrow'} 10 AM”.")

    if day is not None and day.rule:
        rules.append(day.rule)
    target = day.day if day is not None else today
    if found.next_day:
        rules.append(f"midnight is the end of {day_label(target)}")
        target += timedelta(days=1)
    at, dst = localize(target, found.wall, tz)
    if at <= now and (day is None or day.flexible) and not found.next_day:
        target += timedelta(days=1 if day is None else 7)
        at, dst = localize(target, found.wall, tz)
        then = "tomorrow" if day is None else f"next {DAY_NAMES[target.weekday()]}"
        rules.append(f"{clock(found.wall)} has passed today, so {then}")
    if dst:
        rules.append(dst)
    return ResolvedInstant(
        phrase=phrase,
        at=at,
        label=instant_label(at, tz, now),
        rule="; ".join(rules) or None,
    )


# ---------------------------------------------------------------- ranges


@dataclass(frozen=True)
class _Span:
    start: datetime  # UTC
    end: datetime  # UTC
    rule: str | None = None
    calendar: bool = False  # a calendar period: looking back, it runs to now if not over


@dataclass(frozen=True)
class _Scope:
    now: datetime
    tz: ZoneInfo
    upcoming: bool

    @property
    def today(self) -> date:
        return self.now.astimezone(self.tz).date()

    def days(self, first: date, last: date, rule: str | None = None) -> _Span:
        """Whole days ``first``..``last``, both included."""
        start = _midnight(first, self.tz)
        return _Span(start, _midnight(last + timedelta(days=1), self.tz), rule, calendar=True)


_WEEK_RULE = "weeks run Monday to Sunday"
_PERIOD = re.compile(r"^(this|current|last|previous|next|coming|past) (week|weekend|month|year)$")
_ROLLING = re.compile(rf"^(last|past|previous|recent|next|coming) (?:{_NUMBER} ?)?{_UNIT}$")
_SEPARATOR = re.compile(r"\s*-\s*|\s+(?:and|to|until|till|through|thru)\s+")
# "the past week" is rolling, unlike "last week" (module docstring).
_PAST = {
    "week": (_Duration(7, "day"), "the last 7 days up to now"),
    "month": (_Duration(1, "month"), "from this day last month up to now"),
    "year": (_Duration(12, "month"), "the last 12 months up to now"),
}


def _named_period(which: str, unit: str, scope: _Scope) -> _Span:
    today = scope.today
    if which == "past" and unit in _PAST:
        span, words = _PAST[unit]
        start = _shift(scope.now, scope.tz, span, -1)
        return _Span(start, scope.now, f"“the past {unit}” is {words}")
    step = {"this": 0, "current": 0, "last": -1, "previous": -1, "past": -1, "next": 1}
    offset = step.get(which, 1)
    if unit == "week":
        first = _week_start(today) + timedelta(weeks=offset)
        return scope.days(first, first + timedelta(days=6), _WEEK_RULE)
    if unit == "weekend":
        saturday = _week_start(today) + timedelta(weeks=offset, days=5)
        return scope.days(saturday, saturday + timedelta(days=1), _WEEK_RULE)
    if unit == "month":
        first = _add_months(today.replace(day=1), offset)
        return scope.days(first, _add_months(first, 1) - timedelta(days=1))
    return scope.days(date(today.year + offset, 1, 1), date(today.year + offset, 12, 31))


def _year_for(first: tuple[int, int], last: tuple[int, int], scope: _Scope) -> int:
    """The year of a span's first day when no year was given (module docstring): looking back,
    the latest span that has started; ``upcoming``, the earliest that hasn't ended."""
    today = scope.today
    wraps = last < first  # "20 Dec to 5 Jan": the end is in the following year
    spans = []
    for year in range(today.year - 8, today.year + 9):
        start, end = _make_date(year, *first), _make_date(year + wraps, *last)
        if start is not None and end is not None:
            spans.append((year, start, end))
    if scope.upcoming:
        chosen = next((year for year, _, end in spans if end >= today), None)
    else:
        chosen = next((year for year, start, _ in reversed(spans) if start <= today), None)
    if chosen is None:
        raise TimeParseError("That date doesn't exist.")
    return chosen


def _date_span(a: _DateSpec, b: _DateSpec, scope: _Scope) -> _Span:
    """Whole days from ``a`` to ``b``; a bare day number borrows ``b``'s month and year."""
    if b.month is None:
        raise TimeParseError("Name the month, for example “1-15 Sep”.")
    a_month = a.month if a.month is not None else b.month
    a_year = a.year if a.month is not None else b.year
    if a_month == b.month and a.day > b.day and a_year == b.year:
        raise TimeParseError("The end date is before the start date.")
    rule = None
    if a_year is not None and b.year is not None:
        first = _checked_date(a_year, a_month, a.day)
        last = _checked_date(b.year, b.month, b.day)
    elif b.year is not None:
        year = b.year if (a_month, a.day) <= (b.month, b.day) else b.year - 1
        first = _checked_date(year, a_month, a.day)
        last = _checked_date(b.year, b.month, b.day)
    elif a_year is not None:
        first = _checked_date(a_year, a_month, a.day)
        year = a_year if (b.month, b.day) >= (a_month, a.day) else a_year + 1
        last = _checked_date(year, b.month, b.day)
    else:
        year = _year_for((a_month, a.day), (b.month, b.day), scope)
        first = _checked_date(year, a_month, a.day)
        last = _checked_date(year + ((b.month, b.day) < (a_month, a.day)), b.month, b.day)
        if first.year != scope.today.year or last.year != scope.today.year:
            which = "next" if scope.upcoming else "most recent"
            rule = f"no year given, so the {which}: {span_label(first, last)}"
    if last < first:
        raise TimeParseError("The end date is before the start date.")
    return scope.days(first, last, rule)


def _day_span(text: str, scope: _Scope) -> _Span | None:
    """A named period, a day, a month or a date; None when ``text`` isn't one."""
    today = scope.today
    named = {
        "today": 0,
        "tonight": 0,
        "yesterday": -1,
        "tomorrow": 1,
        "tmrw": 1,
        "day after tomorrow": 2,
        "day before yesterday": -2,
    }
    if text in named:
        day = today + timedelta(days=named[text])
        return scope.days(day, day)
    if match := _PERIOD.match(text):
        return _named_period(match.group(1), match.group(2), scope)
    if match := _WEEKDAY_PHRASE.match(text):
        which, weekday = match.group(1), WEEKDAYS[match.group(2)]
        day = _weekday(which, weekday, today, upcoming=scope.upcoming)
        return scope.days(day, day, _weekday_rule(which, weekday, today, upcoming=scope.upcoming))
    if match := _MONTH_ONLY.match(text):
        month = MONTHS[match.group(1)]
        rule = None
        if match.group(2):
            year = int(match.group(2))
        else:
            if scope.upcoming:
                year = today.year if month >= today.month else today.year + 1
            else:
                year = today.year if month <= today.month else today.year - 1
            if year != today.year:
                which = "next" if scope.upcoming else "most recent"
                rule = f"no year given, so the {which} {MONTH_NAMES[month - 1]}: {year}"
        first = date(year, month, 1)
        return scope.days(first, _add_months(first, 1) - timedelta(days=1), rule)
    spec = _date_spec(text)
    if spec is not None:
        return _date_span(spec, spec, scope)
    return None


def _endpoint(text: str, scope: _Scope) -> _Span:
    found = _day_span(_strip_filler(text), scope)
    if found is None:
        raise TimeParseError(f"I can't read “{text}” as a day.")
    return found


def _between(a: str, b: str, scope: _Scope) -> _Span:
    a, b = _strip_filler(a), _strip_filler(b)
    bare = _BARE_DAY.match(a)
    spec_a = _DateSpec(int(bare.group(1)), None, None) if bare else _date_spec(a)
    spec_b = _date_spec(b)
    if spec_a is not None and spec_b is not None:
        return _date_span(spec_a, spec_b, scope)
    days_a, days_b = _WEEKDAY_PHRASE.match(a), _WEEKDAY_PHRASE.match(b)
    if days_a and days_b and days_b.group(1) is None:
        # "Monday to Wednesday": the second day is the first such day on or after the first.
        first = _endpoint(a, scope)
        offset = (WEEKDAYS[days_b.group(2)] - WEEKDAYS[days_a.group(2)]) % 7
        return _Span(
            first.start,
            _shift(first.end, scope.tz, _Duration(offset, "day"), +1),
            first.rule,
            calendar=True,
        )
    first, last = _endpoint(a, scope), _endpoint(b, scope)
    if last.end <= first.start:
        raise TimeParseError("The end is before the start.")
    rule = "; ".join(r for r in (first.rule, last.rule) if r) or None
    return _Span(first.start, last.end, rule, calendar=True)


def _splits(text: str) -> Iterator[tuple[str, str]]:
    for match in _SEPARATOR.finditer(text):
        a, b = text[: match.start()].strip(), text[match.end() :].strip()
        if a and b:
            yield a, b


def _since(text: str, scope: _Scope) -> _Span:
    """From the start of the named day (or the most recent such time) to now. "since" always
    looks back, whatever ``scope.upcoming`` says."""
    back = _Scope(scope.now, scope.tz, upcoming=False)
    text = _strip_filler(text)
    found, rest = _take_clock(text)
    rest = _strip_filler(rest)
    unreadable = TimeParseError(f"I can't read “since {text}”.")
    if found is None:
        day = _day_span(text, back)
        if day is None:
            raise unreadable
        start, rule = day.start, day.rule
    elif rest:
        day = _day_span(rest, back)
        if day is None:
            raise unreadable
        start, dst = localize(day.start.astimezone(scope.tz).date(), found.wall, scope.tz)
        rule = "; ".join(r for r in (day.rule, dst) if r) or None
    else:  # "since 9 AM": the most recent 9 AM
        start, rule = localize(back.today, found.wall, scope.tz)
        if start > scope.now:
            start, rule = localize(back.today - timedelta(days=1), found.wall, scope.tz)
    if start >= scope.now:
        raise TimeParseError(f"“since {text}” is in the future.")
    return _Span(start, scope.now, rule)


def _parse_range(text: str, scope: _Scope) -> _Span:
    found = _day_span(text, scope)
    if found is not None:
        return found
    if match := _ROLLING.match(text):
        amount = match.group(2)
        span = _Duration(
            float(NUMBER_WORDS[amount]) if amount in NUMBER_WORDS else float(amount or 1),
            UNITS[match.group(3)],
        )
        if span.amount <= 0:
            raise TimeParseError(f"“{text}” isn't a period I can use.")
        if match.group(1) in ("next", "coming"):
            return _Span(scope.now, _shift(scope.now, scope.tz, span, +1))
        return _Span(_shift(scope.now, scope.tz, span, -1), scope.now)
    if text.startswith("since "):
        return _since(text.removeprefix("since "), scope)
    body = re.sub(r"^(?:between|from) ", "", text)
    problem: TimeParseError | None = None
    for a, b in _splits(body):
        try:
            return _between(a, b, scope)
        except TimeParseError as error:
            problem = problem or error
    if text.startswith("from "):
        return _since(body, scope)
    raise problem or TimeParseError(f"I can't read “{text}” as a period.")


def resolve_range(
    phrase: str, *, now: datetime, tz: ZoneInfo, upcoming: bool = False
) -> ResolvedRange:
    """A period: "last week", "this month", "the last 30 days", "yesterday", "1-15 Sep".

    ``upcoming`` is for lists of what is coming (scheduled messages and posts): a period that
    hasn't ended keeps its end, and days, months and spans without a year look forward."""
    text = _normalise(phrase)
    text = re.sub(r"^(?:over|during|for|within|in)\s+", "", text)
    text = re.sub(r"^the\s+", "", text)
    if not text:
        raise TimeParseError("Say which period, for example “the last 30 days”.")
    span = _parse_range(text, _Scope(now, tz, upcoming))
    end = span.end
    if span.calendar and not upcoming and span.start < now < span.end:
        end = now  # looking back, a period that hasn't ended runs to now
    if end <= span.start:
        raise TimeParseError(f"“{phrase}” is an empty period.")
    if end - span.start > _MAX_SPAN:
        raise TimeParseError(f"“{phrase}” is longer than I can look at.")
    return ResolvedRange(
        phrase=phrase,
        start=span.start,
        end=end,
        label=range_label(span.start, end, tz),
        rule=span.rule,
    )


def calendar_days(resolved: ResolvedRange, tz: ZoneInfo) -> tuple[date, date]:
    """The calendar days (both included) an analytics query covers for ``resolved`` (module
    docstring): a partial first day is left out unless the range lies within one day."""
    first = resolved.start.astimezone(tz)
    last = (resolved.end - timedelta(microseconds=1)).astimezone(tz).date()
    since = first.date()
    if first.time() != time(0) and since < last:
        since += timedelta(days=1)
    return since, last


# ---------------------------------------------------------------- ages


_AGE_PREFIX = re.compile(r"^(?:(?:after|at the|at|within|by|when it was|when)\s+)+")
_AGE_SUFFIX = re.compile(
    r"(?:\s+(?:old|mark|in|of publishing|of posting|after (?:publishing|posting|it was posted|"
    r"it was published|it went live)))+$"
)


def resolve_age(phrase: str) -> ResolvedAge:
    """An age after publishing: "after 24 hours", "at 7 days", "1 h"."""
    text = _AGE_SUFFIX.sub("", _AGE_PREFIX.sub("", _normalise(phrase))).strip()
    span = _duration(text)
    if span is None:
        raise TimeParseError(f"I can't read “{phrase}” as an age, for example “24 hours”.")
    age = span.elapsed()
    if age < timedelta(minutes=1) or age > timedelta(days=366):
        raise TimeParseError(f"“{phrase}” isn't an age I can compare at.")
    rule = "a month counts as 30 days" if span.unit == "month" else None
    return ResolvedAge(phrase=phrase, age=age, label=age_label(age), rule=rule)
