"""Runs Ask Social Hood's eval set (TA.6; agent-architecture.html §18) against the real model.

For each case (tests/evals/cases.py), in order, one at a time:

1. the run is created the way POST …/agent/runs creates it (services/agent_runs.create, the
   workspace's policy, the credit check) for the member the case names, and committed;
2. run_agent's body runs it in process (agent/orchestrator.run): the Pydantic AI planner on
   Gemini (``settings.ai_model_agent`` or the reply model), the registered R1 tools, metering on
   the seed's Max plan, with the clock at the seed's ``NOW`` (time-machine, ticking);
3. the stored run and steps are read back and checked (tests/evals/checks.py).

A run that fails because the model didn't answer (a 429 or a 5xx after the planner's own retry)
is run again after a backoff. Tools that call AI (draft_reply, answer_from_knowledge) use Gemini
too; embeddings use the fake provider's bag of words, like the seeded knowledge chunks.

The JSON and markdown reports go to tests/evals/results/ (gitignored). ``python
scripts/agent_eval.py`` is the command line; test_agent_eval.py the opt-in pytest.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import time_machine
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from socialhood.agent import orchestrator, planner
from socialhood.ai.fake import FakeProvider
from socialhood.ai.gemini import GeminiProvider
from socialhood.ai.provider import AIResult, EmbedKind, M, Turn
from socialhood.ai.registry import use_provider
from socialhood.auth.deps import WorkspaceContext
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.identity import Role, User, Workspace
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.agent import AgentRunCreate
from socialhood.services import agent_runs
from socialhood.settings import Settings
from tests.evals import checks
from tests.evals import seed as S
from tests.evals.cases import CASES, Case

RESULTS = Path(__file__).parent / "results"
# TA.6 (agent-architecture.html §18): at least 90% correct tool choice, every number equal to the
# database, no invented number.
TARGETS = {"tool_choice": 90.0, "exact_numbers": 100.0, "grounding": 100.0}
RETRY_CODES = frozenset({"ai_unavailable"})
BACKOFF_S = (20.0, 60.0, 120.0)
# Bag-of-words similarities run lower than Gemini's embeddings; 0.35 keeps the FAQ a question
# is about and drops the others (the seeded chunks and the queries are embedded the same way).
EVAL_RETRIEVAL_MIN_SIM = "0.35"


class EvalProvider:
    """Gemini for text and JSON (drafted replies, knowledge answers); the fake's bag-of-words
    embedding, which the seed used for the knowledge chunks."""

    def __init__(self, settings: Settings) -> None:
        self.gemini = GeminiProvider(settings)
        self.fake = FakeProvider()

    async def generate_json(
        self,
        *,
        task: str,
        schema: type[M],
        system: str,
        contents: list[Turn],
        model: str,
        max_output_tokens: int,
        temperature: float,
        timeout_s: float,
    ) -> AIResult[M]:
        return await self.gemini.generate_json(
            task=task,
            schema=schema,
            system=system,
            contents=contents,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )

    async def generate_text(
        self,
        *,
        task: str,
        system: str,
        contents: list[Turn],
        model: str,
        max_output_tokens: int,
        temperature: float,
        timeout_s: float,
    ) -> AIResult[str]:
        return await self.gemini.generate_text(
            task=task,
            system=system,
            contents=contents,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            timeout_s=timeout_s,
        )

    async def embed(self, texts: list[str], *, kind: EmbedKind) -> list[list[float]]:
        return await self.fake.embed(texts, kind=kind)


# ---------------------------------------------------------------- what a run left


@dataclass
class StepRecord:
    ordinal: int
    kind: str
    tool: str | None
    status: str
    args: dict[str, Any]
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None


@dataclass
class RunRecord:
    run_id: str
    status: str
    answer: str | None
    answer_refs: list[dict[str, Any]]
    error_code: str | None
    error_message: str | None
    credits: int | None
    input_tokens: int | None
    output_tokens: int | None
    model: str | None
    prompt_version: str | None
    steps: list[StepRecord]
    latency_ms: int
    attempts: int = 1

    @property
    def tools(self) -> list[str]:
        return [s.tool for s in self.steps if s.kind == "tool" and s.tool]

    @property
    def cards(self) -> list[dict[str, Any]]:
        return [
            s.result["action_card"]
            for s in self.steps
            if s.kind == "tool"
            and s.status == "succeeded"
            and s.result is not None
            and isinstance(s.result.get("action_card"), dict)
        ]

    @property
    def evidence(self) -> list[Any]:
        """What the model was shown: each succeeded step's result, each failed step's reason."""
        shown: list[Any] = []
        for s in self.steps:
            if s.kind != "tool":
                continue
            if s.status == "succeeded" and s.result is not None:
                shown.append(s.result)
            elif s.error_message:
                shown.append(s.error_message)
        return shown


def _failed_record(run_id: uuid.UUID | None, code: str, message: str, latency: int) -> RunRecord:
    return RunRecord(
        run_id=str(run_id) if run_id else "",
        status="failed",
        answer=None,
        answer_refs=[],
        error_code=code,
        error_message=message,
        credits=None,
        input_tokens=None,
        output_tokens=None,
        model=None,
        prompt_version=None,
        steps=[],
        latency_ms=latency,
    )


async def load_record(engine: AsyncEngine, run_id: uuid.UUID, latency_ms: int) -> RunRecord:
    async with engine.connect() as conn:
        run = (
            (
                await conn.execute(
                    text(
                        "SELECT status, answer, answer_refs, error_code, error_message, credits,"
                        " input_tokens, output_tokens, model, prompt_version"
                        " FROM agent_runs WHERE id = :id"
                    ),
                    {"id": run_id},
                )
            )
            .mappings()
            .one()
        )
        steps = (
            (
                await conn.execute(
                    text(
                        "SELECT ordinal, kind, tool, status, args, result, error_code,"
                        " error_message FROM agent_steps WHERE run_id = :id ORDER BY ordinal"
                    ),
                    {"id": run_id},
                )
            )
            .mappings()
            .all()
        )
    return RunRecord(
        run_id=str(run_id),
        status=run["status"],
        answer=run["answer"],
        answer_refs=list(run["answer_refs"] or []),
        error_code=run["error_code"],
        error_message=run["error_message"],
        credits=run["credits"],
        input_tokens=run["input_tokens"],
        output_tokens=run["output_tokens"],
        model=run["model"],
        prompt_version=run["prompt_version"],
        steps=[StepRecord(**dict(s)) for s in steps],
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------- running one case


@dataclass
class Env:
    engine: AsyncEngine
    redis: Redis
    platform: PlatformDeps
    provider: EvalProvider
    seeded: S.Seeded
    log: Callable[[str], None] = print


async def _run_once(env: Env, case: Case) -> RunRecord:
    maker = make_sessionmaker(env.engine)
    wid = env.seeded.workspace_id
    run_id: uuid.UUID | None = None
    started = time.monotonic()
    with time_machine.travel(S.NOW, tick=True), workspace_scope(wid):
        try:
            async with maker() as session:
                workspace = await session.get(Workspace, wid)
                user = await session.get(User, env.seeded.users[case.role])
                assert workspace is not None
                assert user is not None
                ctx = WorkspaceContext(workspace=workspace, role=Role(case.role), user=user)
                row = await agent_runs.create(session, ctx, AgentRunCreate(request=case.request))
                run_id = row.id
                await commit_and_publish(session, env.redis)
        except ApiError as error:
            return _failed_record(run_id, error.code, error.detail or error.code, 0)
        started = time.monotonic()
        with use_provider(env.provider):
            await orchestrator.run(maker, env.redis, env.platform, run_id=run_id, workspace_id=wid)
    return await load_record(env.engine, run_id, round((time.monotonic() - started) * 1000))


async def run_case(env: Env, case: Case) -> RunRecord:
    """One case, run again after a backoff while the model is unavailable."""
    for attempt in range(1, len(BACKOFF_S) + 2):
        record = await _run_once(env, case)
        record.attempts = attempt
        if record.status != "failed" or record.error_code not in RETRY_CODES:
            return record
        if attempt <= len(BACKOFF_S):
            wait = BACKOFF_S[attempt - 1]
            env.log(
                f"  {case.id}: the model didn't answer ({record.error_code}); again in {wait:g}s"
            )
            await asyncio.sleep(wait)
    return record


# ---------------------------------------------------------------- checking one case


@dataclass
class CaseResult:
    case: Case
    record: RunRecord
    tool_choice: checks.ToolChoice
    grounding: checks.Grounding
    exact: checks.ExactNumbers | None
    citations: checks.Citations
    card_ok: bool
    text_missing: list[str]

    @property
    def answered(self) -> bool:
        return self.record.status in ("succeeded", "partial") and bool(self.record.answer)

    @property
    def failures(self) -> list[str]:
        found = []
        if not self.answered:
            found.append("no_answer")
        if not self.tool_choice.passed:
            found.append("tool_choice")
        if not self.grounding.passed:
            found.append("grounding")
        if self.exact is not None and not self.exact.passed:
            found.append("exact_numbers")
        if not self.citations.passed:
            found.append("citations")
        if not self.card_ok:
            found.append("card")
        if self.text_missing:
            found.append("text")
        return found

    @property
    def passed(self) -> bool:
        return not self.failures


def evaluate(case: Case, record: RunRecord) -> CaseResult:
    answer = record.answer or ""
    pool = checks.pool_of(record.evidence, request=case.request, now=S.NOW, timezone=S.TZ)
    drafts = [
        text
        for s in record.steps
        if s.kind == "tool" and s.status == "succeeded" and s.tool
        for text in checks.drafted_texts(s.tool, s.args)
    ]
    return CaseResult(
        case=case,
        record=record,
        tool_choice=checks.tool_choice(record.tools, case.expect_tools, case.forbid_tools),
        grounding=checks.ground_run(answer, drafts, pool),
        exact=checks.exact_numbers(answer, case.expect_numbers) if case.expect_numbers else None,
        citations=checks.citations(answer, record.answer_refs),
        card_ok=checks.card_kind(record.cards, case.expect_card),
        text_missing=checks.text_expectations(answer, case.expect_text),
    )


# ---------------------------------------------------------------- totals


@dataclass
class Summary:
    label: str
    model: str
    prompt_version: str
    started_at: str
    cases: int
    answered: int
    passed: int
    tool_choice: float
    grounding: float
    exact_numbers: float
    citations: float
    cards: float
    text: float
    avg_credits: float
    avg_latency_ms: float
    p95_latency_ms: float
    failures: dict[str, list[str]] = field(default_factory=dict)

    def meets_targets(self) -> dict[str, bool]:
        return {name: getattr(self, name) >= target for name, target in TARGETS.items()}


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 100.0


def summarise(results: Sequence[CaseResult], *, label: str, model: str, started: str) -> Summary:
    answered = [r for r in results if r.answered]
    with_numbers = [r for r in results if r.exact is not None]
    with_cards = [r for r in results if r.case.expect_card]
    with_text = [r for r in results if r.case.expect_text]
    latencies = sorted(r.record.latency_ms for r in results)
    credits = [r.record.credits or 0 for r in results]
    failures: dict[str, list[str]] = {}
    for r in results:
        for name in r.failures:
            failures.setdefault(name, []).append(r.case.id)
    versions = {r.record.prompt_version for r in results if r.record.prompt_version}
    return Summary(
        label=label,
        model=model,
        prompt_version=", ".join(sorted(versions)) or "?",
        started_at=started,
        cases=len(results),
        answered=len(answered),
        passed=sum(1 for r in results if r.passed),
        tool_choice=_pct(sum(1 for r in results if r.tool_choice.passed), len(results)),
        grounding=_pct(sum(1 for r in answered if r.grounding.passed), len(answered)),
        exact_numbers=_pct(
            sum(1 for r in with_numbers if r.exact and r.exact.passed), len(with_numbers)
        ),
        citations=_pct(sum(1 for r in answered if r.citations.passed), len(answered)),
        cards=_pct(sum(1 for r in with_cards if r.card_ok), len(with_cards)),
        text=_pct(sum(1 for r in with_text if not r.text_missing), len(with_text)),
        avg_credits=round(sum(credits) / len(credits), 2) if credits else 0.0,
        avg_latency_ms=round(sum(latencies) / len(latencies)) if latencies else 0.0,
        p95_latency_ms=(
            latencies[max(math.ceil(len(latencies) * 0.95) - 1, 0)] if latencies else 0.0
        ),
        failures=failures,
    )


# ---------------------------------------------------------------- reports


def _case_json(r: CaseResult) -> dict[str, Any]:
    c, rec = r.case, r.record
    return {
        "id": c.id,
        "area": c.area,
        "lang": c.lang,
        "role": c.role,
        "request": c.request,
        "passed": r.passed,
        "failures": r.failures,
        "status": rec.status,
        "error_code": rec.error_code,
        "tools": rec.tools,
        "steps": [
            {
                "tool": s.tool,
                "args": s.args,
                "status": s.status,
                "error": s.error_message,
                "result": s.result,
            }
            for s in rec.steps
            if s.kind == "tool"
        ],
        "expect_tools": sorted(c.expect_tools),
        "forbid_tools": sorted(c.forbid_tools),
        "tool_choice_missing": r.tool_choice.missing,
        "tool_choice_forbidden": r.tool_choice.forbidden,
        "numbers_checked": r.grounding.checked,
        "flagged_numbers": r.grounding.flagged,
        "expected_numbers": r.exact.expected if r.exact else [],
        "missing_numbers": r.exact.missing if r.exact else [],
        "invalid_citations": r.citations.invalid,
        "stray_brackets": r.citations.stray,
        "cards": [card.get("kind") for card in rec.cards],
        "expect_card": c.expect_card,
        "text_missing": r.text_missing,
        "answer": rec.answer,
        "answer_refs": rec.answer_refs,
        "credits": rec.credits,
        "latency_ms": rec.latency_ms,
        "attempts": rec.attempts,
        "run_id": rec.run_id,
    }


def _summary_lines(s: Summary) -> list[str]:
    met = s.meets_targets()
    return [
        f"- Cases: {s.cases} ({s.answered} answered, {s.passed} passed every check)",
        f"- Tool choice: {s.tool_choice}% (target {TARGETS['tool_choice']:g}%: "
        f"{'met' if met['tool_choice'] else 'missed'})",
        f"- Grounding (no invented number): {s.grounding}% of answers (target 100%: "
        f"{'met' if met['grounding'] else 'missed'})",
        f"- Exact numbers: {s.exact_numbers}% of cases with expected numbers (target 100%: "
        f"{'met' if met['exact_numbers'] else 'missed'})",
        f"- Citations valid: {s.citations}%",
        f"- Action cards: {s.cards}%",
        f"- Honest-answer text: {s.text}%",
        f"- Credits per run: {s.avg_credits} on average",
        f"- Latency: {s.avg_latency_ms / 1000:.1f} s average, {s.p95_latency_ms / 1000:.1f} s p95",
    ]


def markdown(summary: Summary, results: Sequence[CaseResult]) -> str:
    lines = [
        f"# Agent eval: {summary.label}",
        "",
        f"Model {summary.model}, prompt {summary.prompt_version}, run {summary.started_at}; "
        f"clock pinned to {S.NOW.astimezone(S.TZ):%a %d %b %Y %H:%M} {S.TIMEZONE}.",
        "",
        *_summary_lines(summary),
        "",
        "## Failures by check",
        "",
    ]
    if summary.failures:
        lines += [f"- {name}: {', '.join(ids)}" for name, ids in sorted(summary.failures.items())]
    else:
        lines.append("None.")
    lines += ["", "## Cases", ""]
    for r in results:
        c, rec = r.case, r.record
        verdict = "PASS" if r.passed else "FAIL (" + ", ".join(r.failures) + ")"
        lines += [
            f"### {c.id}: {verdict}",
            "",
            f"- Request ({c.lang}, {c.role}): {c.request}",
            f"- Tools called: {', '.join(rec.tools) or 'none'} "
            f"(acceptable: {', '.join(sorted(c.expect_tools)) or 'any'}"
            + (f"; forbidden: {', '.join(sorted(c.forbid_tools))}" if c.forbid_tools else "")
            + ")",
        ]
        for s in rec.steps:
            if s.kind == "tool":
                args = json.dumps(s.args, ensure_ascii=False)
                note = f" failed: {s.error_message}" if s.status == "failed" else ""
                lines.append(f"  - {s.tool} {args}{note}")
        if r.grounding.flagged:
            lines.append(f"- Flagged numbers: {', '.join(r.grounding.flagged)}")
        if r.exact is not None:
            lines.append(
                f"- Expected numbers: {', '.join(r.exact.expected)}"
                + (f"; missing: {', '.join(r.exact.missing)}" if r.exact.missing else "")
            )
        if c.expect_card:
            lines.append(
                f"- Card: expected {c.expect_card}, got "
                f"{', '.join(str(card.get('kind')) for card in rec.cards) or 'none'}"
            )
        if r.text_missing:
            lines.append(f"- Missing text: {' | '.join(r.text_missing)}")
        if r.citations.invalid:
            lines.append(f"- Invalid citations: {r.citations.invalid}")
        if r.citations.stray:
            lines.append(f"- Brackets that aren't citations: {' '.join(r.citations.stray)}")
        lines.append(
            f"- Status {rec.status}"
            + (f" ({rec.error_code})" if rec.error_code else "")
            + f", {rec.credits} credits, {rec.latency_ms / 1000:.1f} s"
            + (f", {rec.attempts} attempts" if rec.attempts > 1 else "")
        )
        lines += ["", "> " + (rec.answer or "(no answer)").replace("\n", "\n> "), ""]
    return "\n".join(lines) + "\n"


def write_reports(
    summary: Summary, results: Sequence[CaseResult], out: Path = RESULTS
) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    name = f"agent-eval-{stamp}-{summary.label}"
    as_json = out / f"{name}.json"
    as_md = out / f"{name}.md"
    as_json.write_text(
        json.dumps(
            {
                "summary": summary.__dict__,
                "targets": TARGETS,
                "cases": [_case_json(r) for r in results],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    as_md.write_text(markdown(summary, results), encoding="utf-8")
    return as_json, as_md


# ---------------------------------------------------------------- the whole eval


async def run_eval(
    settings: Settings,
    *,
    cases: Sequence[Case] = CASES,
    delay_s: float = 2.0,
    label: str = "eval",
    out: Path | None = RESULTS,
    log: Callable[[str], None] = print,
) -> tuple[Summary, list[CaseResult]]:
    """Seed the eval database fresh, run the cases, check them; write the reports when ``out``
    is given. Needs a migrated database (tests or scripts/agent_eval.py migrate it)."""
    engine = create_async_engine(settings.database_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    results: list[CaseResult] = []
    try:
        await redis.flushdb()
        await S.wipe(engine)
        seeded = await S.seed(engine)
        log(f"Seeded workspace {seeded.workspace_id}; running {len(cases)} cases")
        async with httpx.AsyncClient() as http:
            env = Env(
                engine=engine,
                redis=redis,
                platform=deps_from(http, settings),
                provider=EvalProvider(settings),
                seeded=seeded,
                log=log,
            )
            for i, case in enumerate(cases, 1):
                record = await run_case(env, case)
                result = evaluate(case, record)
                results.append(result)
                verdict = "pass" if result.passed else "FAIL " + ",".join(result.failures)
                log(
                    f"[{i}/{len(cases)}] {case.id}: {verdict} "
                    f"({', '.join(record.tools) or 'no tools'}; {record.latency_ms / 1000:.1f}s)"
                )
                if i < len(cases):
                    await asyncio.sleep(delay_s)
    finally:
        await redis.aclose()
        await engine.dispose()
    summary = summarise(results, label=label, model=planner.model_name(settings), started=started)
    if out is not None:
        paths = write_reports(summary, results, out)
        log(f"Reports: {paths[0]} and {paths[1]}")
    for line in _summary_lines(summary):
        log(line)
    return summary, results
