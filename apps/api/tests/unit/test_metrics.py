"""T9.3, TR-OPS-01: metric increments, the Prometheus text format, and the job middleware."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
import sentry_sdk
from procrastinate import exceptions as queue_errors

from socialhood.observability import jobs as observability_jobs
from socialhood.observability.metrics import (
    AI_CALLS,
    AI_TOKENS,
    BUFFER,
    JOB_DURATION,
    JOB_RUNS,
    PLATFORM_CALLS,
    SENDS,
    Counter,
    Gauge,
    Histogram,
    escape_label,
    record_ai_call,
    record_platform_call,
    record_send,
)
from tests.unit.test_sentry import DSN, Capture, make_settings


@pytest.fixture(autouse=True)
def empty_buffer() -> Iterator[None]:
    BUFFER.clear()
    yield
    BUFFER.clear()


def stored(metric: Counter | Histogram) -> dict[str, str]:
    """The buffer's fields for one metric, as they would sit in its Valkey hash."""
    items = BUFFER.drain()
    BUFFER.restore(items)
    return {f: str(v) for (k, f), v in items.items() if k == metric.key}


def test_counter_renders_in_prometheus_text_format() -> None:
    counter = Counter("t_requests_total", "Requests.", ("route", "status"))
    counter.inc(route="/v1/w/{wid}/x", status="200")
    counter.inc(route="/v1/w/{wid}/x", status="200")
    counter.inc(2, route='a"b\\c', status="500")
    assert counter.render(stored(counter)) == [
        "# HELP t_requests_total Requests.",
        "# TYPE t_requests_total counter",
        't_requests_total{route="/v1/w/{wid}/x",status="200"} 2',
        't_requests_total{route="a\\"b\\\\c",status="500"} 2',
    ]


def test_histogram_buckets_are_cumulative_and_inclusive() -> None:
    histogram = Histogram("t_seconds", "Latency.", ("route",), (0.1, 1.0))
    for value in (0.05, 0.1, 0.5, 3.0):
        histogram.observe(value, route="/x")
    assert histogram.render(stored(histogram)) == [
        "# HELP t_seconds Latency.",
        "# TYPE t_seconds histogram",
        't_seconds_bucket{route="/x",le="0.1"} 2',
        't_seconds_bucket{route="/x",le="1"} 3',
        't_seconds_bucket{route="/x",le="+Inf"} 4',
        't_seconds_sum{route="/x"} 3.65',
        't_seconds_count{route="/x"} 4',
    ]


def test_gauges_and_unlabelled_series() -> None:
    assert Gauge("t_open", "Open.").render([({}, 3.0)])[-1] == "t_open 3"


def test_unknown_labels_are_refused() -> None:
    with pytest.raises(ValueError, match="unknown labels"):
        SENDS.inc(platform="instagram", outcome="sent", code="", workspace="w")


def test_label_values_are_escaped() -> None:
    assert escape_label('x\n"y"\\') == 'x\\n\\"y\\"\\\\'


def test_send_ai_and_platform_helpers_increment() -> None:
    record_send("instagram")
    record_send("instagram", failed_code="platform_rejected")
    record_ai_call("reply_suggestion", "gemini-x", "ok", input_tokens=100, output_tokens=20)
    record_ai_call("message_analysis", "gemini-x", "error")
    record_platform_call("instagram", "send_message", "platform_rate_limited")

    assert stored(SENDS) == {
        'platform="instagram",outcome="sent",code=""': "1.0",
        'platform="instagram",outcome="failed",code="platform_rejected"': "1.0",
    }
    assert stored(AI_CALLS) == {
        'feature="reply_suggestion",model="gemini-x",outcome="ok"': "1.0",
        'feature="message_analysis",model="gemini-x",outcome="error"': "1.0",
    }
    assert stored(AI_TOKENS) == {
        'feature="reply_suggestion",model="gemini-x",direction="input"': "100.0",
        'feature="reply_suggestion",model="gemini-x",direction="output"': "20.0",
    }
    assert stored(PLATFORM_CALLS) == {
        'platform="instagram",endpoint="send_message",outcome="platform_rate_limited"': "1.0"
    }


# ---------------------------------------------------------------- the job middleware


@dataclass
class FakeJob:
    task_name: str = "send_message"
    queue: str = "interactive"
    id: int = 7
    attempts: int = 0
    task_kwargs: dict[str, Any] = field(default_factory=lambda: {"workspace_id": "w-1"})


@dataclass
class FakeTask:
    retry: bool = False

    def get_retry_exception(self, *, exception: BaseException, job: Any) -> object | None:
        return object() if self.retry else None


@dataclass
class FakeContext:
    job: FakeJob = field(default_factory=FakeJob)
    task: FakeTask = field(default_factory=FakeTask)


@pytest.fixture
def no_process_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observability_jobs, "_start_process", lambda: None)


@pytest.fixture
def sentry_capture() -> Iterator[Capture]:
    transport = Capture()
    from socialhood.observability.sentry import init_sentry, reset_for_tests

    init_sentry(make_settings(sentry_dsn=DSN), component="worker", transport=transport)
    yield transport
    reset_for_tests()


def job_runs() -> dict[str, str]:
    return stored(JOB_RUNS)


async def test_a_successful_job_is_counted(no_process_start: None) -> None:
    async def work() -> str:
        return "done"

    assert await observability_jobs.observe_job(work, FakeContext(), None) == "done"  # type: ignore[arg-type]
    assert job_runs() == {'task="send_message",lane="interactive",status="succeeded"': "1.0"}
    assert 'task="send_message",lane="interactive",status="succeeded"\ncount' in stored(
        JOB_DURATION
    )


async def test_a_final_failure_is_reported_with_job_and_workspace_tags(
    no_process_start: None, sentry_capture: Capture
) -> None:
    async def work() -> None:
        raise RuntimeError("platform said no")

    with pytest.raises(RuntimeError):
        await observability_jobs.observe_job(work, FakeContext(), None)  # type: ignore[arg-type]
    sentry_sdk.flush()
    [event] = sentry_capture.events
    assert event["tags"]["job"] == "send_message"
    assert event["tags"]["workspace_id"] == "w-1"
    assert event["tags"]["lane"] == "interactive"
    assert event["contexts"]["job"]["id"] == 7
    assert job_runs() == {'task="send_message",lane="interactive",status="failed"': "1.0"}


async def test_a_retry_is_counted_but_not_reported(
    no_process_start: None, sentry_capture: Capture
) -> None:
    async def work() -> None:
        raise RuntimeError("try again")

    with pytest.raises(RuntimeError):
        await observability_jobs.observe_job(work, FakeContext(task=FakeTask(retry=True)), None)  # type: ignore[arg-type]
    assert sentry_capture.events == []
    assert job_runs() == {'task="send_message",lane="interactive",status="retry"': "1.0"}


@pytest.mark.parametrize("error", [queue_errors.JobAborted(), asyncio.CancelledError()])
async def test_an_aborted_job_is_counted_as_aborted(
    no_process_start: None, error: BaseException
) -> None:
    async def work() -> None:
        raise error

    with pytest.raises(type(error)):
        await observability_jobs.observe_job(work, FakeContext(), None)  # type: ignore[arg-type]
    assert job_runs() == {'task="send_message",lane="interactive",status="aborted"': "1.0"}


def test_the_queue_app_runs_the_middleware() -> None:
    from socialhood.jobs.app import app

    assert app.worker_defaults["worker_middleware"] == [observability_jobs.observe_job]
