"""Caps on what AI apps create (C-165 phase B; 01-design.md §5.3, §6.1): posts scheduled
(``mcp_posts_daily``), files uploaded (``mcp_uploads_daily``) and megabytes uploaded
(``mcp_upload_mb_daily``). Counted per workspace in Valkey for the UTC day, across all its AI
connections, like ``mcp_calls_daily`` (mcp/calls.py). ``reserve_post`` adds a limit per minute
(``mcp_posts``, C-169) and takes both together, for a post really being scheduled: previews and
drafts count for neither, and one post to several accounts counts once.

``reserve`` counts first and refuses past the plan's limit (402 quota_exceeded, in plain words);
the caller ``refund``s if the work then fails, so a refused post doesn't use up the day. Valkey
being down never blocks a call (the same rule as the rest of the pipeline).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime

from redis.asyncio import Redis

from socialhood.billing.entitlements import entitlement_error, quota_error
from socialhood.billing.plans import entitlement
from socialhood.errors import ApiError
from socialhood.observability.logging import get_logger
from socialhood.security import ratelimit

log = get_logger(__name__)

POSTS = "mcp_posts_daily"
POSTS_RATE = "mcp_posts"
TOO_FAST = "AI apps can schedule {n} posts a minute in this workspace. Try again in {s} seconds."
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
    rate_subject: str | None = None  # the minute's window it also holds a place in

    async def refund(self) -> None:
        try:
            if self.key is not None:
                await self.redis.decrby(self.key, self.amount)
            if self.rate_subject is not None:
                await ratelimit.release(self.redis, ratelimit.LIMITS[POSTS_RATE], self.rate_subject)
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


async def reserve_post(
    redis: Redis,
    plan: str,
    workspace_id: uuid.UUID,
    now: datetime,
    *,
    rate_limited: bool = True,
) -> Reservation:
    """One post being scheduled: the minute's limit first, so a call refused there doesn't use up
    the day, then the day's cap. ``refund`` gives back both if the post then fails."""
    subject = str(workspace_id)
    limit = ratelimit.LIMITS[POSTS_RATE]
    holds_place = False
    if rate_limited:
        try:
            wait = await ratelimit.hit(redis, limit, subject)
        except Exception as error:
            log.warning("rate_limit_unavailable", limit=POSTS_RATE, error=type(error).__name__)
        else:
            if wait > 0:
                seconds = max(1, math.ceil(wait))
                raise ApiError(
                    "rate_limited",
                    TOO_FAST.format(n=limit.max_requests, s=seconds),
                    headers={"Retry-After": str(seconds)},
                )
            holds_place = True
    rate_subject = subject if holds_place else None
    try:
        reservation = await reserve(redis, plan, POSTS, workspace_id, now)
    except BaseException:
        await Reservation(redis, None, 0, rate_subject).refund()
        raise
    reservation.rate_subject = rate_subject
    return reservation


async def check(
    redis: Redis, plan: str, name: str, workspace_id: uuid.UUID, now: datetime, *, words: str
) -> None:
    """Refuse when today's cap is already used up, without counting (the start of an upload)."""
    limit = entitlement(plan, name)
    if limit is not None and await used(redis, name, workspace_id, now) >= limit:
        raise quota_error(name, limit, words)
