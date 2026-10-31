"""Daily caps on what AI apps create (C-165 phase B; 01-design.md §5.3, §6.1): posts scheduled
(``mcp_posts_daily``), files uploaded (``mcp_uploads_daily``) and megabytes uploaded
(``mcp_upload_mb_daily``). Counted per workspace in Valkey for the UTC day, across all its AI
connections, like ``mcp_calls_daily`` (mcp/calls.py).

``reserve`` counts first and refuses past the plan's limit (402 quota_exceeded, in plain words);
the caller ``refund``s if the work then fails, so a refused post doesn't use up the day. Valkey
being down never blocks a call (the same rule as the rest of the pipeline).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from redis.asyncio import Redis

from socialhood.billing.entitlements import entitlement_error, quota_error
from socialhood.billing.plans import entitlement
from socialhood.observability.logging import get_logger

log = get_logger(__name__)

POSTS = "mcp_posts_daily"
UPLOADS = "mcp_uploads_daily"
UPLOAD_MB = "mcp_upload_mb_daily"
MB = 1024 * 1024


def _key(name: str, workspace_id: uuid.UUID, now: datetime) -> str:
    return f"mcp-cap:{name}:{workspace_id}:{now:%Y-%m-%d}"


@dataclass
class Reservation:
    redis: Redis
    key: str | None
    amount: int

    async def refund(self) -> None:
        if self.key is None:
            return
        try:
            await self.redis.decrby(self.key, self.amount)
        except Exception:
            log.warning("mcp_cap_unavailable")


async def used(redis: Redis, name: str, workspace_id: uuid.UUID, now: datetime) -> int:
    try:
        return int(await redis.get(_key(name, workspace_id, now)) or 0)
    except Exception:
        log.warning("mcp_cap_unavailable")
        return 0


async def reserve(
    redis: Redis,
    plan: str,
    name: str,
    workspace_id: uuid.UUID,
    now: datetime,
    *,
    amount: int = 1,
    words: str | None = None,
) -> Reservation:
    """Count ``amount`` against today's cap, or 402. A limit of 0 means the plan has none of it
    (entitlement_required); None means unlimited."""
    limit = entitlement(plan, name)
    if limit is None:
        return Reservation(redis, None, 0)
    if limit == 0:
        raise entitlement_error("ai_connections")
    key = _key(name, workspace_id, now)
    try:
        total = int(await redis.incrby(key, amount))
        if total == amount:
            await redis.expire(key, 2 * 86_400)
    except Exception:
        log.warning("mcp_cap_unavailable")
        return Reservation(redis, None, 0)
    if total > limit:
        await redis.decrby(key, amount)
        raise quota_error(name, limit, words)
    return Reservation(redis, key, amount)


async def check(
    redis: Redis, plan: str, name: str, workspace_id: uuid.UUID, now: datetime, *, words: str
) -> None:
    """Refuse when today's cap is already used up, without counting (the start of an upload)."""
    limit = entitlement(plan, name)
    if limit is not None and await used(redis, name, workspace_id, now) >= limit:
        raise quota_error(name, limit, words)
