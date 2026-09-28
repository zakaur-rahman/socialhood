"""T2.10: the failed-work CLI (TR-OPS-04)."""

from __future__ import annotations

import contextlib
import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.models.platform import WebhookStatus
from socialhood.ops import cli
from socialhood.repositories.webhook_events import MAX_ATTEMPTS
from socialhood.services import webhook_processing
from socialhood.services.webhook_processing import Outcome, process_event
from tests.support.instagram import fixture, signed_delivery


async def failed_event(
    app: FastAPI, client: httpx.AsyncClient, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> uuid.UUID:
    """Deliver an event and exhaust its attempts with a broken handler."""

    async def broken(session: Any, event: Any) -> Outcome:
        raise RuntimeError("parser bug")

    monkeypatch.setitem(webhook_processing.HANDLERS, "instagram", broken)
    raw, headers = signed_delivery(fixture("webhook_comment_changes.json"))
    await client.post("/webhooks/instagram", content=raw, headers=headers)
    async with engine.connect() as conn:
        event_id: uuid.UUID = (
            await conn.execute(text("SELECT id FROM webhook_events"))
        ).scalar_one()
    for _ in range(MAX_ATTEMPTS):
        with contextlib.suppress(RuntimeError):
            await process_event(app.state.sessionmaker, event_id)
    return event_id


async def test_a_failed_event_replayed_after_a_fix_is_processed_once(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id = await failed_event(app, client, engine, monkeypatch)

    listed = await cli.list_events(
        app.state.sessionmaker, provider="instagram", since=None, error_contains="parser"
    )
    assert listed.matched == 1
    assert str(event_id) in listed.lines[0]

    dry = await cli.replay_events(
        app.state.sessionmaker, ids=[event_id], provider=None, since=None, dry_run=True
    )
    assert (dry.matched, dry.acted) == (1, 0)
    async with engine.connect() as conn:
        status = (await conn.execute(text("SELECT status FROM webhook_events"))).scalar_one()
    assert status == "failed"

    calls: list[uuid.UUID] = []

    async def fixed(session: Any, event: Any) -> Outcome:
        calls.append(event.id)
        return Outcome("processed")

    monkeypatch.setitem(webhook_processing.HANDLERS, "instagram", fixed)
    replayed = await cli.replay_events(
        app.state.sessionmaker,
        ids=None,
        provider="instagram",
        since=cli.parse_since("1h"),
        dry_run=False,
    )
    assert (replayed.matched, replayed.acted) == (1, 1)

    # The worker runs the queued job; a duplicate delivery of the job does nothing.
    assert await process_event(app.state.sessionmaker, event_id) is WebhookStatus.PROCESSED
    assert await process_event(app.state.sessionmaker, event_id) is None
    assert calls == [event_id]
    again = await cli.replay_events(
        app.state.sessionmaker, ids=[event_id], provider=None, since=None, dry_run=False
    )
    assert again.matched == 0


async def insert_failed_job(task_name: str, *, failed_at: datetime | None = None) -> int:
    row = await jobs_app.connector.execute_query_one_async(
        "INSERT INTO procrastinate_jobs (queue_name, task_name, args, status, attempts)"
        " VALUES ('interactive', %(task)s, %(args)s, 'failed', 3) RETURNING id",
        task=task_name,
        args=json.dumps({"x": 1}),
    )
    await jobs_app.connector.execute_query_async(
        "INSERT INTO procrastinate_events (job_id, type, at) VALUES (%(id)s, 'failed', %(at)s)",
        id=row["id"],
        at=failed_at or datetime.now(UTC),
    )
    return int(row["id"])


async def job_status(job_id: int) -> str:
    row = await jobs_app.connector.execute_query_one_async(
        "SELECT status FROM procrastinate_jobs WHERE id = %(id)s", id=job_id
    )
    return str(row["status"])


async def test_failed_jobs_are_listed_and_retried(queue: None) -> None:
    recent = await insert_failed_job("analyze_comments")
    await insert_failed_job("analyze_comments", failed_at=datetime.now(UTC) - timedelta(days=2))
    await insert_failed_job("refresh_tokens")

    listed = await cli.list_jobs(jobs_app, task="analyze_comments", since=cli.parse_since("2h"))
    assert listed.matched == 1
    assert listed.lines[0].startswith(str(recent))

    dry = await cli.retry_jobs(jobs_app, ids=[recent], task=None, since=None, dry_run=True)
    assert (dry.matched, dry.acted) == (1, 0)
    assert await job_status(recent) == "failed"

    done = await cli.retry_jobs(jobs_app, ids=[recent], task=None, since=None, dry_run=False)
    assert done.acted == 1
    assert await job_status(recent) == "todo"


async def test_a_send_is_never_retried_from_the_cli(queue: None) -> None:
    """TR-JOB-05: a send whose outcome may be unknown is retried by the user, not the operator."""
    send = await insert_failed_job("send_message")
    report = await cli.retry_jobs(jobs_app, ids=[send], task=None, since=None, dry_run=False)
    assert (report.matched, report.acted, len(report.skipped)) == (1, 0, 1)
    assert await job_status(send) == "failed"


def test_durations() -> None:
    now = datetime(2026, 1, 2, 12, tzinfo=UTC)
    assert cli.parse_since("90s", now) == now - timedelta(seconds=90)
    assert cli.parse_since("2h", now) == now - timedelta(hours=2)
    assert cli.parse_since("7d", now) == now - timedelta(days=7)
    with pytest.raises(Exception, match="duration"):
        cli.parse_since("2 hours", now)


@pytest.mark.parametrize(
    "argv",
    [
        ["failed-events", "replay"],
        ["failed-jobs", "retry"],
        ["failed-jobs", "retry", "--task", "x"],
    ],
)
def test_bulk_actions_need_a_filter(argv: list[str]) -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        cli._validate(parser, parser.parse_args(argv))


def test_the_report_summarises(capsys: pytest.CaptureFixture[str]) -> None:
    report = cli.Report("failed-jobs retry", {}, matched=3, acted=2, skipped=["9 send_message"])
    out = io.StringIO()
    cli.print_report(report, out)
    assert out.getvalue().strip() == "3 matched, 2 retried, 1 skipped"
