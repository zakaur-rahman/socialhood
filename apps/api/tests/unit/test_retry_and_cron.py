from __future__ import annotations

from datetime import UTC, datetime

import croniter
import pytest
from procrastinate import App, RetryDecision
from procrastinate.jobs import Job
from procrastinate.periodic import PeriodicDeferrer
from procrastinate.testing import InMemoryConnector

from socialhood.jobs.retry import MAX_DELAY_S, PlatformRetry
from socialhood.platforms.errors import PlatformError


def job(attempts: int) -> Job:
    return Job(
        id=1, queue="interactive", lock=None, queueing_lock=None, task_name="t", attempts=attempts
    )


def seconds(decision: RetryDecision | None) -> float:
    assert decision is not None
    assert decision.retry_at is not None
    return (decision.retry_at - datetime.now(UTC)).total_seconds()


def test_only_retryable_platform_errors_are_retried() -> None:
    strategy = PlatformRetry()
    assert strategy.get_retry_decision(exception=ValueError("x"), job=job(0)) is None
    rejected = PlatformError("platform_rejected")
    assert strategy.get_retry_decision(exception=rejected, job=job(0)) is None


def test_backoff_doubles_and_is_capped() -> None:
    strategy = PlatformRetry(max_attempts=20)
    error = PlatformError("platform_unavailable")
    assert strategy.delay_for(error, 0) == 10
    assert strategy.delay_for(error, 1) == 20
    assert strategy.delay_for(error, 3) == 80
    assert strategy.delay_for(error, 10) == MAX_DELAY_S
    assert 5 < seconds(strategy.get_retry_decision(exception=error, job=job(0))) <= 10


def test_last_attempt_is_not_retried() -> None:
    strategy = PlatformRetry(max_attempts=5)
    error = PlatformError("platform_unavailable")
    assert strategy.get_retry_decision(exception=error, job=job(3)) is not None
    assert strategy.get_retry_decision(exception=error, job=job(4)) is None


def test_rate_limits_wait_for_regain_time_and_do_not_use_up_tries() -> None:
    strategy = PlatformRetry(max_attempts=5)
    error = PlatformError("platform_rate_limited", retry_after_s=900)
    decision = strategy.get_retry_decision(exception=error, job=job(10))
    assert 890 < seconds(decision) <= 900


def test_the_seconds_field_of_the_cron_syntax_works() -> None:
    start = datetime(2026, 9, 28, 10, 0, 0, tzinfo=UTC)
    it = croniter.croniter("* * * * * */30", start)
    assert it.get_next(datetime) == datetime(2026, 9, 28, 10, 0, 30, tzinfo=UTC)
    assert it.get_next(datetime) == datetime(2026, 9, 28, 10, 1, 0, tzinfo=UTC)


def test_periodic_tasks_accept_a_seconds_field() -> None:
    app = App(connector=InMemoryConnector())

    @app.periodic(cron="* * * * * */30", periodic_id="every30")
    @app.task(name="every30")
    async def every30(timestamp: int) -> None:
        return None

    deferrer = PeriodicDeferrer(registry=app.periodic_registry)
    at = datetime(2026, 9, 28, 10, 0, 1, tzinfo=UTC).timestamp()
    assert deferrer.get_next_tick(at=at) == pytest.approx(29)
