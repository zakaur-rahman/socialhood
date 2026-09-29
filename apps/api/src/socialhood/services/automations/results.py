"""A run's result from what it sent (T4.4, T4.6; FR-AUT-04, FR-AUT-08, FR-AUT-16).

A DM automation's run is ``sent`` once its message is handed to the send pipeline, like a
scheduled message (Q-015), and mirrors the message's outcome: ``failed`` with its reason if the
send fails, ``sent`` again after a successful retry. ``follow_message`` is called wherever a
send's result is decided (the send job, echo reconciliation, the sweeper).

A comment automation's run has two parts. The public reply is posted when the run is created;
its failure is kept in ``error_code``/``error_message`` while the private reply waits in the
queue. When the private reply is sent, fails or is skipped, ``finish_comment_run`` decides:
both parts (or the only one) worked → ``sent``; one of two failed → ``partial``; nothing reached
the commenter → ``failed``.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import AutomationRun, RunResult
from socialhood.models.inbox import Message, MessageStatus
from socialhood.repositories import automation_runs as runs

PrivateOutcome = Literal["sent", "failed", "skipped"]
DELIVERED = frozenset({MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ})
PUBLIC_PREFIX = "Public reply: "
PRIVATE_PREFIX = "DM: "
NOTHING_SENT = (
    "nothing_sent",
    "The automation is set to public reply only and has no public reply, so nothing was sent.",
)


def public_attempted(run: AutomationRun) -> bool:
    return run.public_reply_variant is not None


def public_failed(run: AutomationRun) -> bool:
    return public_attempted(run) and run.error_code is not None


def finish_comment_run(
    run: AutomationRun,
    private: PrivateOutcome,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Settle a queued comment run once its private reply is decided (sets attributes; the
    caller flushes). Does nothing to a run that is no longer queued."""
    if run.result != RunResult.QUEUED:
        return
    attempted, failed = public_attempted(run), public_failed(run)
    if private == "sent":
        run.result = RunResult.PARTIAL if failed else RunResult.SENT
        if not failed:
            run.error_code = run.error_message = None
        return
    if private == "skipped":
        if attempted and not failed:
            run.result = RunResult.SENT
        else:
            run.result = RunResult.FAILED
            if not attempted:
                run.error_code, run.error_message = NOTHING_SENT
        return
    reason = f"{PRIVATE_PREFIX}{error_message or 'The DM could not be sent.'}"
    if attempted and not failed:
        run.result = RunResult.PARTIAL
        run.error_code, run.error_message = error_code or "failed", reason
    elif failed:
        run.result = RunResult.FAILED
        run.error_message = f"{run.error_message} {reason}"
    else:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = error_code or "failed", reason


def record_public(
    run: AutomationRun,
    *,
    reply_id: str | None,
    error: tuple[str, str] | None,
    dm_planned: bool,
) -> None:
    """Record the public reply's result. A run without a DM is settled by it; a queued one
    keeps its failure for the private reply to settle; one the private reply already settled
    (the queue can be faster than the public reply) is corrected."""
    run.public_reply_platform_id = reply_id
    if error is None:
        return
    code, reason = error[0], f"{PUBLIC_PREFIX}{error[1]}"
    if not dm_planned:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = code, reason
    elif run.result == RunResult.QUEUED:
        run.error_code, run.error_message = code, reason
    elif run.result == RunResult.SENT:
        run.result = RunResult.PARTIAL
        run.error_code, run.error_message = code, reason
    elif run.result == RunResult.PARTIAL:  # the DM failed too
        run.result = RunResult.FAILED
        run.error_message = f"{reason} {run.error_message or ''}".strip()


async def follow_message(session: AsyncSession, msg: Message) -> None:
    """Mirror a sent or failed automation message onto its run."""
    if msg.automation_run_id is None or msg.status not in (*DELIVERED, MessageStatus.FAILED):
        return
    run = await runs.lock(session, msg.automation_run_id)
    if run is not None:
        apply_message(run, msg)
        await session.flush()


def apply_message(run: AutomationRun, msg: Message) -> None:
    """``follow_message`` for a run already loaded (and locked); sets attributes only."""
    if run.private_reply_message_id != msg.id or msg.status not in (
        *DELIVERED,
        MessageStatus.FAILED,
    ):
        return
    delivered = msg.status in DELIVERED
    if run.trigger_comment_id is not None:
        finish_comment_run(
            run,
            "sent" if delivered else "failed",
            error_code=msg.error_code,
            error_message=msg.error_message,
        )
    elif run.result in (RunResult.SENT, RunResult.FAILED):
        run.result = RunResult.SENT if delivered else RunResult.FAILED
        run.error_code = None if delivered else msg.error_code
        run.error_message = None if delivered else msg.error_message
