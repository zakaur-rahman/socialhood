"""The report's citations and the answer a run gives when it stops early (TA.2; FR-AGT-01,
FR-AGT-04, FR-AGT-06; agent-architecture.html §9 Report, §15).

Citations. Every record a tool result names (``ToolResult.refs``) goes into the run's ``RefBook``
in the order the steps ran, numbered from 1, and the model sees each ref with its number (``n``).
The model cites with ``[n]``; ``cite`` then keeps only the records the answer cites, renumbers
them 1, 2, … in order of first use (so ``[n]`` in the stored answer is item n of answer_refs) and
drops a marker that points at no record: an answer can only cite what a tool returned. The
numbering is a function of the stored steps alone, so a resumed run numbers the same way.

Stopping early. Past a cap (tool calls, model turns, credits, wall time) or when the credits run
out, no model writes the answer: ``fallback_answer`` lists what the finished steps found, in
their own words and with their citations, and which data couldn't be fetched (FR-AGT-06).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from socialhood.schemas.agent import AnswerRef

# "[3]", "[1, 2]" and "[1][2]" (two markers); a leading space goes with a dropped marker.
CITATION = re.compile(r"(\s?)\[(\s*\d{1,3}(?:\s*,\s*\d{1,3})*\s*)\]")
REPEATED = re.compile(r"(\[\d{1,3}\])\1+")  # "[2][2]" once renumbered
FALLBACK_REFS_PER_STEP = 3


class RefBook:
    """The records a run's tool results named, numbered from 1 in the order they came."""

    def __init__(self) -> None:
        self.refs: list[AnswerRef] = []
        self._numbers: dict[tuple[str, uuid.UUID], int] = {}

    def add(self, refs: Iterable[AnswerRef]) -> list[int]:
        """Number ``refs`` (a record seen before keeps its number); their numbers in order."""
        numbers: list[int] = []
        for ref in refs:
            key = (ref.kind, ref.id)
            number = self._numbers.get(key)
            if number is None:
                self.refs.append(ref)
                number = len(self.refs)
                self._numbers[key] = number
            numbers.append(number)
        return numbers

    def add_stored(self, result: Mapping[str, Any] | None) -> list[int]:
        """Number the refs of a stored step result (``ToolResult`` dumped as JSON)."""
        raw = (result or {}).get("refs") or []
        return self.add(AnswerRef.model_validate(ref) for ref in raw)


def model_view(result: Mapping[str, Any], numbers: Sequence[int]) -> dict[str, Any]:
    """A stored result as the model sees it: each ref carries the number to cite."""
    refs = list(result.get("refs") or [])
    numbered = [{"n": n, **ref} for n, ref in zip(numbers, refs, strict=False)]
    return {**result, "refs": numbered}


def cite(answer: str, book: RefBook) -> tuple[str, list[AnswerRef]]:
    """The answer with its markers renumbered, and answer_refs: the cited records in order of
    first use. Markers that point at no record are removed."""
    renumbered: dict[int, int] = {}
    cited: list[AnswerRef] = []

    def replace(match: re.Match[str]) -> str:
        markers: list[str] = []
        for part in match.group(2).split(","):
            number = int(part)
            if not 1 <= number <= len(book.refs):
                continue
            if number not in renumbered:
                cited.append(book.refs[number - 1])
                renumbered[number] = len(cited)
            marker = f"[{renumbered[number]}]"
            if marker not in markers:
                markers.append(marker)
        return match.group(1) + "".join(markers) if markers else ""

    text = REPEATED.sub(r"\1", CITATION.sub(replace, answer))
    return text.strip(), cited


@dataclass(frozen=True, kw_only=True)
class Found:
    """One finished tool step, for the fallback answer."""

    label: str  # the tool in plain words
    summary: str | None  # the result's summary; None when the step failed
    numbers: list[int] = field(default_factory=list)  # its refs' numbers in the RefBook
    caveats: list[str] = field(default_factory=list)
    error: str | None = None  # why it failed


def fallback_answer(reason: str, found: Sequence[Found]) -> str | None:
    """What the run found before it stopped, in the answer's markdown subset; None when no step
    finished (the run then fails with the reason alone)."""
    if not any(item.summary for item in found):
        return None
    lines = [f"I stopped before finishing because {reason}. Here is what I found so far:", ""]
    for item in found:
        if item.summary:
            markers = "".join(f"[{n}]" for n in item.numbers[:FALLBACK_REFS_PER_STEP])
            lines.append(f"- {item.summary}{' ' + markers if markers else ''}")
            lines.extend(f"- Note: {caveat}" for caveat in item.caveats)
        else:
            detail = f" ({item.error})" if item.error else ""
            lines.append(f"- {item.label}: this data wasn't available{detail}.")
    lines += ["", "Ask again with a narrower question to get a full answer."]
    return "\n".join(lines)
