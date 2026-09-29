"""The AI evaluation harness (T5.9; TR-AI-10). Not part of the pytest suite: it calls the model.

    cd apps/api
    uv run python -m tests.ai_eval.run            # Gemini, with the models in .env
    uv run python -m tests.ai_eval.run --fake     # the FakeProvider: checks the harness only

It reads two datasets next to this file:

- ``messages.jsonl``: one customer message per line with its conversation and the owner's labels
  for intent, sentiment and needs_human. It runs the analysis prompt (analysis.v1, as the analysis
  job builds it) and prints per-class intent accuracy, the intent confusion matrix, sentiment
  accuracy and needs_human precision and recall.
- ``suggestions.jsonl``: questions with the knowledge they need and the facts a correct answer must
  contain (``answerable: false`` when the knowledge lacks the answer). It runs the suggestion prompt
  (suggest.v1) and prints answer accuracy, the fabrication rate (answers stating a price, number,
  link, email or phone number that is not in the knowledge, or answering an unanswerable
  question) and the auto-policy pass rate (the checks of TR-AI-07 that depend on the draft alone:
  can_answer, confidence >= AUTO_MIN_CONFIDENCE, the output filter and the length).

Both are JSON Lines; lines starting with ``//`` are comments. The seed files are synthetic
placeholders (``"placeholder": true``) until the owner's 300 labelled
messages (T5.9, including Hinglish) and 50 knowledge questions replace them. Run it before changing
a model or a prompt version and record the results in docs/ai-eval-log.md (``--markdown`` prints the
table row). Members' corrections (FR-AI-04) are exported with ``tests.ai_eval.export_corrections``;
anonymise them before adding them here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from socialhood.ai import prompts
from socialhood.ai.provider import AIError, AIProvider, Turn
from socialhood.models.inbox import Direction, Message
from socialhood.services.analysis import (
    MAX_OUTPUT_TOKENS,
    TIMEOUT_S,
    AnalysisOut,
    transcript,
)
from socialhood.settings import Settings

HERE = Path(__file__).parent
DEFAULTS = Settings.model_fields
KNOWLEDGE_IDS = 6  # TR-AI-06: k1…k6
REPLY_LIMIT = 1_000  # TR-AI-07 check 13
FACT = re.compile(
    r"https?://\S+|www\.\S+|[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s-]{6,}\d|[₹$€£]\s?\d[\d,.]*|\d+(?:[.,]\d+)?"
)


class SuggestionOut(BaseModel):
    """TR-AI-06's SuggestionOut (mirrors the suggestion job's schema)."""

    can_answer: bool
    reply: str | None
    missing_info: str | None
    missing_topic: str | None
    confidence: float
    used_source_ids: list[str]


# ---------------------------------------------------------------- datasets


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip() and not line.lstrip().startswith("//"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise SystemExit(f"{path.name}:{number}: {error}") from error
    return rows


def as_messages(case: dict[str, Any]) -> tuple[list[Message], uuid.UUID]:
    """The case's conversation as transient message rows (nothing touches the database)."""
    rows: list[Message] = []
    for turn in [*case.get("context", []), {"from": "customer", "text": case["text"]}]:
        rows.append(
            Message(
                id=uuid.uuid4(),
                direction=Direction.INBOUND if turn["from"] == "customer" else Direction.OUTBOUND,
                kind="text",
                text=turn["text"],
                occurred_at=datetime.now(UTC),
            )
        )
    return rows, rows[-1].id


# ---------------------------------------------------------------- metrics


@dataclass
class ClassReport:
    labels: list[tuple[str, str]] = field(default_factory=list)  # (expected, predicted)

    def add(self, expected: str, predicted: str) -> None:
        self.labels.append((expected, predicted))

    @property
    def accuracy(self) -> float:
        return _ratio(sum(e == p for e, p in self.labels), len(self.labels))

    def per_class(self) -> dict[str, tuple[int, int, float]]:
        """Class -> (correct, total, accuracy), by the expected label."""
        totals: Counter[str] = Counter(e for e, _ in self.labels)
        correct: Counter[str] = Counter(e for e, p in self.labels if e == p)
        return {c: (correct[c], totals[c], _ratio(correct[c], totals[c])) for c in sorted(totals)}

    def confusion(self) -> dict[str, Counter[str]]:
        matrix: dict[str, Counter[str]] = defaultdict(Counter)
        for expected, predicted in self.labels:
            matrix[expected][predicted] += 1
        return matrix


