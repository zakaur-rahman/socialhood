"""Gauges computed when /metrics is scraped (TR-OPS-01, TR-JOB-06, T9.3).

They read the database and Valkey directly, so they are right whichever process did the work and
even while the worker is down. Each collector reports ``socialhood_collector_up``; a failed query
leaves its gauges out rather than failing the scrape. The queries aggregate across workspaces and
return only counts and ages, never rows.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood import __version__
from socialhood.observability.logging import get_logger
from socialhood.observability.metrics import Gauge
from socialhood.settings import Settings

log = get_logger(__name__)

LANES = ("interactive", "bulk")  # socialhood.jobs.app.LANES, not imported: the worker imports us
STATEMENT_TIMEOUT_MS = 2000

QUEUE_READY = Gauge("socialhood_queue_ready_jobs", "Jobs waiting to run now, per lane.", ("lane",))
QUEUE_SCHEDULED = Gauge(
    "socialhood_queue_scheduled_jobs",
    "Jobs waiting for a later time (delays and retries), per lane.",
    ("lane",),
)
QUEUE_RUNNING = Gauge("socialhood_queue_running_jobs", "Jobs running, per lane.", ("lane",))
QUEUE_OLDEST = Gauge(
    "socialhood_queue_oldest_ready_seconds",
    "Age of the oldest job ready to run, per lane (0 when none).",
    ("lane",),
)
DISPATCHER_LAG = Gauge(
    "socialhood_dispatcher_lag_seconds",
    "How overdue the oldest due scheduled message or post is (0 when none).",
    ("kind",),
)
SSE_CONNECTIONS = Gauge("socialhood_sse_connections", "Open SSE streams (Valkey clients).")
COLLECTOR_UP = Gauge(
    "socialhood_collector_up", "1 when the scrape-time collector succeeded.", ("collector",)
)
BUILD_INFO = Gauge(
    "socialhood_build_info", "Always 1; labels carry the build.", ("version", "environment")
)

_QUEUE_COUNTS = """
SELECT queue_name AS lane,
       count(*) FILTER (WHERE status = 'todo'
                        AND (scheduled_at IS NULL OR scheduled_at <= now())) AS ready,
       count(*) FILTER (WHERE status = 'todo' AND scheduled_at > now()) AS scheduled,
       count(*) FILTER (WHERE status = 'doing') AS running
FROM procrastinate_jobs
WHERE status IN ('todo', 'doing')
GROUP BY queue_name
"""

# A job without scheduled_at became ready when it was deferred; one with scheduled_at (a delay
# or a retry) when that time came. The oldest unscheduled job is the lowest id.
_QUEUE_OLDEST = """
SELECT lane,
       coalesce(greatest(
         (SELECT extract(epoch FROM now() - min(e.at))
            FROM procrastinate_events e
           WHERE e.type = 'deferred'
             AND e.job_id = (SELECT min(j.id) FROM procrastinate_jobs j
                              WHERE j.queue_name = lanes.lane AND j.status = 'todo'
                                AND j.scheduled_at IS NULL)),
         (SELECT extract(epoch FROM now() - min(j.scheduled_at))
            FROM procrastinate_jobs j
           WHERE j.queue_name = lanes.lane AND j.status = 'todo' AND j.scheduled_at <= now())
       ), 0) AS oldest
FROM unnest(CAST(:lanes AS text[])) AS lanes(lane)
"""

# The rows dispatch_due claims (TR-JOB-03): scheduled messages, and posts with a target pending.
_DISPATCHER_LAG = """
SELECT
  coalesce((SELECT extract(epoch FROM now() - min(send_at))
              FROM scheduled_messages
             WHERE status = 'scheduled' AND send_at <= now()), 0) AS message,
  coalesce((SELECT extract(epoch FROM now() - min(p.publish_at))
              FROM scheduled_posts p
             WHERE p.status IN ('scheduled', 'publishing') AND p.publish_at <= now()
               AND EXISTS (SELECT 1 FROM scheduled_post_targets t
                            WHERE t.scheduled_post_id = p.id AND t.status = 'pending')), 0) AS post
"""


async def _queue(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as conn:
        await conn.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
        counts = {row.lane: row for row in (await conn.execute(text(_QUEUE_COUNTS))).all()}
        oldest = {
            row.lane: float(row.oldest)
            for row in (await conn.execute(text(_QUEUE_OLDEST), {"lanes": list(LANES)})).all()
        }
    lanes = sorted(set(LANES) | set(counts))

    def per_lane(column: str) -> list[tuple[Mapping[str, object], float]]:
        return [
            ({"lane": lane}, float(getattr(counts[lane], column)) if lane in counts else 0.0)
            for lane in lanes
        ]

    return [
        *QUEUE_READY.render(per_lane("ready")),
        *QUEUE_SCHEDULED.render(per_lane("scheduled")),
        *QUEUE_RUNNING.render(per_lane("running")),
        *QUEUE_OLDEST.render([({"lane": lane}, oldest.get(lane, 0.0)) for lane in lanes]),
    ]


async def _dispatcher(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as conn:
        await conn.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
        row = (await conn.execute(text(_DISPATCHER_LAG))).one()
    return DISPATCHER_LAG.render(
        [({"kind": "message"}, float(row.message)), ({"kind": "post"}, float(row.post))]
    )


async def _sse(redis: Redis) -> list[str]:
    clients: list[dict[str, Any]] = await redis.client_list(_type="normal")
    count = sum(1 for c in clients if str(c.get("name") or "").startswith("sse:"))
    return SSE_CONNECTIONS.render([({}, float(count))])


async def collect(engine: AsyncEngine, redis: Redis, settings: Settings) -> list[str]:
    collectors: dict[str, Callable[[], Awaitable[list[str]]]] = {
        "queue": lambda: _queue(engine),
        "dispatcher": lambda: _dispatcher(engine),
        "sse": lambda: _sse(redis),
    }
    lines: list[str] = []
    up: list[tuple[Mapping[str, object], float]] = []
    for name, run in collectors.items():
        try:
            lines.extend(await run())
            up.append(({"collector": name}, 1.0))
        except Exception:
            log.warning("metrics_collector_failed", collector=name, exc_info=True)
            up.append(({"collector": name}, 0.0))
    lines.extend(COLLECTOR_UP.render(up))
    lines.extend(
        BUILD_INFO.render([({"version": __version__, "environment": settings.app_env.value}, 1.0)])
    )
    return lines
