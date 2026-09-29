"""ingest_knowledge_source(id, version) (T5.3; TR-AI-08, job catalogue: bulk lane, queueing lock
kb:{id}:{version}, 3 tries).

Thin: it takes a per-workspace bulk slot (TR-JOB-06; without one it defers a fresh copy 5 s later,
which does not use up its tries) and runs services/knowledge/ingest.py. The service raises only
while the job has tries left, so a source is marked failed on its final attempt, never before a
retry (TR-JOB-04).
"""

from __future__ import annotations

import uuid

from procrastinate import JobContext

from socialhood.jobs.app import BULK, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.retry import BackoffRetry
from socialhood.jobs.runtime import runtime
from socialhood.services.knowledge import ingest

INGEST_RETRY = BackoffRetry(max_attempts=3)


@app.task(name="ingest_knowledge_source", queue=BULK, retry=INGEST_RETRY, pass_context=True)
async def ingest_knowledge_source(
    context: JobContext, workspace_id: str, source_id: str, version: int
) -> None:
    rt = runtime()
    will_retry = int(context.job.attempts) + 1 < INGEST_RETRY.max_attempts

    async def work() -> None:
        await ingest.ingest_source(
            rt.sessionmaker,
            rt.http,
            workspace_id=uuid.UUID(workspace_id),
            source_id=uuid.UUID(source_id),
            version=int(version),
            will_retry=will_retry,
        )

    async def requeue(delay_s: float) -> None:
        await enqueue(
            ingest_knowledge_source,
            key=f"kb:{source_id}:{version}",
            delay_s=delay_s,
            workspace_id=workspace_id,
            source_id=source_id,
            version=version,
        )

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)