@dataclass
class BinaryReport:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def add(self, expected: bool, predicted: bool) -> None:
        if expected and predicted:
            self.tp += 1
        elif predicted:
            self.fp += 1
        elif expected:
            self.fn += 1
        else:
            self.tn += 1

    @property
    def precision(self) -> float:
        return _ratio(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float:
        return _ratio(self.tp, self.tp + self.fn)


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def facts(text: str) -> set[str]:
    """Prices, numbers, links, emails and phone numbers in a text, normalised (no spaces,
    separators or currency signs, so "₹1,499" and "1499" are the same fact)."""
    return {re.sub(r"[\s,₹$€£-]", "", match).rstrip(".").casefold() for match in FACT.findall(text)}


def fabricated(reply: str, knowledge: str) -> bool:
    """A fact in the reply that is not in the knowledge (TR-AI-10's fabrication)."""
    return not facts(reply) <= facts(knowledge)


def passes_auto_policy(out: SuggestionOut, knowledge: str, min_confidence: float) -> bool:
    """TR-AI-07 checks 9, 10 and 13; the others need a conversation's state."""
    if not out.can_answer or not out.reply or out.confidence < min_confidence:
        return False
    return len(out.reply) <= REPLY_LIMIT and not fabricated(out.reply, knowledge)


# ---------------------------------------------------------------- runs


@dataclass
class MessageResults:
    intent: ClassReport = field(default_factory=ClassReport)
    sentiment: ClassReport = field(default_factory=ClassReport)
    needs_human: BinaryReport = field(default_factory=BinaryReport)
    errors: int = 0


@dataclass
class SuggestionResults:
    cases: int = 0
    answered: int = 0
    correct: int = 0
    answerable: int = 0
    fabricated: int = 0
    auto_pass: int = 0
    errors: int = 0


async def run_messages(
    provider: AIProvider, cases: Sequence[dict[str, Any]], *, model: str, business: tuple[str, str]
) -> MessageResults:
    prompt = prompts.load("analysis")
    system = prompt.render(business_name=business[0], business_description=business[1])
    results = MessageResults()
    for case in cases:
        rows, target = as_messages(case)
        try:
            answer = await provider.generate_json(
                task="analysis",
                schema=AnalysisOut,
                system=system,
                contents=[Turn("user", transcript(rows, target))],
                model=model,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.0,
                timeout_s=TIMEOUT_S,
            )
        except AIError as error:
            print(f"  {case.get('id')}: {error.code}", file=sys.stderr)
            results.errors += 1
            continue
        labels, out = case["labels"], answer.value
        results.intent.add(labels["intent"], out.intent)
        results.sentiment.add(labels["sentiment"], out.sentiment)
        results.needs_human.add(bool(labels["needs_human"]), out.needs_human)
    return results


def knowledge_block(knowledge: Iterable[dict[str, str]]) -> str:
    lines = [
        f"[k{n}] ({item['title']}) {item['text']}"
        for n, item in enumerate(list(knowledge)[:KNOWLEDGE_IDS], start=1)
    ]
    return "KNOWLEDGE:\n" + ("\n".join(lines) if lines else "(none)")


async def run_suggestions(
    provider: AIProvider,
    cases: Sequence[dict[str, Any]],
    *,
    model: str,
    business: tuple[str, str],
    min_confidence: float,
) -> SuggestionResults:
    prompt = prompts.load("suggest")
    results = SuggestionResults()
    for case in cases:
        system = prompt.render(
            business_name=business[0],
            business_description=business[1],
            platform="Instagram",
            tone="friendly",
            emoji_policy="light",
            do_list="none",
            dont_list="none",
            sign_off="none",
            language=case.get("language", "en"),
            automation_instructions="",
        )
        rows, target = as_messages({"text": case["question"], "context": case.get("context", [])})
        knowledge = knowledge_block(case.get("knowledge", []))
        try:
            answer = await provider.generate_json(
                task="suggest",
                schema=SuggestionOut,
                system=system,
                contents=[Turn("user", f"{knowledge}\n\n{transcript(rows, target)}")],
                model=model,
                max_output_tokens=600,
                temperature=0.4,
                timeout_s=12,
            )
        except AIError as error:
            print(f"  {case.get('id')}: {error.code}", file=sys.stderr)
            results.errors += 1
            continue
        out = answer.value
        results.cases += 1
        answerable = bool(case.get("answerable", True))
        results.answerable += answerable
        if out.can_answer and out.reply:
            results.answered += 1
            made_up = not answerable or fabricated(out.reply, knowledge)
            results.fabricated += made_up
            must = [m.casefold() for m in case.get("must_contain", [])]
            results.correct += answerable and all(m in out.reply.casefold() for m in must)
        results.auto_pass += passes_auto_policy(out, knowledge, min_confidence)
    return results


# ---------------------------------------------------------------- output


def print_messages(results: MessageResults) -> None:
    print(
        f"\nIntent accuracy: {results.intent.accuracy:.1%} ({len(results.intent.labels)} messages)"
    )
    for label, (correct, total, accuracy) in results.intent.per_class().items():
        print(f"  {label:<16} {correct:>4}/{total:<4} {accuracy:6.1%}")
    matrix = results.intent.confusion()
    predicted = sorted({p for row in matrix.values() for p in row})
    if predicted:
        print("\nConfusion matrix (rows: expected, columns: predicted)")
        print(" " * 17 + " ".join(f"{p[:8]:>8}" for p in predicted))
        for expected in sorted(matrix):
            cells = " ".join(f"{matrix[expected][p]:>8}" for p in predicted)
            print(f"  {expected:<15}{cells}")
    print(f"\nSentiment accuracy: {results.sentiment.accuracy:.1%}")
    nh = results.needs_human
    print(f"needs_human precision {nh.precision:.1%}, recall {nh.recall:.1%}")
    if results.errors:
        print(f"Errors: {results.errors}")


def print_suggestions(results: SuggestionResults) -> None:
    print(f"\nSuggestions: {results.cases} ({results.answered} answered)")
    print(f"Answer accuracy: {_ratio(results.correct, results.answerable):.1%} of answerable")
    print(f"Fabrication rate: {_ratio(results.fabricated, results.answered):.1%} of answers")
    print(f"Auto-policy pass rate: {_ratio(results.auto_pass, results.cases):.1%}")
    if results.errors:
        print(f"Errors: {results.errors}")


def markdown_row(model: str, m: MessageResults, s: SuggestionResults) -> str:
    today = datetime.now(UTC).date().isoformat()
    return (
        f"| {today} | {model} | {prompts.load('analysis').version}, "
        f"{prompts.load('suggest').version} | {m.intent.accuracy:.1%} | "
        f"{m.sentiment.accuracy:.1%} | {m.needs_human.recall:.1%} | "
        f"{_ratio(s.fabricated, s.answered):.1%} | {_ratio(s.auto_pass, s.cases):.1%} | |"
    )


# ---------------------------------------------------------------- main


def _provider(fake: bool) -> tuple[AIProvider, Settings | None]:
    if fake:
        from socialhood.ai.fake import FakeProvider

        return FakeProvider(), None
    from socialhood.ai.gemini import GeminiProvider
    from socialhood.settings import get_settings

    settings = get_settings()
    return GeminiProvider(settings), settings


async def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fake", action="store_true", help="use the FakeProvider")
    parser.add_argument("--messages", type=Path, default=HERE / "messages.jsonl")
    parser.add_argument("--suggestions", type=Path, default=HERE / "suggestions.jsonl")
    parser.add_argument("--limit", type=int, default=None, help="first N cases of each file")
    parser.add_argument("--business", default="Maple Boutique")
    parser.add_argument(
        "--description", default="A clothing and jewellery shop in Pune that sells on Instagram."
    )
    parser.add_argument("--markdown", action="store_true", help="print a docs/ai-eval-log.md row")
    args = parser.parse_args(argv)

    provider, settings = _provider(args.fake)
    analysis_model = (
        settings.ai_model_analysis if settings else DEFAULTS["ai_model_analysis"].default
    )
    reply_model = settings.ai_model_reply if settings else DEFAULTS["ai_model_reply"].default
    min_confidence = (
        settings.auto_min_confidence if settings else DEFAULTS["auto_min_confidence"].default
    )
    messages = load_jsonl(args.messages)[: args.limit]
    suggestions = load_jsonl(args.suggestions)[: args.limit]
    if any(case.get("placeholder") for case in [*messages, *suggestions]):
        print("Note: the datasets contain synthetic placeholders, not the owner's labels.")
    business = (args.business, args.description)

    print(f"Analysis: {len(messages)} messages with {analysis_model}")
    message_results = await run_messages(
        provider, messages, model=analysis_model, business=business
    )
    print_messages(message_results)
    print(f"\nSuggestions: {len(suggestions)} questions with {reply_model}")
    suggestion_results = await run_suggestions(
        provider,
        suggestions,
        model=reply_model,
        business=business,
        min_confidence=min_confidence,
    )
    print_suggestions(suggestion_results)
    if args.markdown:
        print("\n" + markdown_row(analysis_model, message_results, suggestion_results))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
