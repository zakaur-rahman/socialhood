"""A run's result from what it sent (T4.4, T4.6, T4.8; FR-AUT-04, FR-AUT-08, FR-AUT-16,
FR-AUT-21, FR-AUT-22).

A DM automation's run is ``sent`` once its message is handed to the send pipeline, like a
scheduled message (Q-015), and mirrors the message's outcome: ``failed`` with its reason if the
send fails, ``sent`` again after a successful retry. ``follow_message`` is called wherever a
send's result is decided (the send job, echo reconciliation, the sweeper).

A comment automation's run has two parts. The public reply is posted when the run is created;
its failure is kept in ``error_code``/``error_message`` while the private reply waits in the
queue. When the private reply is sent, fails or is skipped, ``finish_comment_run`` decides:
both parts (or the only one) worked → ``sent``; one of two failed → ``partial``; nothing reached
the commenter → ``failed``.

Tap first (FR-AUT-21): when the private reply was the opening, a sent opening leaves the run
``awaiting_reply`` (keeping a public reply's failure). The commenter's answer hands the message to
the send pipeline (``hand_over``: ``sent``, or ``partial`` if the public reply had failed) and
the run then mirrors that message like a DM run, the public reply's failure included.

When a run's message reaches Instagram, the follow nudge may be due (services/automations/nudge,
FR-AUT-22).
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
DM_FAILED = "The DM could not be sent."


def public_attempted(run: AutomationRun) -> bool:
    return run.public_reply_variant is not None


def public_failed(run: AutomationRun) -> bool:
    return public_attempted(run) and run.error_code is not None


def public_error(run: AutomationRun) -> tuple[str, str] | None:
    """The public reply's failure kept on the run ("Public reply: …"), without any DM part."""
    message = run.error_message or ""
    if not message.startswith(PUBLIC_PREFIX):
        return None
    return run.error_code or "failed", message.split(f" {PRIVATE_PREFIX}", 1)[0]


def finish_comment_run(
    run: AutomationRun,
    private: PrivateOutcome,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    opening: bool = False,
) -> None:
    """Settle a queued comment run once its private reply is decided (sets attributes; the
    caller flushes). Does nothing to a run that is no longer queued. A sent ``opening`` (tap
    first) leaves the run waiting for the commenter's answer."""
    if run.result != RunResult.QUEUED:
        return
    attempted, failed = public_attempted(run), public_failed(run)
    if private == "sent" and opening:
        run.result = RunResult.AWAITING_REPLY  # a public reply's failure stays for later
        return
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
    reason = f"{PRIVATE_PREFIX}{error_message or DM_FAILED}"
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
    """Record the public reply's result. A run without a DM is settled by it; a queued one (or
    one whose opening waits for an answer) keeps its failure for the DM to settle; one the
    private reply already settled (the queue can be faster than the public reply) is corrected."""
    run.public_reply_platform_id = reply_id
    if error is None:
        return
    code, reason = error[0], f"{PUBLIC_PREFIX}{error[1]}"
    if not dm_planned:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = code, reason
    elif run.result in (RunResult.QUEUED, RunResult.AWAITING_REPLY):
        run.error_code, run.error_message = code, reason
    elif run.result == RunResult.SENT:
        run.result = RunResult.PARTIAL
        run.error_code, run.error_message = code, reason
    elif run.result == RunResult.PARTIAL:  # the DM failed too
        run.result = RunResult.FAILED
        run.error_message = f"{reason} {run.error_message or ''}".strip()


# ---------------------------------------------------------------- tap first (FR-AUT-21)


def hand_over(run: AutomationRun) -> None:
    """The commenter answered and the message is queued: ``sent``, or ``partial`` when the
    public reply had failed (its reason stays)."""
    public = public_error(run)
    if public is None:
        run.result = RunResult.SENT
        run.error_code = run.error_message = None
    else:
        run.result = RunResult.PARTIAL
        run.error_code, run.error_message = public


def answered_failed(run: AutomationRun, code: str, message: str) -> None:
    """The message after the answer failed (refused by the send pipeline, or by Instagram)."""
    public = public_error(run)
    reason = f"{PRIVATE_PREFIX}{message or DM_FAILED}"
    if public is not None:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = public[0], f"{public[1]} {reason}"
    elif public_attempted(run):
        run.result = RunResult.PARTIAL
        run.error_code, run.error_message = code, reason
    else:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = code, reason


# ---------------------------------------------------------------- following a send


async def follow_message(session: AsyncSession, msg: Message) -> None:
    """Mirror a sent or failed automation message onto its run; once the run's message reached
    Instagram, see whether the follow nudge is due."""
    from socialhood.services.automations import nudge

    if msg.automation_run_id is None or msg.status not in (*DELIVERED, MessageStatus.FAILED):
        return
    run = await runs.lock(session, msg.automation_run_id)
    if run is None:
        return
    opening = False
    if (
        run.result == RunResult.QUEUED
        and run.trigger_comment_id is not None
        and run.private_reply_message_id == msg.id
    ):
        # An opening's echo can settle it before the queue does (C-011).
        opening = bool(msg.quick_replies) or await _opens_first(session, run)
    apply_message(run, msg, opening=opening)
    await session.flush()
    if msg.status in DELIVERED and run.private_reply_message_id == msg.id:
        await nudge.after_message(session, run)


async def _opens_first(session: AsyncSession, run: AutomationRun) -> bool:
    from socialhood.services.automations import actions

    automation = await runs.get_automation(session, run.automation_id)
    return automation is not None and actions.opens_first(automation)


def apply_message(run: AutomationRun, msg: Message, *, opening: bool = False) -> None:
    """``follow_message`` for a run already loaded (and locked); sets attributes only.
    ``opening``: the message is a tap-first opening (FR-AUT-21)."""
    if run.private_reply_message_id != msg.id or msg.status not in (
        *DELIVERED,
        MessageStatus.FAILED,
    ):
        return
    delivered = msg.status in DELIVERED
    if run.trigger_comment_id is not None and run.confirmed_at is not None:
        # The message that followed a tap-first answer.
        if run.result not in (RunResult.SENT, RunResult.PARTIAL, RunResult.FAILED):
            return
        if delivered:
            hand_over(run)
        else:
            answered_failed(run, msg.error_code or "failed", msg.error_message or DM_FAILED)
    elif run.trigger_comment_id is not None:
        finish_comment_run(
            run,
            "sent" if delivered else "failed",
            error_code=msg.error_code,
            error_message=msg.error_message,
            opening=opening,
        )
    elif run.result in (RunResult.SENT, RunResult.FAILED):
        run.result = RunResult.SENT if delivered else RunResult.FAILED
        run.error_code = None if delivered else msg.error_code
        run.error_message = None if delivered else msg.error_message
