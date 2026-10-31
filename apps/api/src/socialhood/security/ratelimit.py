"""Rate limits (TR-API-07): Valkey sliding windows; over the limit is 429 rate_limited with
Retry-After.

- per user, every signed-in request: 300 a minute (auth/deps.current_user);
- per API key, every public API request (GR-25, auth/api_key.py): 120 a minute; sending also
  counts against the workspace's 60 sends a minute;
- MCP tool calls (C-165, mcp/calls.py): 120 a minute per connection and 300 a minute per
  workspace, refused as a tool error rather than a 429;
- per workspace: 60 sends a minute and 20 AI requests a minute (api/ratelimit.per_workspace);
- per client IP on unauthenticated routes: 30 a minute on OAuth callbacks (TR-API-07), 60 a
  minute on the other public routes (api/ratelimit.per_ip);
- the website chat widget's public routes (GR-28): per IP 120 frame loads, 20 sessions, 40 sends,
  240 polls and 10 email forms a minute, and per visitor 10 sends a minute, 300 sends a day and 60
  polls a minute.

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
from socialhood.security.client_ip import FORWARDED_FOR, MAX_KEY_CHARS, rightmost_untrusted
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
        Limit("api_key", 120, 60),
        # C-165, MCP tool calls: per connection (an API key or, from phase C, an OAuth grant),
        # and per workspace across all its connections.
        Limit("mcp", 120, 60),
        Limit("mcp_workspace", 300, 60),
        # C-165 phase C, the OAuth endpoints (§6.1): authorize per IP, registration per IP (DCR
        # makes a client each time), token and revoke per client.
        Limit("oauth_authorize", 30, 60),
        Limit("oauth_register", 10, 3600),
        Limit("oauth_token", 60, 60),
        # GR-28, the website chat widget (no sign-in): per IP, then per visitor.
        Limit("widget_frame", 120, 60),
        Limit("widget_session", 20, 60),
        Limit("widget_send_ip", 40, 60),
        Limit("widget_send_visitor", 10, 60),
        Limit("widget_send_day", 300, 86_400),
        Limit("widget_poll_ip", 240, 60),
        Limit("widget_poll_visitor", 60, 60),
        Limit("widget_email_ip", 10, 60),
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
    """The caller's address (security/client_ip.py). On Render CLIENT_IP_HEADER is
    x-forwarded-for, read from the right: the rightmost entry that isn't one of the proxies.
    Its first entry is whatever the client wrote and is never used. Without the header (local
    runs, tests) it is the socket address."""
    settings: Settings = request.app.state.settings
    header = (settings.client_ip_header or "").strip().lower()
    if header == FORWARDED_FOR:
        # Every X-Forwarded-For line, in order, as one list (RFC 9110 §5.3).
        found = rightmost_untrusted(", ".join(request.headers.getlist(FORWARDED_FOR)))
        if found:
            return found
    elif header:
        value = request.headers.get(header, "").strip()
        if value:
            return value[:MAX_KEY_CHARS]
    return request.client.host if request.client else "unknown"
