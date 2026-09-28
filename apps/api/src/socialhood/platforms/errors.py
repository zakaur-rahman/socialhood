"""Platform errors (TR-PL-03). Adapters raise PlatformError; services act on ``code`` only.

The mapping follows Meta's Graph error codes; T0.9 confirms them against real responses.
"""

from __future__ import annotations

import json
from typing import Any

# Codes services act on. Only the retryable ones matter to the job retry strategy.
RETRYABLE_CODES = frozenset({"platform_rate_limited", "platform_unavailable"})

RATE_LIMIT_CODES = frozenset({4, 17, 32, 613, 80002})
UNAVAILABLE_CODES = frozenset({1, 2})
PUBLISH_TEMPORARY = 2207008
PUBLISH_QUOTA = 2207042


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


def _regain_seconds(headers: dict[str, str]) -> float | None:
    """Minutes until access returns, from X-Business-Use-Case-Usage, as seconds."""
    raw = headers.get("x-business-use-case-usage")
    if not raw:
        return None
    try:
        usage: dict[str, list[dict[str, Any]]] = json.loads(raw)
    except ValueError:
        return None
    minutes = [
        float(entry.get("estimated_time_to_regain_access") or 0)
        for entries in usage.values()
        for entry in entries
    ]
    longest = max(minutes, default=0.0)
    return longest * 60 if longest > 0 else None


def map_graph_error(status: int, body: Any, headers: dict[str, str] | None = None) -> PlatformError:
    """Turn a failed Graph response into the PlatformError services understand."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    error = body.get("error", {}) if isinstance(body, dict) else {}
    code = error.get("code")
    subcode = error.get("error_subcode")
    message = str(error.get("error_user_msg") or error.get("message") or f"HTTP {status}")
    platform_code = f"{code}/{subcode}" if subcode else (str(code) if code is not None else None)

    def build(ours: str, **kw: Any) -> PlatformError:
        kw.setdefault("message", message)
        return PlatformError(ours, platform_code=platform_code, **kw)

    if code == 190:
        return build("account_needs_reconnect")
    if code == 10 and subcode == 2534022:
        return build("reply_window_closed")
    if code == 551:
        return build("recipient_unavailable")
    if code in RATE_LIMIT_CODES or status == 429:
        return build("platform_rate_limited", retry_after_s=_regain_seconds(headers))
    if subcode == PUBLISH_TEMPORARY:
        return build("platform_unavailable")
    if subcode == PUBLISH_QUOTA:
        return build("platform_rejected", message="Instagram's daily publishing limit reached")
    if code in UNAVAILABLE_CODES or status >= 500:
        return build("platform_unavailable")
    return build("platform_rejected")
