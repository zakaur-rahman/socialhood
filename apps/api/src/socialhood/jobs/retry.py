"""Retries that actually retry (TR-JOB-04).

Only retryable PlatformErrors are retried: 10 s times 2^attempt, capped at 10 minutes. Rate limits
wait for the platform's reported regain time and are not limited by ``max_attempts`` (TR-PL-03),
with a hard ceiling so a job can never loop forever. AI jobs retry retryable AIErrors the same way.
"""

from __future__ import annotations

from procrastinate import BaseRetryStrategy, RetryDecision
from procrastinate.jobs import Job

from socialhood.ai.provider import AIError
from socialhood.platforms.errors import PlatformError

BASE_DELAY_S = 10
MAX_DELAY_S = 600
RATE_LIMIT_CEILING = 50


class PlatformRetry(BaseRetryStrategy):
    def __init__(self, max_attempts: int = 5) -> None:
        self.max_attempts = max_attempts

    def delay_for(self, exception: PlatformError, attempts: int) -> int:
        if exception.is_rate_limit and exception.retry_after_s:
            return max(1, round(exception.retry_after_s))
        return min(MAX_DELAY_S, BASE_DELAY_S << min(attempts, 16))

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if not isinstance(exception, PlatformError) or not exception.retryable:
            return None
        # job.attempts counts previous attempts: 0 on the first run.
        limit = RATE_LIMIT_CEILING if exception.is_rate_limit else self.max_attempts
        if job.attempts + 1 >= limit:
            return None
        return RetryDecision(retry_in={"seconds": self.delay_for(exception, job.attempts)})


class AIRetry(BaseRetryStrategy):
    """Retry retryable AIErrors (timeouts, 429s, 5xx; TR-AI-03) with the same backoff. The
    metering refunded the failed call's credits, so a retry reserves them again."""

    def __init__(self, max_attempts: int = 2) -> None:
        self.max_attempts = max_attempts

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if not isinstance(exception, AIError) or not exception.retryable:
            return None
        if job.attempts + 1 >= self.max_attempts:
            return None
        return RetryDecision(
            retry_in={"seconds": min(MAX_DELAY_S, BASE_DELAY_S << min(job.attempts, 16))}
        )


class BackoffRetry(BaseRetryStrategy):
    """Retry any error with the same backoff (TR-WH-05: webhook processing, up to 5 attempts)."""

    def __init__(self, max_attempts: int = 5) -> None:
        self.max_attempts = max_attempts

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if job.attempts + 1 >= self.max_attempts:
            return None
        return RetryDecision(
            retry_in={"seconds": min(MAX_DELAY_S, BASE_DELAY_S << min(job.attempts, 16))}
        )
