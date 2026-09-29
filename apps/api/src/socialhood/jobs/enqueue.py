"""The only module that defers jobs (TR-JOB-01).

Keeping every defer here means the queue library can be swapped in one place.
"""

from __future__ import annotations

from typing import Any

from procrastinate import exceptions
from procrastinate.tasks import Task
from procrastinate.types import TimeDeltaParams


async def enqueue(
    task: Task[Any, Any, Any],
    *,
    key: str | None = None,
    lane: str | None = None,
    delay_s: float = 0,
    lock: str | None = None,
    **kwargs: Any,
) -> bool:
    """Defer ``task``. Returns False when a job with the same ``key`` is already waiting.

    ``key`` is the queueing lock (dedupe while waiting); ``lock`` serialises running jobs that
    share it (for example, sends in one conversation); ``lane`` overrides the task's queue.
    """
    schedule_in = TimeDeltaParams(milliseconds=round(delay_s * 1000)) if delay_s else None
    job = task.configure(queueing_lock=key, lock=lock, queue=lane, schedule_in=schedule_in)
    try:
        await job.defer_async(**kwargs)
    except exceptions.AlreadyEnqueued:
        return False
    return True


async def enqueue_named(
    name: str,
    *,
    lane: str,
    key: str | None = None,
    delay_s: float = 0,
    lock: str | None = None,
    **kwargs: Any,
) -> bool:
    """Defer a task by its registered name, resolved when the job is deferred: for tasks another
    module owns (e.g. analysis queues ``suggest_reply``) without importing it. ``lane`` is
    required so the job lands on the right queue even before that task is registered."""
    from socialhood.jobs.app import app

    schedule_in = TimeDeltaParams(milliseconds=round(delay_s * 1000)) if delay_s else None
    job = app.configure_task(
        name, queueing_lock=key, lock=lock, queue=lane, schedule_in=schedule_in
    )
    try:
        await job.defer_async(**kwargs)
    except exceptions.AlreadyEnqueued:
        return False
    return True
