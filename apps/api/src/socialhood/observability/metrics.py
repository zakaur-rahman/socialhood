"""Prometheus metrics (TR-OPS-01, SEC-12, T9.3).

The API and the worker are separate Render services, the API may run several instances, and a
Render background worker takes no inbound traffic, so nothing can scrape each process. Instead
there is one scrape target, the API's ``/metrics``, and one shared registry in Valkey:

- every process adds its counts to an in-memory buffer (``Counter.inc``, ``Histogram.observe``:
  a dict update, no I/O);
- a ``Flusher`` task folds the buffer into Valkey hashes every few seconds (``HINCRBYFLOAT`` in one
  MULTI; the API's lifespan and the worker's first job start it); a failed flush keeps the counts
  for the next one;
- ``/metrics`` flushes its own buffer, reads the hashes and adds gauges computed at scrape time from
  Postgres and Valkey (queue depth, dispatcher lag, SSE connections), so every instance serves the
  same totals.

Counters are totals since Valkey last restarted, which Prometheus's ``rate()`` treats as a counter
reset: Valkey still holds nothing that must survive a restart. Label values come from code (route
templates, task names, error codes), never from ids or user input, so the series stay bounded.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import threading
from bisect import bisect_left
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from socialhood.observability.logging import get_logger

log = get_logger(__name__)

KEY_PREFIX = "metrics:"
FLUSH_INTERVAL_S = 5.0
_SEP = "\n"  # between a labelset and a histogram part; escaped label values never contain it


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def labelset(names: tuple[str, ...], values: Mapping[str, object]) -> str:
    unknown = set(values) - set(names)
    if unknown:
        raise ValueError(f"unknown labels: {sorted(unknown)}")
    return ",".join(f'{name}="{escape_label(str(values.get(name, "")))}"' for name in names)


def format_value(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if math.isnan(value):
        return "NaN"
    return repr(float(value)) if value != int(value) else str(int(value))


def _series(name: str, labels: str, value: float) -> str:
    return (
        f"{name}{{{labels}}} {format_value(value)}" if labels else f"{name} {format_value(value)}"
    )


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


# ---------------------------------------------------------------- the in-process buffer


class _Buffer:
    def __init__(self) -> None:
        self._pending: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()  # sync tasks run in threads

    def add(self, key: str, field: str, amount: float) -> None:
        with self._lock:
            self._pending[(key, field)] = self._pending.get((key, field), 0.0) + amount

    def drain(self) -> dict[tuple[str, str], float]:
        with self._lock:
            pending, self._pending = self._pending, {}
        return pending

    def restore(self, items: Mapping[tuple[str, str], float]) -> None:
        for (key, field), amount in items.items():
            self.add(key, field, amount)

    def clear(self) -> None:
        with self._lock:
            self._pending.clear()


BUFFER = _Buffer()


async def flush(redis: Redis) -> int:
    """Fold the buffer into Valkey; returns how many fields were written. Never raises."""
    items = BUFFER.drain()
    if not items:
        return 0
    try:
        pipe = redis.pipeline(transaction=True)
        for (key, field), amount in items.items():
            pipe.hincrbyfloat(key, field, amount)
        await pipe.execute()
    except Exception:
        BUFFER.restore(items)
        log.warning("metrics_flush_failed", fields=len(items))
        return 0
    return len(items)


class Flusher:
    """Flushes the buffer every ``interval_s`` seconds in the running loop, and once on stop."""

    def __init__(self, redis: Redis, interval_s: float = FLUSH_INTERVAL_S) -> None:
        self.redis = redis
        self.interval_s = interval_s
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self.running:
            self._task = asyncio.get_running_loop().create_task(self._run(), name="metrics-flush")

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_s)
            await flush(self.redis)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await flush(self.redis)


# ---------------------------------------------------------------- metric types


@dataclass(frozen=True)
class Counter:
    name: str
    help: str
    labels: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return KEY_PREFIX + self.name

    def inc(self, amount: float = 1.0, **labels: object) -> None:
        BUFFER.add(self.key, labelset(self.labels, labels), amount)

    def render(self, stored: Mapping[str, str]) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        lines.extend(_series(self.name, ls, float(stored[ls])) for ls in sorted(stored))
        return lines


@dataclass(frozen=True)
class Histogram:
    name: str
    help: str
    labels: tuple[str, ...]
    buckets: tuple[float, ...]

    @property
    def key(self) -> str:
        return KEY_PREFIX + self.name

    def observe(self, value: float, **labels: object) -> None:
        ls = labelset(self.labels, labels)
        # Buckets are "less than or equal": the first bound >= value counts it. Stored per bucket
        # (not cumulative) so one observation is three field updates.
        BUFFER.add(self.key, f"{ls}{_SEP}{bisect_left(self.buckets, value)}", 1.0)
        BUFFER.add(self.key, f"{ls}{_SEP}sum", value)
        BUFFER.add(self.key, f"{ls}{_SEP}count", 1.0)

    def render(self, stored: Mapping[str, str]) -> list[str]:
        groups: dict[str, dict[str, float]] = {}
        for field, value in stored.items():
            ls, _, part = field.rpartition(_SEP)
            groups.setdefault(ls, {})[part] = float(value)
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        for ls in sorted(groups):
            parts = groups[ls]
            prefix = f"{ls}," if ls else ""
            cumulative = 0.0
            for index, bound in enumerate(self.buckets):
                cumulative += parts.get(str(index), 0.0)
                lines.append(
                    _series(
                        f"{self.name}_bucket", f'{prefix}le="{format_value(bound)}"', cumulative
                    )
                )
            count = parts.get("count", 0.0)
            lines.append(_series(f"{self.name}_bucket", f'{prefix}le="+Inf"', count))
            lines.append(_series(f"{self.name}_sum", ls, parts.get("sum", 0.0)))
            lines.append(_series(f"{self.name}_count", ls, count))
        return lines


@dataclass(frozen=True)
class Gauge:
    """A value computed when /metrics is scraped (never buffered)."""

    name: str
    help: str
    labels: tuple[str, ...] = ()

    def render(self, values: Iterable[tuple[Mapping[str, object], float]]) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} gauge"]
        lines.extend(_series(self.name, labelset(self.labels, lbl), v) for lbl, v in values)
        return lines


# ---------------------------------------------------------------- the metrics (TR-OPS-01)

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
JOB_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0)

HTTP_REQUESTS = Counter(
    "socialhood_http_requests_total",
    "HTTP requests by method, route template and status code.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "socialhood_http_request_duration_seconds",
    "HTTP request latency by method and route template.",
    ("method", "route"),
    LATENCY_BUCKETS,
)
WEBHOOK_DELIVERIES = Counter(
    "socialhood_webhook_deliveries_total",
    "Webhook POSTs by provider and outcome (accepted, signature_invalid, rejected, error).",
    ("provider", "outcome"),
)
JOB_RUNS = Counter(
    "socialhood_job_runs_total",
    "Job runs by task, lane and status (succeeded, retry, failed, aborted).",
    ("task", "lane", "status"),
)
JOB_DURATION = Histogram(
    "socialhood_job_duration_seconds",
    "Job run time by task, lane and status.",
    ("task", "lane", "status"),
    JOB_BUCKETS,
)
SENDS = Counter(
    "socialhood_sends_total",
    "Outbound message sends by platform and outcome (sent, failed), with the failure code.",
    ("platform", "outcome", "code"),
)
PLATFORM_CALLS = Counter(
    "socialhood_platform_calls_total",
    "Platform API calls by platform, endpoint name and outcome (ok or the mapped error code).",
    ("platform", "endpoint", "outcome"),
)
AI_CALLS = Counter(
    "socialhood_ai_calls_total",
    "AI calls by feature, model and outcome (ok, error, timeout).",
    ("feature", "model", "outcome"),
)
AI_TOKENS = Counter(
    "socialhood_ai_tokens_total",
    "AI tokens by feature, model and direction (input, output).",
    ("feature", "model", "direction"),
)

STORED: tuple[Counter | Histogram, ...] = (
    HTTP_REQUESTS,
    HTTP_DURATION,
    WEBHOOK_DELIVERIES,
    JOB_RUNS,
    JOB_DURATION,
    SENDS,
    PLATFORM_CALLS,
    AI_CALLS,
    AI_TOKENS,
)


def record_send(platform: str, *, failed_code: str | None = None) -> None:
    """One message send finished: sent (no code) or failed with its error code."""
    outcome = "failed" if failed_code else "sent"
    SENDS.inc(platform=platform, outcome=outcome, code=failed_code or "")


def record_ai_call(
    feature: str, model: str, outcome: str, *, input_tokens: int = 0, output_tokens: int = 0
) -> None:
    AI_CALLS.inc(feature=feature, model=model, outcome=outcome)
    if input_tokens:
        AI_TOKENS.inc(input_tokens, feature=feature, model=model, direction="input")
    if output_tokens:
        AI_TOKENS.inc(output_tokens, feature=feature, model=model, direction="output")


def record_platform_call(platform: str, endpoint: str, outcome: str) -> None:
    PLATFORM_CALLS.inc(platform=platform, endpoint=endpoint, outcome=outcome)


async def render_stored(redis: Redis) -> list[str]:
    pipe = redis.pipeline(transaction=False)
    for metric in STORED:
        pipe.hgetall(metric.key)
    results = await pipe.execute()
    lines: list[str] = []
    for metric, raw in zip(STORED, results, strict=True):
        stored = {_text(k): _text(v) for k, v in (raw or {}).items()}
        lines.extend(metric.render(stored))
    return lines
