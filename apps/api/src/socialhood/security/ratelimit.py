"""Rate limits (TR-API-07): Valkey sliding windows; over the limit is 429 rate_limited with
Retry-After.

- per user, every signed-in request: 300 a minute (auth/deps.current_user);
- per workspace: 60 sends a minute and 20 AI requests a minute (api/ratelimit.per_workspace);
- per client IP on unauthenticated routes: 30 a minute on OAuth callbacks (TR-API-07), 60 a
  minute on the other public routes (api/ratelimit.per_ip).

Webhooks are not limited by IP (Meta shares IPs, TR-API-07); their bodies are capped at 5 MB.

A window is a sorted set of request times per (limit, subject), trimmed and counted in one Lua
call, so concurrent API processes share it exactly. A refused request is not recorded, so a
client that keeps retrying gets in as soon as the oldest request leaves the window. When Valkey
can't be reached the request goes through (logged): limits protect the service, they must not
take it down.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from starlette.requests import Request

from socialhood.errors import ApiError
from socialhood.observability.logging import get_logger
from socialhood.settings import Settings

log = get_logger(__name__)


@dataclass(frozen=True)
class Limit:
    name: str
    max_requests: int
    window_s: int


# Looked up by name when a request is checked, so tests can swap one.
LIMITS: dict[str, Limit] = {
    limit.name: limit
    for limit in (
        Limit("user", 300, 60),
        Limit("sends", 60, 60),
        Limit("ai", 20, 60),
        Limit("oauth_callback", 30, 60),
        Limit("public", 60, 60),
    )
}

# KEYS[1] the window; ARGV now (ms), window (ms), limit, a unique member.
# Returns 0 when the request is admitted (and recorded), else the ms until one would be.
_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) < limit then
  redis.call('ZADD', key, now, ARGV[4])
  redis.call('PEXPIRE', key, window)
  return 0
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local wait = tonumber(oldest[2]) + window - now
if wait < 1 then wait = 1 end
return wait
"""


def window_key(limit: Limit, subject: str) -> str:
    return f"rl:{limit.name}:{subject}"


async def hit(redis: Redis, limit: Limit, subject: str, *, now: float | None = None) -> float:
    """Record one request against ``subject``'s window. 0 when admitted, else the seconds until
    a request would be."""
    now_ms = int((time.time() if now is None else now) * 1000)
    script = redis.register_script(_SLIDING_WINDOW)
    wait_ms = await script(
        keys=[window_key(limit, subject)],
        args=[now_ms, limit.window_s * 1000, limit.max_requests, f"{now_ms}-{uuid.uuid4().hex}"],
    )
    return int(wait_ms) / 1000


async def enforce(request: Request, name: str, subject: str) -> None:
    """Count this request against ``subject`` under the named limit, or raise 429."""
    settings: Settings = request.app.state.settings
    if not settings.rate_limits_enabled:
        return
    limit = LIMITS[name]
    try:
        wait = await hit(request.app.state.redis, limit, subject)
    except Exception as error:
        log.warning("rate_limit_unavailable", limit=name, error=type(error).__name__)
        return
    if wait > 0:
        log.info("rate_limited", limit=name, path=request.url.path)
        raise ApiError(
            "rate_limited",
            "Too many requests. Try again in a moment.",
            headers={"Retry-After": str(max(1, math.ceil(wait)))},
        )


def client_ip(request: Request) -> str:
    """The caller's address. Behind Render the edge (Cloudflare) sets True-Client-IP and
    overwrites any value a client sends, so production names that header in CLIENT_IP_HEADER;
    X-Forwarded-For's first entry is whatever the client wrote and is never used here."""
    settings: Settings = request.app.state.settings
    if settings.client_ip_header:
        value = request.headers.get(settings.client_ip_header, "").strip()
        if value:
            return value
    return request.client.host if request.client else "unknown"
