"""Per-workspace limit on concurrent bulk jobs (TR-JOB-06).

A Valkey sorted set per workspace holds one member per running bulk job, scored by its lease
expiry, so a crashed worker's slot frees itself after the 10-minute lease.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis

LEASE_S = 600
RETRY_DELAY_S = 5

_ACQUIRE = """
local key, member = KEYS[1], ARGV[1]
local limit, now, lease = tonumber(ARGV[2]), tonumber(ARGV[3]), tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now)
if redis.call('ZCARD', key) < limit then
  redis.call('ZADD', key, now + lease, member)
  redis.call('EXPIRE', key, lease)
  return 1
end
return 0
"""


def slot_key(workspace_id: uuid.UUID | str) -> str:
    return f"bulk:{workspace_id}"


class BulkSemaphore:
    def __init__(self, redis: Redis, limit: int, lease_s: int = LEASE_S) -> None:
        self.redis = redis
        self.limit = limit
        self.lease_s = lease_s
        self._acquire = redis.register_script(_ACQUIRE)

    async def acquire(self, workspace_id: uuid.UUID | str) -> str | None:
        """Return a slot token, or None when the workspace already runs ``limit`` bulk jobs."""
        member = uuid.uuid4().hex
        got = await self._acquire(
            keys=[slot_key(workspace_id)],
            args=[member, self.limit, time.time(), self.lease_s],
        )
        return member if int(got) == 1 else None

    async def release(self, workspace_id: uuid.UUID | str, member: str) -> None:
        await self.redis.zrem(slot_key(workspace_id), member)


async def run_with_bulk_slot(
    semaphore: BulkSemaphore,
    workspace_id: uuid.UUID | str,
    work: Callable[[], Awaitable[Any]],
    requeue: Callable[[float], Awaitable[Any]],
) -> bool:
    """Run ``work`` in a bulk slot, or call ``requeue(5)`` to try again later.

    Requeueing defers a fresh job, so waiting for a slot never uses up the job's retries.
    Returns True when the work ran.
    """
    member = await semaphore.acquire(workspace_id)
    if member is None:
        await requeue(RETRY_DELAY_S)
        return False
    try:
        await work()
    finally:
        await semaphore.release(workspace_id, member)
    return True
