"""What the sandbox adapter sent (TR-PL-07), and failures to inject into its sends.

The state lives in the process that sends (the worker, or a test). Two ways to make a send fail:
``fail_next(code)`` queues failures for the next sends (tests), and a message whose text contains
``[sandbox:fail=<code>]`` fails with that code on every attempt, so end-to-end runs can trigger a
Failed bubble from the composer. ``delivery_unknown`` behaves like a timeout after the request
went out (TR-JOB-05).
"""

from __future__ import annotations

import re
import secrets
from collections import deque
from dataclasses import dataclass

from socialhood.platforms.base import OutboundMessage
from socialhood.platforms.errors import PlatformError

DIRECTIVE = re.compile(r"\[sandbox:fail=([a-z_]+)\]")
KEEP = 200


@dataclass(frozen=True)
class SandboxSend:
    account_ref: str
    recipient_ref: str
    message: OutboundMessage
    platform_message_id: str


SENT: deque[SandboxSend] = deque(maxlen=KEEP)
SEEN: deque[tuple[str, str]] = deque(maxlen=KEEP)  # (account_ref, recipient_ref) marked seen
_FAILURES: deque[PlatformError] = deque()


def fail_next(code: str, *, times: int = 1, retry_after_s: float | None = None) -> None:
    for _ in range(times):
        _FAILURES.append(_error(code, retry_after_s))


def reset() -> None:
    SENT.clear()
    SEEN.clear()
    _FAILURES.clear()


def failure_for(message: OutboundMessage) -> PlatformError | None:
    if _FAILURES:
        return _FAILURES.popleft()
    match = DIRECTIVE.search(message.text or "")
    return _error(match.group(1), None) if match else None


def record(account_ref: str, recipient_ref: str, message: OutboundMessage) -> str:
    mid = f"sandbox_mid_{secrets.token_hex(8)}"
    SENT.append(SandboxSend(account_ref, recipient_ref, message, mid))
    return mid


def _error(code: str, retry_after_s: float | None) -> PlatformError:
    retryable = False if code == "delivery_unknown" else None
    return PlatformError(
        code,
        retryable=retryable,
        platform_code="sandbox",
        message=f"Sandbox failure: {code}",
        retry_after_s=retry_after_s,
    )
