"""Platform errors (TR-PL-03).

The mapping from platform error codes arrives with the adapters (T2.3).
"""

from __future__ import annotations

# Codes services act on. Only the retryable ones matter to the job retry strategy.
RETRYABLE_CODES = frozenset({"platform_rate_limited", "platform_unavailable"})


class PlatformError(Exception):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool | None = None,
        platform_code: str | None = None,
        message: str = "",
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.retryable = code in RETRYABLE_CODES if retryable is None else retryable
        self.platform_code = platform_code
        self.message = message
        # Seconds until the platform says calls may resume (rate limits), when it says so.
        self.retry_after_s = retry_after_s

    @property
    def is_rate_limit(self) -> bool:
        return self.code == "platform_rate_limited"
