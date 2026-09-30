"""Worker instrumentation (TR-OPS-01, T9.3): one Procrastinate worker middleware around every job.

For each job it binds ``job`` and ``workspace_id`` for logs, tags Sentry with the job name, lane and
workspace id, reports the exception when the job fails for good (not when it will be retried), and
counts the run and its duration by task, lane and status. On the first job in a worker process it
starts Sentry (component ``worker``) and the metrics flusher, from inside the worker's event loop.

``jobs/app.py`` passes ``worker_defaults()`` to the queue app; nothing else in jobs/ knows about it.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import sentry_sdk
import structlog
from procrastinate import exceptions as queue_errors

from socialhood.observability.metrics import JOB_DURATION, JOB_RUNS, Flusher
from socialhood.observability.sentry import init_sentry, instrument_running_loop

if TYPE_CHECKING:
    from procrastinate import JobContext
    from procrastinate.app import WorkerOptions
    from procrastinate.middleware import AsyncCallNext

_flusher: Flusher | None = None


def _start_process() -> None:
    """Sentry and the metrics flusher, once per worker process."""
    global _flusher
    if _flusher is not None and _flusher.running:
        return
    from socialhood.jobs.runtime import runtime  # the runtime imports the database layer

    rt = runtime()
    if init_sentry(rt.settings, component="worker"):
        instrument_running_loop()
    _flusher = Flusher(rt.redis)
    _flusher.start()


def job_status(error: BaseException, context: JobContext) -> str:
    """What the queue will do with a job that raised: retry it, or mark it failed or aborted."""
    if isinstance(error, queue_errors.JobAborted | asyncio.CancelledError):
        return "aborted"
    try:
        retry = context.task.get_retry_exception(exception=error, job=context.job)
    except Exception:
        retry = None
    return "retry" if retry is not None else "failed"


async def observe_job(call_next: AsyncCallNext, context: JobContext, worker: Any) -> Any:
    _start_process()
    job = context.job
    task, lane = job.task_name, job.queue or "unknown"
    workspace_id = job.task_kwargs.get("workspace_id")
    bound: dict[str, Any] = {"job": task, "job_id": job.id}
    if workspace_id:
        bound["workspace_id"] = str(workspace_id)
    status = "succeeded"
    started = time.perf_counter()
    try:
        with (
            structlog.contextvars.bound_contextvars(**bound),
            sentry_sdk.isolation_scope() as scope,
            sentry_sdk.start_transaction(op="queue.process", name=task, source="task"),
        ):
            scope.set_tag("job", task)
            scope.set_tag("lane", lane)
            if workspace_id:
                scope.set_tag("workspace_id", str(workspace_id))
            scope.set_context("job", {"id": job.id, "lane": lane, "attempts": job.attempts})
            try:
                return await call_next()
            except BaseException as error:
                status = job_status(error, context)
                if status == "failed":
                    sentry_sdk.capture_exception(error)
                raise
    finally:
        JOB_RUNS.inc(task=task, lane=lane, status=status)
        JOB_DURATION.observe(time.perf_counter() - started, task=task, lane=lane, status=status)


def worker_defaults() -> WorkerOptions:
    return {"worker_middleware": [observe_job]}
