"""Failed queue jobs, the job half of the dead-letter set (TR-OPS-04).

Queue-library specifics stay in jobs/, like the defers in enqueue.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from procrastinate import App

# Tasks that write to a platform. Their jobs record nothing about whether the platform received
# the request, so the CLI cannot tell a send that ended delivery_unknown from any other failure;
# it never retries them (TR-JOB-05). Users retry sends from the app after checking Instagram.
# Add each sending task here when it is written (P3 send_message, P5 publish_target, P6 replies).
PLATFORM_WRITE_TASKS = frozenset(
    {
        "send_message",
        "send_scheduled",
        "publish_target",
        "reply_to_comment",
        "private_reply",
        "run_automation",
        "drain_private_replies",
    }
)

_LIST_FAILED = """
SELECT j.id, j.task_name, j.queue_name, j.args, j.attempts, max(e.at) AS failed_at
FROM procrastinate_jobs j
JOIN procrastinate_events e ON e.job_id = j.id AND e.type = 'failed'
WHERE j.status = 'failed'
  AND (%(ids)s::bigint[] IS NULL OR j.id = ANY(%(ids)s::bigint[]))
  AND (%(task)s::text IS NULL OR j.task_name = %(task)s::text)
GROUP BY j.id
HAVING %(since)s::timestamptz IS NULL OR max(e.at) >= %(since)s::timestamptz
ORDER BY failed_at DESC
LIMIT %(limit)s
"""


@dataclass(frozen=True)
class FailedJob:
    id: int
    task_name: str
    queue_name: str
    args: dict[str, Any]
    attempts: int
    failed_at: datetime

    @property
    def retryable_from_ops(self) -> bool:
        return self.task_name not in PLATFORM_WRITE_TASKS


async def list_failed_jobs(
    app: App,
    *,
    ids: list[int] | None = None,
    task: str | None = None,
    since: datetime | None = None,
    limit: int = 500,
) -> list[FailedJob]:
    rows = await app.connector.execute_query_all_async(
        _LIST_FAILED, ids=ids or None, task=task, since=since, limit=limit
    )
    return [
        FailedJob(
            id=row["id"],
            task_name=row["task_name"],
            queue_name=row["queue_name"],
            args=row["args"],
            attempts=row["attempts"],
            failed_at=row["failed_at"],
        )
        for row in rows
    ]


async def retry_now(app: App, job: FailedJob) -> None:
    """``failed`` back to ``todo`` on its own lane (Procrastinate records a ``retried`` event)."""
    await app.job_manager.retry_job_by_id_async(job.id, datetime.now(UTC))
