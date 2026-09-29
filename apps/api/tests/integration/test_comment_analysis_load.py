"""T6.2 done-when: 20,000 comments on one account never use more than 4 bulk slots (TR-JOB-06,
FR-CMT-02). A real Procrastinate worker (8 bulk processes' worth of concurrency) works through the
account's backlog while the dispatcher keeps running, as in production; the workspace's bulk slots
and the account's concurrent batches are measured throughout."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from procrastinate.worker import Worker
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider, comment_ids
from socialhood.jobs.app import BULK
from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.fairness import BulkSemaphore, slot_key
from socialhood.jobs.runtime import Runtime
from socialhood.jobs.tasks import comments as comment_tasks
from socialhood.services.comments import analysis
from socialhood.settings import Settings
from tests.support.comments import Comments
from tests.support.runtime import make_world, platform_deps
from tests.support.sending import clean_outbox

COMMENTS = 20_000
TIMEOUT_S = 600


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def cw(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[Comments]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        world = await make_world(engine, redis, deps)
        monkeypatch.setattr(
            comment_tasks,
            "runtime",
            lambda: Runtime(
                settings=api_settings, sessionmaker=world.maker, redis=redis, http=deps.http
            ),
        )
        yield Comments(world)


async def test_twenty_thousand_comments_on_one_account_never_use_more_than_four_bulk_slots(
    cw: Comments, fake_ai: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    await cw.plan("max")  # 20,000 comments cost 1,200 credits, summaries a few more
    post = await cw.post()
    await cw.bulk_comments(post, COMMENTS)
    await cw.execute("ANALYZE comments")  # autovacuum's job in production

    peak = {"slots": 0, "batches": 0}
    running = [0]
    acquire = BulkSemaphore.acquire

    async def measured_acquire(self: BulkSemaphore, workspace_id: Any) -> str | None:
        member = await acquire(self, workspace_id)
        if member is not None:
            held = int(await self.redis.zcard(slot_key(workspace_id)))
            peak["slots"] = max(peak["slots"], held)
        return member

    batch = analysis.analyze_batch

    async def measured_batch(*args: Any, **kwargs: Any) -> analysis.BatchRun:
        running[0] += 1
        peak["batches"] = max(peak["batches"], running[0])
        try:
            return await batch(*args, **kwargs)
        finally:
            running[0] -= 1

    monkeypatch.setattr(BulkSemaphore, "acquire", measured_acquire)
    monkeypatch.setattr(analysis, "analyze_batch", measured_batch)

    worker = Worker(
        jobs_app,
        queues=[BULK],
        concurrency=8,
        wait=True,
        fetch_job_polling_interval=0.05,
        listen_notify=False,
        install_signal_handlers=False,
    )
    running_worker = asyncio.create_task(worker.run())
    started = time.monotonic()
    try:
        while time.monotonic() - started < TIMEOUT_S:
            await cw.dispatch()  # dispatch_comment_analysis, every 30 s in production
            if (await cw.statuses()).get("pending", 0) == 0:
                break
            await asyncio.sleep(0.5)
    finally:
        worker.stop()
        await asyncio.wait_for(running_worker, timeout=60)

    assert await cw.statuses() == {"done": COMMENTS}
    assert peak["slots"] <= 4  # TR-JOB-06: the workspace's bulk slots
    assert peak["batches"] == 1  # the account's runs never overlap (lock cmt:{account_id})
    calls = fake_ai.calls_for("comment_analysis")
    assert len(calls) == COMMENTS // analysis.BATCH_SIZE
    assert {len(comment_ids(call)) for call in calls} == {analysis.BATCH_SIZE}
    stats = await cw.stats(post)
    assert (stats["total"], stats["analysed"]) == (COMMENTS, COMMENTS)
    [usage] = await cw.rows(
        "SELECT sum(credits) AS c FROM ai_usage_events WHERE feature = 'comment_analysis'"
    )
    # 1 credit per 20 comments, rounded up per batch: 3 for each batch of 50.
    assert usage["c"] == COMMENTS // analysis.BATCH_SIZE * 3
