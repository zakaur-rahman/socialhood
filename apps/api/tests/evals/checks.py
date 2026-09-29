"""The agent eval's checks (TA.6; agent-architecture.html §18): pure functions over one run's
record, unit-tested in tests/unit/test_agent_eval_checks.py without a model.

- Tool choice: the tools called include at least one acceptable tool and no forbidden one.
- Grounding: every number in the answer is in a tool result of that run (anywhere in the step
  result JSON, strings included), in the request, in the run's clock, or trivially derived: a
  rounding of one of those, a percentage of a 0-1 share, a sum or difference of two whole numbers
  from the same result object, or a count of listed items. Numbers inside citation markers
  ``[n]``, list numbering, links and handles are ignored; a date or time counts as grounded when
  its day and month, or its hour and minute, come from a result.
- Exact numbers: each expected number (computed from the seed) appears in the answer, rounded
  the way people write it.
- Citations: every ``[n]`` has an answer_ref.
- Action card: a draft request produced the expected card.
- Text: phrases an honest answer must contain (a caveat, "none", a refusal), as regexes.

Numbers are read the way the answer writes them: "1,234" and "1,23,456" (Indian grouping),
"12%", "3.5", "4.1k", "2 lakh", "1.5 crore", Devanagari digits, and the English number words two
to twenty ("one" is left alone: "which one", "one of them").
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
MULTIPLIERS: dict[str, Decimal] = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "hazaar": Decimal(1_000),
    "hazar": Decimal(1_000),
    "हज़ार": Decimal(1_000),
    "हजार": Decimal(1_000),
    "lakh": Decimal(100_000),
    "lakhs": Decimal(100_000),
    "lac": Decimal(100_000),
    "लाख": Decimal(100_000),
    "million": Decimal(1_000_000),
    "m": Decimal(1_000_000),
    "crore": Decimal(10_000_000),
    "crores": Decimal(10_000_000),
    "cr": Decimal(10_000_000),
    "करोड़": Decimal(10_000_000),
    "करोड": Decimal(10_000_000),
}
WORDS = {
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
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
MONTHS = {
    name: i + 1
    for i, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        )
    )
    for name in names
}
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DASH = r"[-\u2013]"  # a hyphen or an en dash

CITATION = re.compile(r"\[\s*\d{1,3}(?:\s*,\s*\d{1,3})*\s*\]")
LINK = re.compile(
    r"https?://\S+|www\.\S+|\b[a-z][\w-]*(?:\.[\w-]+)*\.(?:in|com|org|net|io)\b(?:/\S*)?|@[\w.]+",
    re.IGNORECASE,
)
LIST_MARKER = re.compile(r"(?m)^\s*\d{1,2}[.)]\s+")
ISO_DATE = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?"
)
# 7 PM, 7:30 pm, 19:00, 7.30 p.m.
TIME = re.compile(
    r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)(?![a-z])|\b(\d{1,2}):(\d{2})\b",
    re.IGNORECASE,
)
# 26 Sep, 26 Sep 2026, 21-27 Sep, Sep 26, September 26th
_ORDINAL = r"(?:st|nd|rd|th)?"
DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}}){_ORDINAL}(?:\s*{_DASH}\s*(\d{{1,2}}){_ORDINAL})?\s+({_MONTH})\b\.?"
    r"(?:,?\s+(\d{4}))?",
    re.IGNORECASE,
)
MONTH_DAY = re.compile(
    rf"\b({_MONTH})\.?\s+(\d{{1,2}}){_ORDINAL}\b(?:\s*{_DASH}\s*(\d{{1,2}})\b)?"
    r"(?:,?\s+(\d{4}))?",
    re.IGNORECASE,
)
NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s*(%|percent|प्रतिशत)"
    r"|\s*(k|thousand|hazaa?r|हज़ार|हजार|lakhs?|lac|लाख|million|m|crores?|cr|करोड़|करोड)\b)?",
    re.IGNORECASE,
)
WORD_NUMBER = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.IGNORECASE)


# ---------------------------------------------------------------- reading numbers


@dataclass(frozen=True)
class Number:
    """A number as the answer (or a result) writes it."""

    value: Decimal
    raw: str
    precision: Decimal  # the unit of its last written digit (1 for "4,125", 100 for "4.1k")
    percent: bool = False


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _precision(digits: str, multiplier: Decimal) -> Decimal:
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    return Decimal(1).scaleb(-decimals) * multiplier


def normalise(text: str) -> str:
    """Devanagari digits as ASCII, typographic dashes and spaces plain."""
    for space in ("\N{THIN SPACE}", "\N{NARROW NO-BREAK SPACE}", "\N{NO-BREAK SPACE}"):
        text = text.replace(space, " ")
    return text.translate(DEVANAGARI_DIGITS)


def strip_noise(text: str) -> str:
    """Citation markers, links and @handles, and list numbering removed."""
    text = CITATION.sub(" ", text)
    text = LINK.sub(" ", text)
    return LIST_MARKER.sub(" ", text)


def _read(text: str, *, words: bool) -> list[tuple[Number, int]]:
    """The numbers in (normalised) ``text`` with where each starts."""
    found: list[tuple[Number, int]] = []
    for match in NUMBER.finditer(text):
        digits, percent, unit = match.group(1), match.group(2), match.group(3)
        value = _decimal(digits)
        if value is None:
            continue
        multiplier = MULTIPLIERS.get(unit.lower(), Decimal(1)) if unit else Decimal(1)
        if unit and unit.lower() == "m" and not re.fullmatch(r"\d+\.\d+", digits):
            multiplier = Decimal(1)  # "5 m" is five minutes more often than five million
        number = Number(
            value=value * multiplier,
            raw=match.group(0),
            precision=_precision(digits, multiplier),
            percent=bool(percent),
        )
        found.append((number, match.start()))
    if words:
        for match in WORD_NUMBER.finditer(text):
            number = Number(Decimal(WORDS[match.group(1).lower()]), match.group(0), Decimal(1))
            found.append((number, match.start()))
    return sorted(found, key=lambda pair: pair[1])


def numbers(text: str, *, words: bool = True) -> list[Number]:
    """Every number written in ``text`` (dates and times included, as plain numbers)."""
    return [n for n, _ in _read(normalise(text), words=words)]


@dataclass(frozen=True)
class Moments:
    """Dates (month, day) and clock times (hour on a 12-hour clock, minute) a text names."""

    dates: frozenset[tuple[int, int]] = frozenset()
    times: frozenset[tuple[int, int]] = frozenset()

    def __or__(self, other: Moments) -> Moments:
        return Moments(self.dates | other.dates, self.times | other.times)


def moments(text: str, timezone: ZoneInfo | None = None) -> Moments:
    """Dates and times written in ``text``; ISO timestamps are read in ``timezone``."""
    text = normalise(text)
    dates: set[tuple[int, int]] = set()
    times: set[tuple[int, int]] = set()
    for match in ISO_DATE.finditer(text):
        _, month, day, hour, minute = match.groups()
        try:
            at = datetime.fromisoformat(match.group(0).replace(" ", "T"))
        except ValueError:
            at = None
        if at is not None and at.tzinfo is not None and timezone is not None:
            local = at.astimezone(timezone)
            dates.add((local.month, local.day))
            times.add((local.hour % 12, local.minute))
            continue
        dates.add((int(month), int(day)))
        if hour is not None:
            times.add((int(hour) % 12, int(minute)))
    for match in DAY_MONTH.finditer(text):
        month = MONTHS[match.group(3).lower().rstrip(".")]
        for day in (match.group(1), match.group(2)):
            if day:
                dates.add((month, int(day)))
    for match in MONTH_DAY.finditer(text):
        month = MONTHS[match.group(1).lower().rstrip(".")]
        for day in (match.group(2), match.group(3)):
            if day:
                dates.add((month, int(day)))
    for match in TIME.finditer(text):
        if match.group(1):
            hour, minute = int(match.group(1)), int(match.group(2) or 0)
        else:
            hour, minute = int(match.group(4)), int(match.group(5))
        if hour <= 24 and minute < 60:
            times.add((hour % 12, minute))
    return Moments(frozenset(dates), frozenset(times))


# ---------------------------------------------------------------- the pool of known numbers


@dataclass
class Pool:
    """What a run's answer may state: every number its tool results (and request and clock)
    contain, and the values trivially derived from them."""

    values: set[Decimal] = field(default_factory=set)
    derived: set[Decimal] = field(default_factory=set)
    known: Moments = field(default_factory=Moments)

    def add(self, value: Decimal) -> None:
        value = abs(value)  # "-0.8" is written "0.8" as often as not
        self.values.add(value)
        if Decimal(0) < value <= Decimal(1) and value != value.to_integral_value():
            self.derived.add(value * 100)  # a 0-1 share as a percentage

    def contains(self, number: Number) -> bool:
        """``number`` is a known value, or one of them rounded to its precision."""
        half = number.precision / 2
        return any(abs(v - number.value) <= half for v in (*self.values, *self.derived))


def _walk(node: Any, pool: Pool, timezone: ZoneInfo | None) -> None:
    if isinstance(node, bool) or node is None:
        return
    if isinstance(node, int | float):
        pool.add(Decimal(str(node)))
        return
    if isinstance(node, str):
        for n in numbers(node, words=False):
            pool.add(n.value)
        pool.known = pool.known | moments(node, timezone)
        return
    if isinstance(node, Mapping):
        whole = [
            Decimal(v) for v in node.values() if isinstance(v, int) and not isinstance(v, bool)
        ]
        for i, a in enumerate(whole):  # sums and differences of two figures of one object
            for b in whole[i + 1 :]:
                pool.derived.update({a + b, abs(a - b)})
        for value in node.values():
            _walk(value, pool, timezone)
        return
    if isinstance(node, Sequence):
        pool.derived.add(Decimal(len(node)))  # a count of listed items
        for value in node:
            _walk(value, pool, timezone)


def pool_of(
    results: Iterable[Any],
    *,
    request: str = "",
    now: datetime | None = None,
    timezone: ZoneInfo | None = None,
) -> Pool:
    """The pool for one run: its step results (as stored JSON), the request and the clock."""
    pool = Pool()
    tops: list[Decimal] = []
    for result in results:
        _walk(result, pool, timezone)
        if isinstance(result, Mapping):
            tops += [
                Decimal(v)
                for v in result.values()
                if isinstance(v, int) and not isinstance(v, bool)
            ]
    for i, a in enumerate(tops):  # a headline figure of one step against another's
        for b in tops[i + 1 :]:
            pool.derived.update({a + b, abs(a - b)})
    for n in numbers(request):
        pool.add(n.value)
    pool.known = pool.known | moments(request, timezone)
    if now is not None:  # today's date and the time, as the system prompt states them
        local = now.astimezone(timezone) if timezone else now
        pool.add(Decimal(local.year))
        pool.known = pool.known | Moments(
            frozenset({(local.month, local.day)}), frozenset({(local.hour % 12, local.minute)})
        )
    return pool


# ---------------------------------------------------------------- grounding


@dataclass(frozen=True)
class Grounding:
    checked: int  # numbers read from the answer
    flagged: list[str]  # the ones no result supports

    @property
    def passed(self) -> bool:
        return not self.flagged


def ground(answer: str, pool: Pool) -> Grounding:
    """Every number in the answer must come from the pool (see the module docstring). A date
    ("26 Sep", "21-27 Sep 2026") is grounded when its days and year are known; a time ("7 PM",
    "19:00") when its hour and minute are."""
    text = strip_noise(normalise(answer))
    flagged: list[str] = []
    checked = 0
    covered: list[tuple[int, int]] = []

    def inside(at: int) -> bool:
        return any(a <= at < b for a, b in covered)

    for pattern in (DAY_MONTH, MONTH_DAY):
        for match in pattern.finditer(text):
            if inside(match.start()):
                continue
            covered.append(match.span())
            checked += 1
            said = moments(match.group(0))
            year = match.group(4)
            known_year = year is None or Decimal(year) in pool.values
            if not (said.dates and said.dates <= pool.known.dates and known_year):
                flagged.append(match.group(0).strip().rstrip("."))
    for match in TIME.finditer(text):
        if inside(match.start()):
            continue
        covered.append(match.span())
        checked += 1
        if not moments(match.group(0)).times <= pool.known.times:
            flagged.append(match.group(0).strip().rstrip("."))
    for n, at in _read(text, words=True):
        if inside(at):
            continue
        checked += 1
        if not pool.contains(n):
            flagged.append(n.raw.strip())
    return Grounding(checked=checked, flagged=_dedupe(flagged))


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


# Text the model writes into a draft tool's arguments: it lands on a card the member may send as
# it is, so its numbers must be grounded like the answer's.
DRAFT_TEXT: dict[str, tuple[str, ...]] = {
    "prepare_comment_reply": ("text",),
    "prepare_scheduled_message": ("text",),
    "prepare_automation": ("message_text", "ai_instructions", "public_reply_texts"),
    "draft_reply": ("instructions",),
}


def drafted_texts(tool: str, args: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for name in DRAFT_TEXT.get(tool, ()):
        value = args.get(name)
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, list):
            texts += [v for v in value if isinstance(v, str)]
    return texts


def ground_run(answer: str, drafts: Sequence[str], pool: Pool) -> Grounding:
    """The answer and the text the model drafted for cards, against one pool."""
    said = ground(answer, pool)
    flagged = list(said.flagged)
    checked = said.checked
    for text in drafts:
        drafted = ground(text, pool)
        checked += drafted.checked
        flagged += [f"{n} (drafted text)" for n in drafted.flagged]
    return Grounding(checked=checked, flagged=_dedupe(flagged))


# ---------------------------------------------------------------- the other checks


@dataclass(frozen=True)
class ToolChoice:
    passed: bool
    called: list[str]
    missing: bool  # none of the acceptable tools was called
    forbidden: list[str]


def tool_choice(
    called: Sequence[str], expect: Iterable[str], forbid: Iterable[str] = ()
) -> ToolChoice:
    """At least one acceptable tool (any, when none is listed) and no forbidden one."""
    acceptable = set(expect)
    used = list(dict.fromkeys(called))
    forbidden = [t for t in used if t in set(forbid)]
    missing = bool(acceptable) and not acceptable & set(used)
    return ToolChoice(not missing and not forbidden, used, missing, forbidden)


@dataclass(frozen=True)
class Expect:
    """An expected number; ``alternatives`` are other readings of the question that are also
    right (for example comments with and without spam)."""

    value: float
    alternatives: tuple[float, ...] = ()
    label: str = ""

    @property
    def values(self) -> tuple[float, ...]:
        return (self.value, *self.alternatives)


def matches(written: Number, expected: float) -> bool:
    """The answer's number is the expected one as people write it: exact, or rounded to the
    precision written (69 or 69.2 for 69.23), or 4.1k for 4,125."""
    target = Decimal(str(expected))
    return abs(written.value - target) <= written.precision / 2


@dataclass(frozen=True)
class ExactNumbers:
    expected: list[str]
    missing: list[str]

    @property
    def passed(self) -> bool:
        return not self.missing


def exact_numbers(answer: str, expected: Sequence[Expect]) -> ExactNumbers:
    written = numbers(strip_noise(normalise(answer)))
    missing = [
        e.label or f"{e.value:g}"
        for e in expected
        if not any(matches(n, v) for n in written for v in e.values)
    ]
    return ExactNumbers([e.label or f"{e.value:g}" for e in expected], missing)


@dataclass(frozen=True)
class Citations:
    markers: list[int]
    invalid: list[int]  # numbers with no answer_ref
    stray: list[str] = field(default_factory=list)  # "[summary]", "[1-3]", "[]": not citations

    @property
    def passed(self) -> bool:
        return not self.invalid and not self.stray


# Anything in square brackets that isn't a citation ("[3]", "[1, 2]") or a markdown link text.
BRACKETED = re.compile(r"\[[^\[\]\n]{0,400}\](?!\()")


def citations(answer: str, refs: Sequence[Any]) -> Citations:
    """Every [n] (or [1, 2]) points at an answer_ref, and brackets hold nothing else: the report
    turns only numeric markers into links, so "[summary]" or "[1-3]" would show as written."""
    markers = [
        int(part)
        for match in CITATION.finditer(answer)
        for part in match.group(0).strip("[]").split(",")
    ]
    stray = [m.group(0) for m in BRACKETED.finditer(answer) if not CITATION.fullmatch(m.group(0))]
    return Citations(markers, [n for n in markers if not 1 <= n <= len(refs)], _dedupe(stray))


def card_kind(cards: Sequence[Mapping[str, Any]], expected: str | None) -> bool:
    """The run produced a card of the expected kind (no expectation: anything goes)."""
    return expected is None or any(c.get("kind") == expected for c in cards)


def text_expectations(answer: str, patterns: Sequence[str]) -> list[str]:
    """The regexes (case-insensitive) the answer doesn't match."""
    return [p for p in patterns if not re.search(p, answer, re.IGNORECASE | re.DOTALL)]


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
