"""Operator CLI for failed work (TR-OPS-04). Runs from a shell on the worker service:

    python -m socialhood.ops failed-events list [--provider instagram] [--since 2h] [--error-contains …]
    python -m socialhood.ops failed-events replay (--id … | --since 2h [--provider …]) [--dry-run]
    python -m socialhood.ops failed-jobs list [--task analyze_comments] [--since 2h]
    python -m socialhood.ops failed-jobs retry (--id … | --task … --since 2h) [--dry-run]

Every run logs the operator, the filters and the counts (``ops_run``).
"""  # noqa: E501

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import re
import sys
import uuid
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, TextIO

from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.jobs import failed
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.services.webhook_intake import enqueue_processing

log = get_logger("socialhood.ops")

_DURATION = re.compile(r"^(\d+)([smhd])$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def parse_since(value: str, now: datetime | None = None) -> datetime:
    """``90s``, ``30m``, ``2h`` or ``7d`` before now."""
    match = _DURATION.match(value.strip())
    if match is None:
        raise argparse.ArgumentTypeError(f"expected a duration like 30m, 2h or 7d, got {value!r}")
    amount, unit = int(match.group(1)), match.group(2)
    return (now or datetime.now(UTC)) - timedelta(**{_UNITS[unit]: amount})


@dataclass
class Report:
    command: str
    filters: dict[str, Any]
    dry_run: bool = False
    matched: int = 0
    acted: int = 0
    skipped: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    def log(self, operator: str) -> None:
        log.info(
            "ops_run",
            operator=operator,
            command=self.command,
            filters=self.filters,
            dry_run=self.dry_run,
            matched=self.matched,
            acted=self.acted,
            skipped=len(self.skipped),
        )


# ---- failed events


async def list_events(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    provider: str | None,
    since: datetime | None,
    error_contains: str | None,
) -> Report:
    filters = {"provider": provider, "since": _iso(since), "error_contains": error_contains}
    report = Report("failed-events list", filters)
    async with sessionmaker() as session:
        events = await webhook_events.list_failed(
            session, provider=provider, since=since, error_contains=error_contains
        )
    report.matched = len(events)
    for event in events:
        report.lines.append(
            f"{event.id}  {event.provider:<9} {event.event_type:<18} "
            f"{event.received_at:%Y-%m-%d %H:%M}  attempts={event.attempts}  "
            f"{(event.last_error or '')[:120]}"
        )
    return report


async def replay_events(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    ids: list[uuid.UUID] | None,
    provider: str | None,
    since: datetime | None,
    dry_run: bool,
) -> Report:
    """Back to ``received`` with attempts reset, then enqueue. Safe because handlers are
    idempotent (TR-WH-06); an event that was already replayed is no longer ``failed``."""
    filters = {"ids": [str(i) for i in ids or []], "provider": provider, "since": _iso(since)}
    report = Report("failed-events replay", filters, dry_run=dry_run)
    async with sessionmaker() as session:
        events = await webhook_events.list_failed(
            session, ids=ids, provider=provider, since=since, limit=10_000
        )
        report.matched = len(events)
        chosen = [event.id for event in events]
        for event in events:
            report.lines.append(f"{event.id}  {event.provider}  {event.event_type}")
        if dry_run or not chosen:
            return report
        report.acted = await webhook_events.reset_for_replay(session, chosen)
        await session.commit()
    for event_id in chosen:
        # A job may already be waiting for the event (the enqueue is then a no-op), and an enqueue
        # that fails leaves the row ``received`` for sweep_stuck. Either way it gets processed.
        await enqueue_processing(event_id)
    return report


# ---- failed jobs


async def list_jobs(app: App, *, task: str | None, since: datetime | None) -> Report:
    report = Report("failed-jobs list", {"task": task, "since": _iso(since)})
    jobs = await failed.list_failed_jobs(app, task=task, since=since)
    report.matched = len(jobs)
    for job in jobs:
        note = "" if job.retryable_from_ops else "  (not safe to re-run from here)"
        report.lines.append(
            f"{job.id:<8} {job.task_name:<24} {job.queue_name:<11} "
            f"{job.failed_at:%Y-%m-%d %H:%M}  attempts={job.attempts}{note}"
        )
    return report


async def retry_jobs(
    app: App,
    *,
    ids: list[int] | None,
    task: str | None,
    since: datetime | None,
    dry_run: bool,
) -> Report:
    filters = {"ids": ids or [], "task": task, "since": _iso(since)}
    report = Report("failed-jobs retry", filters, dry_run=dry_run)
    jobs = await failed.list_failed_jobs(app, ids=ids, task=task, since=since, limit=10_000)
    report.matched = len(jobs)
    for job in jobs:
        if not job.retryable_from_ops:
            # TR-JOB-05: the platform (or the member's device) may already have it.
            report.skipped.append(f"{job.id} {job.task_name}")
            report.lines.append(f"skip  {job.id}  {job.task_name}: not safe to re-run")
            continue
        report.lines.append(f"{'would retry' if dry_run else 'retry'}  {job.id}  {job.task_name}")
        if not dry_run:
            await failed.retry_now(app, job)
            report.acted += 1
    return report


# ---- command line


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _operator() -> str:
    for name in ("SOCIALHOOD_OPERATOR", "RENDER_SERVICE_NAME"):
        if os.environ.get(name):
            return os.environ[name]
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m socialhood.ops")
    parser.add_argument("--operator", default=None, help="who is running this (logged)")
    groups = parser.add_subparsers(dest="group", required=True)

    events = groups.add_parser("failed-events").add_subparsers(dest="action", required=True)
    ev_list = events.add_parser("list")
    ev_list.add_argument("--provider")
    ev_list.add_argument("--since", type=parse_since)
    ev_list.add_argument("--error-contains")
    ev_replay = events.add_parser("replay")
    ev_replay.add_argument("--id", dest="ids", action="append", type=uuid.UUID)
    ev_replay.add_argument("--since", type=parse_since)
    ev_replay.add_argument("--provider")
    ev_replay.add_argument("--dry-run", action="store_true")

    jobs = groups.add_parser("failed-jobs").add_subparsers(dest="action", required=True)
    jb_list = jobs.add_parser("list")
    jb_list.add_argument("--task")
    jb_list.add_argument("--since", type=parse_since)
    jb_retry = jobs.add_parser("retry")
    jb_retry.add_argument("--id", dest="ids", action="append", type=int)
    jb_retry.add_argument("--task")
    jb_retry.add_argument("--since", type=parse_since)
    jb_retry.add_argument("--dry-run", action="store_true")
    return parser


def _validate(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    # Bulk actions need a time window, so a bare command never replays the whole history.
    command = (args.group, args.action)
    if command == ("failed-events", "replay") and not args.ids and args.since is None:
        parser.error("replay needs --id or --since")
    if (
        command == ("failed-jobs", "retry")
        and not args.ids
        and not (args.task and args.since is not None)
    ):
        parser.error("retry needs --id, or --task with --since")


async def run(
    args: argparse.Namespace,
    sessionmaker: async_sessionmaker[AsyncSession],
    jobs_app: App,
) -> Report:
    if args.group == "failed-events":
        if args.action == "list":
            return await list_events(
                sessionmaker,
                provider=args.provider,
                since=args.since,
                error_contains=args.error_contains,
            )
        async with jobs_app.open_async():
            return await replay_events(
                sessionmaker,
                ids=args.ids,
                provider=args.provider,
                since=args.since,
                dry_run=args.dry_run,
            )
    async with jobs_app.open_async():
        if args.action == "list":
            return await list_jobs(jobs_app, task=args.task, since=args.since)
        return await retry_jobs(
            jobs_app, ids=args.ids, task=args.task, since=args.since, dry_run=args.dry_run
        )


def print_report(report: Report, out: TextIO) -> None:
    for line in report.lines:
        print(line, file=out)
    verb = {"failed-events replay": "replayed", "failed-jobs retry": "retried"}.get(report.command)
    summary = f"{report.matched} matched"
    if verb:
        summary += " (dry run, nothing changed)" if report.dry_run else f", {report.acted} {verb}"
    if report.skipped:
        summary += f", {len(report.skipped)} skipped"
    print(summary, file=out)


def _asyncio_run(coro: Coroutine[Any, Any, Report]) -> Report:
    # The queue's psycopg driver needs a selector loop on Windows.
    factory: Callable[[], asyncio.AbstractEventLoop] | None = (
        asyncio.SelectorEventLoop if sys.platform == "win32" else None
    )
    return asyncio.run(coro, loop_factory=factory)


def main(argv: Sequence[str] | None = None) -> int:
    from socialhood.jobs.app import app as jobs_app
    from socialhood.jobs.runtime import runtime

    parser = build_parser()
    args = parser.parse_args(argv)
    _validate(parser, args)
    report = _asyncio_run(run(args, runtime().sessionmaker, jobs_app))
    report.log(args.operator or _operator())
    print_report(report, sys.stdout)
    return 0
