"""TR-JOB-01, TR-JOB-02, TR-JOB-06 against the real queue tables and Valkey."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from procrastinate.periodic import PeriodicDeferrer
from redis.asyncio import Redis

from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import RETRY_DELAY_S, BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.tasks.maintenance import ping


@pytest.fixture
async def queue() -> AsyncIterator[None]:
    async with app.open_async():
        await _clear()
        yield
        await _clear()


async def _clear() -> None:
    await app.connector.execute_query_async(
        "TRUNCATE procrastinate_periodic_defers, procrastinate_events, procrastinate_jobs CASCADE"
    )


async def _jobs(task_name: str) -> list[dict[str, object]]:
    return list(
        await app.connector.execute_query_all_async(
            "SELECT id, queue_name, status, args FROM procrastinate_jobs WHERE task_name = %(t)s",
            t=task_name,
        )
    )


async def test_the_same_key_enqueued_twice_runs_once(queue: None) -> None:
    assert await enqueue(ping, key="ping:k1", timestamp=1) is True
    assert await enqueue(ping, key="ping:k1", timestamp=2) is False
    jobs = await _jobs("ping")
    assert len(jobs) == 1
    assert jobs[0]["queue_name"] == INTERACTIVE


async def test_a_different_key_is_a_different_job(queue: None) -> None:
    assert await enqueue(ping, key="ping:k1", timestamp=1)
    assert await enqueue(ping, key="ping:k2", timestamp=1)
    assert len(await _jobs("ping")) == 2


async def test_lane_and_delay_are_applied(queue: None) -> None:
    await enqueue(ping, key="ping:bulk", lane="bulk", delay_s=60, timestamp=1)
    rows = await app.connector.execute_query_all_async(
        "SELECT queue_name, scheduled_at > now() + interval '50 seconds' AS later "
        "FROM procrastinate_jobs WHERE task_name = 'ping'"
    )
    assert rows == [{"queue_name": "bulk", "later": True}]


async def test_a_periodic_job_runs_once_with_two_workers(queue: None) -> None:
    periodic_task = next(iter(app.periodic_registry.periodic_tasks.values()))
    tick = 1_790_000_040
    first, second = PeriodicDeferrer(app.periodic_registry), PeriodicDeferrer(app.periodic_registry)

    await first.defer_jobs([(periodic_task, tick)])
    # The first worker's job has run, so the queueing lock no longer blocks: only the
    # database's periodic record can stop the second worker from deferring the same tick.
    await app.connector.execute_query_async(
        "UPDATE procrastinate_jobs SET status = 'succeeded' WHERE task_name = 'ping'"
    )
    await second.defer_jobs([(periodic_task, tick)])
    assert len(await _jobs("ping")) == 1

    await second.defer_jobs([(periodic_task, tick + 60)])
    assert len(await _jobs("ping")) == 2


async def test_a_fifth_bulk_job_for_one_workspace_waits(redis: Redis) -> None:
    semaphore = BulkSemaphore(redis, limit=4)
    workspace, other = uuid.uuid4(), uuid.uuid4()
    held = [await semaphore.acquire(workspace) for _ in range(4)]
    assert all(held)
    assert await semaphore.acquire(workspace) is None
    assert await semaphore.acquire(other) is not None  # other workspaces are unaffected

    requeued: list[float] = []
    ran: list[bool] = []

    async def work() -> None:
        ran.append(True)

    async def requeue(delay: float) -> None:
        requeued.append(delay)

    assert await run_with_bulk_slot(semaphore, workspace, work, requeue) is False
    assert requeued == [RETRY_DELAY_S]
    assert ran == []

    assert held[0] is not None
    await semaphore.release(workspace, held[0])
    assert await run_with_bulk_slot(semaphore, workspace, work, requeue) is True
    assert ran == [True]
    # The slot used by that job was released afterwards.
    assert await semaphore.acquire(workspace) is not None


async def test_expired_leases_free_their_slot(redis: Redis) -> None:
    semaphore = BulkSemaphore(redis, limit=1, lease_s=-1)
    workspace = uuid.uuid4()
    assert await semaphore.acquire(workspace) is not None
    # The first lease is already expired, so a crashed job cannot hold the slot forever.
    assert await semaphore.acquire(workspace) is not None
