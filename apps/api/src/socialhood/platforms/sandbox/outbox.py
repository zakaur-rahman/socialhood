"""What the sandbox adapter sent (TR-PL-07), and failures to inject into its sends.

The state lives in the process that sends (the worker, or a test). Two ways to make a send fail:
``fail_next(code)`` queues failures for the next sends (tests; ``kind`` limits one to DMs,
private replies or public comment replies), and a message whose text contains
``[sandbox:fail=<code>]`` fails with that code on every attempt, so end-to-end runs can trigger a
Failed bubble from the composer. ``delivery_unknown`` behaves like a timeout after the request
went out (TR-JOB-05).

Tap first and the follow nudge (FR-AUT-21, FR-AUT-22): quick replies are recorded with the
message; ``reject_quick_replies()`` makes Instagram-like refusals of any send or private reply
that carries them (to exercise the text-only fallback). ``set_follows(ref, value)`` sets what the
profile says about a contact following the account; without it a sandbox contact whose id
contains ``follower`` follows, one whose id contains ``unknown`` is unknown, and anyone else does
not follow, so the nudge can be seen in development.
"""

from __future__ import annotations

import re
import secrets
from collections import deque
from dataclasses import dataclass
from typing import Literal

from socialhood.platforms.base import OutboundMessage
from socialhood.platforms.errors import PlatformError

DIRECTIVE = re.compile(r"\[sandbox:fail=([a-z_]+)\]")
KEEP = 200

SendKind = Literal["send", "private_reply", "comment_reply"]


@dataclass(frozen=True)
class SandboxSend:
    account_ref: str
    recipient_ref: str  # the contact; for a private reply, the comment
    message: OutboundMessage
    platform_message_id: str


@dataclass(frozen=True)
class SandboxCommentReply:
    account_ref: str
    comment_ref: str
    text: str
    platform_comment_id: str


SENT: deque[SandboxSend] = deque(maxlen=KEEP)
PRIVATE_REPLIES: deque[SandboxSend] = deque(maxlen=KEEP)
COMMENT_REPLIES: deque[SandboxCommentReply] = deque(maxlen=KEEP)
SEEN: deque[tuple[str, str]] = deque(maxlen=KEEP)  # (account_ref, recipient_ref) marked seen
_FAILURES: deque[tuple[SendKind | None, PlatformError]] = deque()
FOLLOWS: dict[str, bool | None] = {}  # contact ref -> is_user_follow_business
_REJECT_QUICK_REPLIES: list[bool] = [False]


def set_follows(contact_ref: str, value: bool | None) -> None:
    FOLLOWS[contact_ref] = value


def follows(contact_ref: str) -> bool | None:
    if contact_ref in FOLLOWS:
        return FOLLOWS[contact_ref]
    if "unknown" in contact_ref:
        return None
    return "follower" in contact_ref


def reject_quick_replies(on: bool = True) -> None:
    _REJECT_QUICK_REPLIES[0] = on


def quick_reply_failure(message: OutboundMessage) -> PlatformError | None:
    """Instagram's refusal of quick replies, when switched on (the runtime then sends text)."""
    if not (_REJECT_QUICK_REPLIES[0] and message.quick_replies):
        return None
    return PlatformError(
        "platform_rejected",
        platform_code="100",
        message="Sandbox: quick replies are not supported here",
    )


def fail_next(
    code: str,
    *,
    times: int = 1,
    retry_after_s: float | None = None,
    kind: SendKind | None = None,
) -> None:
    for _ in range(times):
        _FAILURES.append((kind, _error(code, retry_after_s)))


def reset() -> None:
    SENT.clear()
    PRIVATE_REPLIES.clear()
    COMMENT_REPLIES.clear()
    SEEN.clear()
    _FAILURES.clear()
    FOLLOWS.clear()
    _REJECT_QUICK_REPLIES[0] = False


def failure_for(message: OutboundMessage, kind: SendKind = "send") -> PlatformError | None:
    return failure_for_text(message.text, kind)


def failure_for_text(text: str | None, kind: SendKind) -> PlatformError | None:
    for index, (only, error) in enumerate(_FAILURES):
        if only is None or only == kind:
            del _FAILURES[index]
            return error
    match = DIRECTIVE.search(text or "")
    return _error(match.group(1), None) if match else None


def record(account_ref: str, recipient_ref: str, message: OutboundMessage) -> str:
    mid = f"sandbox_mid_{secrets.token_hex(8)}"
    SENT.append(SandboxSend(account_ref, recipient_ref, message, mid))
    return mid


def record_private_reply(account_ref: str, comment_ref: str, message: OutboundMessage) -> str:
    mid = f"sandbox_mid_{secrets.token_hex(8)}"
    PRIVATE_REPLIES.append(SandboxSend(account_ref, comment_ref, message, mid))
    return mid


def record_comment_reply(account_ref: str, comment_ref: str, text: str) -> str:
    reply_id = f"sandbox_reply_{secrets.token_hex(8)}"
    COMMENT_REPLIES.append(SandboxCommentReply(account_ref, comment_ref, text, reply_id))
    return reply_id


def _error(code: str, retry_after_s: float | None) -> PlatformError:
    retryable = False if code == "delivery_unknown" else None
    return PlatformError(
        code,
        retryable=retryable,
        platform_code="sandbox",
        message=f"Sandbox failure: {code}",
        retry_after_s=retry_after_s,
    )
