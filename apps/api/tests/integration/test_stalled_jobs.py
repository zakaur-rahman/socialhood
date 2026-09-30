"""recover_stalled_jobs (TR-JOB-03, TR-JOB-05; jobs/recovery.py) against the real queue tables.

A worker killed mid-job (a deploy's SIGKILL, a crash) leaves its jobs ``doing``. Once its heartbeat
is 90 s old: an idempotent job goes back to todo (up to 3 attempts), a job a domain sweeper owns
is only released (aborted, so its run lock stops blocking), and any other job is failed with an
alert, listed by the ops CLI and never re-run.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs import failed, recovery
from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.recovery import MAX_ATTEMPTS, recover_stalled


class Recorder:
    """Stands in for the module's logger."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def _record(self, level: str, event: str, **fields: Any) -> None:
        self.events.append((level, event, fields))

    def info(self, event: str, **fields: Any) -> None:
        self._record("info", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._record("warning", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._record("error", event, **fields)

    def alerts(self) -> list[dict[str, Any]]:
        return [f for level, e, f in self.events if level == "error" and e == "alert"]


@pytest.fixture
async def workers(engine: AsyncEngine, queue: None) -> AsyncIterator[None]:
    """No worker rows around the test (the queue fixture empties the job tables)."""
    await _run("DELETE FROM procrastinate_workers")
    yield
    await _run("DELETE FROM procrastinate_workers")


@pytest.fixture
def logged(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr(recovery, "log", recorder)
    return recorder


async def _run(sql: str, **params: Any) -> None:
    await jobs_app.connector.execute_query_async(sql, **params)


async def _one(sql: str, **params: Any) -> dict[str, Any]:
    return dict(await jobs_app.connector.execute_query_one_async(sql, **params))


async def worker(*, silent_for_s: int) -> int:
    row = await _one(
        "INSERT INTO procrastinate_workers (last_heartbeat)"
        " VALUES (now() - make_interval(secs => %(s)s)) RETURNING id",
        s=silent_for_s,
    )
    return int(row["id"])


async def job(
    task: str,
    *,
    worker_id: int | None,
    lane: str = "bulk",
    lock: str | None = None,
    queueing_lock: str | None = None,
    attempts: int = 0,
    status: str = "doing",
) -> int:
    """A job as a worker left it: ``doing`` on that worker (todo first, so the events are real)."""
    row = await _one(
        "INSERT INTO procrastinate_jobs"
        " (queue_name, task_name, args, status, lock, queueing_lock, attempts)"
        " VALUES (%(lane)s, %(task)s, %(args)s, 'todo', %(lock)s, %(qlock)s, %(attempts)s)"
        " RETURNING id",
        lane=lane,
        task=task,
        args=json.dumps({"workspace_id": "w", "source_id": "s", "version": 1}),
        lock=lock,
        qlock=queueing_lock,
        attempts=attempts,
    )
    job_id = int(row["id"])
    if status == "doing":
        await _run(
            "UPDATE procrastinate_jobs SET status = 'doing', worker_id = %(w)s WHERE id = %(id)s",
            w=worker_id,
            id=job_id,
        )
    return job_id


async def state(job_id: int) -> dict[str, Any]:
    return await _one(
        "SELECT status, attempts, worker_id FROM procrastinate_jobs WHERE id = %(id)s", id=job_id
    )


async def events(job_id: int) -> list[str]:
    rows = await jobs_app.connector.execute_query_all_async(
        "SELECT type FROM procrastinate_events WHERE job_id = %(id)s ORDER BY id", id=job_id
    )
    return [str(r["type"]) for r in rows]


# ---------------------------------------------------------------- idempotent tasks


async def test_a_stalled_idempotent_job_is_retried(workers: None, logged: Recorder) -> None:
    """The live evidence: ingestion left ``doing`` by a restarted worker runs again."""
    dead = await worker(silent_for_s=300)
    live = await worker(silent_for_s=5)
    stalled = await job("ingest_knowledge_source", worker_id=dead, queueing_lock="kb:s:1")
    running = await job("ingest_knowledge_source", worker_id=live, queueing_lock="kb:t:1")

    counts = await recover_stalled(jobs_app)

    assert counts == {"retried": 1, "released": 0, "failed": 0, "skipped": 0}
    assert (await state(stalled))["status"] == "todo"
    assert (await state(stalled))["attempts"] == 1
    assert "deferred_for_retry" in await events(stalled)
    # A job whose worker is alive is left alone, and the dead worker's row is pruned.
    assert (await state(running))["status"] == "doing"
    workers_left = await jobs_app.connector.execute_query_all_async(
        "SELECT id FROM procrastinate_workers ORDER BY id"
    )
    assert [r["id"] for r in workers_left] == [live]
    assert logged.alerts() == []

    # The retried job is picked up like any other.
    fetched = await jobs_app.job_manager.fetch_job(queues=["bulk"], worker_id=live)
    assert fetched is not None
    assert fetched.id == stalled


async def test_a_job_whose_worker_row_is_gone_is_recovered_too(workers: None) -> None:
    """A worker pruned at another worker's start leaves worker_id NULL (ON DELETE SET NULL)."""
    dead = await worker(silent_for_s=300)
    stalled = await job("analyze_conversation", worker_id=dead, lane="interactive")
    await _run("DELETE FROM procrastinate_workers WHERE id = %(id)s", id=dead)
    assert (await state(stalled))["worker_id"] is None

    await recover_stalled(jobs_app)

    assert (await state(stalled))["status"] == "todo"


async def test_a_worker_silent_for_less_than_90_s_is_not_dead(workers: None) -> None:
    """A worker shutting down stops its heartbeat but may run jobs until Render's 60 s grace
    ends; they are never taken from it."""
    draining = await worker(silent_for_s=70)
    busy = await job("ingest_knowledge_source", worker_id=draining)

    assert await recover_stalled(jobs_app) == {
        "retried": 0,
        "released": 0,
        "failed": 0,
        "skipped": 0,
    }
    assert (await state(busy))["status"] == "doing"


async def test_retries_stop_after_the_cap(workers: None, logged: Recorder) -> None:
    """A job that kills its worker every time (say, out of memory) is failed after 3 attempts."""
    dead = await worker(silent_for_s=300)
    poison = await job("ingest_knowledge_source", worker_id=dead, attempts=MAX_ATTEMPTS)

    counts = await recover_stalled(jobs_app)

    assert counts["failed"] == 1
    assert (await state(poison))["status"] == "failed"
    [alert] = logged.alerts()
    assert alert["kind"] == "stalled_job"
    assert alert["task"] == "ingest_knowledge_source"
    assert "after 3 attempts" in alert["detail"]
    # Failed jobs of idempotent tasks can be retried from the ops CLI.
    [listed] = await failed.list_failed_jobs(jobs_app, ids=[poison])
    assert listed.retryable_from_ops


async def test_the_same_work_already_waiting_releases_the_stalled_job(workers: None) -> None:
    """A newer job with the same queueing lock waits (a burst's analysis): it does the work, so
    the stalled one is aborted rather than queued twice."""
    dead = await worker(silent_for_s=300)
    lock = "analyze:c1"
    stalled = await job(
        "analyze_conversation", worker_id=dead, lane="interactive", lock=lock, queueing_lock=lock
    )
    waiting = await job(
        "analyze_conversation",
        worker_id=None,
        lane="interactive",
        lock=lock,
        queueing_lock=lock,
        status="todo",
    )

    counts = await recover_stalled(jobs_app)

    assert counts["released"] == 1
    assert (await state(stalled))["status"] == "aborted"
    assert (await state(waiting))["status"] == "todo"
    # The stalled job no longer holds the run lock: the waiting one can start.
    live = await worker(silent_for_s=0)
    fetched = await jobs_app.job_manager.fetch_job(queues=["interactive"], worker_id=live)
    assert fetched is not None
    assert fetched.id == waiting


# ---------------------------------------------------------------- tasks with their own sweeper


async def test_a_sweeper_owned_job_is_released_never_rerun(workers: None, logged: Recorder) -> None:
    """send_message: sweep_messages decides the message (delivery_unknown, TR-JOB-05). The dead
    job is only aborted, so its ``conv:`` run lock stops blocking the conversation's next send."""
    dead = await worker(silent_for_s=300)
    conv = "conv:c1"
    stalled = await job(
        "send_message", worker_id=dead, lane="interactive", lock=conv, queueing_lock="send:m1"
    )
    blocked = await job(
        "send_message",
        worker_id=None,
        lane="interactive",
        lock=conv,
        queueing_lock="send:m2",
        status="todo",
    )
    live = await worker(silent_for_s=0)
    assert await jobs_app.job_manager.fetch_job(queues=["interactive"], worker_id=live) is None

    counts = await recover_stalled(jobs_app)

    assert counts == {"retried": 0, "released": 1, "failed": 0, "skipped": 0}
    assert (await state(stalled))["status"] == "aborted"
    assert await events(stalled) == ["deferred", "started", "aborted"]
    assert logged.alerts() == []
    fetched = await jobs_app.job_manager.fetch_job(queues=["interactive"], worker_id=live)
    assert fetched is not None
    assert fetched.id == blocked


@pytest.mark.parametrize(
    "task", ["send_private_reply", "send_scheduled", "publish_target", "run_agent"]
)
async def test_other_sweeper_owned_jobs_are_not_retried(workers: None, task: str) -> None:
    dead = await worker(silent_for_s=300)
    stalled = await job(task, worker_id=dead, lane="interactive")

    await recover_stalled(jobs_app)

    assert (await state(stalled))["status"] == "aborted"


# ---------------------------------------------------------------- anything else


async def test_a_stalled_non_idempotent_job_is_failed_and_not_rerun(
    workers: None, logged: Recorder
) -> None:
    """post_first_comment may already have posted: failed, alerted, listed, never retried."""
    dead = await worker(silent_for_s=300)
    stalled = await job("post_first_comment", worker_id=dead, lane="interactive")

    counts = await recover_stalled(jobs_app)

    assert counts == {"retried": 0, "released": 0, "failed": 1, "skipped": 0}
    assert (await state(stalled))["status"] == "failed"
    assert await events(stalled) == ["deferred", "started", "failed"]
    [alert] = logged.alerts()
    assert (alert["kind"], alert["task"], alert["job_id"]) == (
        "stalled_job",
        "post_first_comment",
        stalled,
    )
    assert "not safe to run again" in alert["detail"]
    # Listed by `ops failed-jobs list`, and the CLI refuses to re-run it.
    [listed] = await failed.list_failed_jobs(jobs_app, ids=[stalled])
    assert listed.task_name == "post_first_comment"
    assert not listed.retryable_from_ops
    # Nothing re-runs it: a second pass finds nothing to do.
    assert (await recover_stalled(jobs_app))["failed"] == 0
    live = await worker(silent_for_s=0)
    assert await jobs_app.job_manager.fetch_job(queues=None, worker_id=live) is None


async def test_a_job_of_an_unknown_task_is_failed(workers: None, logged: Recorder) -> None:
    dead = await worker(silent_for_s=300)
    stalled = await job("renamed_task", worker_id=dead)

    await recover_stalled(jobs_app)

    assert (await state(stalled))["status"] == "failed"
    [alert] = logged.alerts()
    assert "no recovery rule" in alert["detail"]


async def test_a_job_that_moved_on_meanwhile_is_skipped(workers: None) -> None:
    """Two sweeps at once, or a slow worker that finished after all: each job moves once."""
    dead = await worker(silent_for_s=300)
    stalled = await job("ingest_knowledge_source", worker_id=dead)
    [found] = await jobs_app.job_manager.get_stalled_jobs(seconds_since_heartbeat=90)
    await _run("UPDATE procrastinate_jobs SET status = 'succeeded' WHERE id = %(id)s", id=stalled)

    assert await recovery._settle(jobs_app, found) == "skipped"
    assert (await state(stalled))["status"] == "succeeded"
