"""Jobs a dead worker left ``doing`` (TR-JOB-03, TR-JOB-05): the rules recover_stalled_jobs applies.

A worker that stops without finishing its jobs (Render's SIGKILL at the end of a deploy's
shutdown grace, a crash, an out-of-memory kill) leaves them ``doing`` for good. Nothing picks them
up again, and one holding a run lock (``conv:{id}``, ``pub:{id}``, ``agent:{id}``…) blocks every
later job with that lock: the next send in the conversation, the sweeper's re-queued publish, the
resumed agent run. A job is stalled once its worker's heartbeat (every 10 s) is STALLED_AFTER_S
old, or its worker row is gone; recover_stalled_jobs (jobs/tasks/maintenance.py, every 2 minutes,
bulk lane) then settles it by its task's class in RECOVERY:

- RETRY: the task is safe to run again from the start: it re-checks the state it would change
  (a row's status, a unique row, a stable client id, an Idempotency-Key) or only reads and
  recomputes. The job goes back to ``todo`` at once, while it has used fewer than MAX_ATTEMPTS
  attempts (a job that kills its worker every time stops there); after that it is failed with an
  alert. A job with the same queueing lock already waiting does the same work, so the stalled one
  is aborted instead.
- SWEEPER: a domain sweeper already recovers the work and must decide what happened (a send
  that may have reached the platform becomes delivery_unknown, TR-JOB-05). The job is never run
  again; it is only aborted, so its run lock no longer holds up the job the sweeper queues.
- FAIL: not safe to run again and no sweeper: failed, so it is listed by
  ``python -m socialhood.ops failed-jobs list``, with an ``alert`` log event. So is a job whose
  task isn't in RECOVERY (tests/unit/test_job_recovery.py fails for a registered task missing
  from it).

STALLED_AFTER_S has to stay above the worker's shutdown grace on Render (maxShutdownDelaySeconds,
infra/render.yaml) plus the heartbeat interval: a worker stops its heartbeat as soon as it is
asked to stop and may still be finishing jobs until the grace runs out (docs/ops/runbook.md).
"""

from __future__ import annotations

from enum import StrEnum

from procrastinate import App, exceptions
from procrastinate.jobs import Job, Status

from socialhood.observability.logging import get_logger

log = get_logger(__name__)

HEARTBEAT_INTERVAL_S = 10.0  # the worker's update_heartbeat_interval (Procrastinate's default)
STALLED_AFTER_S = 90.0  # > 60 s of shutdown grace on Render + one heartbeat interval
MAX_ATTEMPTS = 3  # a stalled RETRY job goes back to todo while job.attempts is below this


class Recovery(StrEnum):
    RETRY = "retry"
    SWEEPER = "sweeper"
    FAIL = "fail"


R, S, F = Recovery.RETRY, Recovery.SWEEPER, Recovery.FAIL

# Every registered task, by name. Keep it next to the task when adding one.
RECOVERY: dict[str, Recovery] = {
    # ---- periodic: each tick re-reads the state and does what is due, so a re-run is harmless
    "ping": R,
    "sweep_stuck": R,
    "check_webhook_health": R,
    "check_failures": R,
    "recover_stalled_jobs": R,
    "refresh_tokens": R,
    "reconcile_subscriptions": R,
    "sync_all_media": R,
    "sweep_messages": R,
    "dispatch_due": R,  # claims with FOR UPDATE SKIP LOCKED; claimed rows are the sweeper's
    "sweep_stuck_scheduled": R,
    "end_automation_windows": R,
    "check_closing_windows": R,  # one transaction: reminded conversations are no longer due
    "dispatch_comment_analysis": R,
    "dispatch_post_summaries": R,
    "snapshot_post_metrics": R,
    "snapshot_account_daily": R,
    "dispatch_due_posts": R,
    "sweep_stuck_posts": R,
    "sweep_agent_runs": R,
    "reconcile_billing": R,
    "sweep_email_outbox": R,
    "send_weekly_digests": R,  # weekly_digests' unique (workspace, week_start)
    "sweep_deletions": R,
    "purge_expired": R,
    # ---- reads, AI and recomputation: they overwrite or skip what already exists
    "fetch_contact_profile": R,
    "ingest_media": R,  # skips an attachment that already has its asset
    "delete_unsent_media": R,  # deleting twice is a no-op; retried on any error already
    "mark_read": R,  # a read receipt sent twice changes nothing
    "sync_media": R,
    "backfill_account": R,
    "backfill_comments": R,
    "snapshot_account_posts": R,  # each window is captured once
    "snapshot_account_day": R,  # one row per account and day
    "ingest_knowledge_source": R,  # re-ingests the version; retried on any error already
    "analyze_conversation": R,  # "already_analysed" when the message has its analysis
    "summarize_conversation": R,
    "analyze_comments": R,
    "summarize_post": R,
    "suggest_reply": R,  # skips a message that already has this generation
    "decide_auto_reply": R,  # one transaction; a stable client id per suggestion, pending only
    "run_automation": R,  # a run recorded for the event means handled; retried on any error
    "drain_private_replies": R,  # each reply is committed ``sending`` before the call
    "delete_platform_user_data": R,  # until the request is completed
    "purge_workspace": R,  # retried on any error already; sweep_deletions re-queues it
    "cancel_orphan_subscription": R,  # an ended subscription counts as done
    # ---- recovered by their own sweepers (never run again here)
    "send_message": S,  # sweep_messages: sending → delivery_unknown, queued → enqueued again
    "send_private_reply": S,  # sweep_messages: sending → delivery_unknown, queued → its own job
    "send_scheduled": S,  # sweep_stuck_scheduled: the claim goes back to scheduled, or fails
    "publish_target": S,  # sweep_stuck_posts: back to pending (or failed after 3 claims)
    "poll_container": S,  # sweep_stuck_posts: the next poll is queued
    "run_agent": S,  # sweep_agent_runs: resumes from its last step, or fails the run
    "process_webhook_event": S,  # sweep_stuck: the event is still ``received``
    "deliver_email": S,  # sweep_email_outbox: still ``queued``; the resend has the same key
    # ---- not safe to run again, and nothing else recovers them
    "post_first_comment": F,  # the comment may already be on the post
    "deliver_push": F,  # the devices already reached would be notified twice
}


def recovery_for(task_name: str) -> Recovery:
    """The task's class; FAIL for a task that isn't listed."""
    return RECOVERY.get(task_name, Recovery.FAIL)


async def recover_stalled(app: App, *, stalled_after_s: float = STALLED_AFTER_S) -> dict[str, int]:
    """Settle every job whose worker is dead (see the module docstring); returns counts."""
    pruned = await app.job_manager.prune_stalled_workers(stalled_after_s)
    stalled = await app.job_manager.get_stalled_jobs(seconds_since_heartbeat=stalled_after_s)
    counts = {"retried": 0, "released": 0, "failed": 0, "skipped": 0}
    for job in stalled:
        counts[await _settle(app, job)] += 1
    if pruned or any(counts.values()):
        log.info("recover_stalled_jobs", pruned_workers=len(pruned), **counts)
    return counts


async def _settle(app: App, job: Job) -> str:
    rule = recovery_for(job.task_name)
    manager = app.job_manager
    fields = {"job_id": job.id, "task": job.task_name, "attempts": job.attempts}
    try:
        if rule is Recovery.RETRY and job.attempts < MAX_ATTEMPTS:
            try:
                await manager.retry_job(job)
            except exceptions.UniqueViolation:
                # Its queueing lock: the same work is already waiting in another job.
                await manager.finish_job(job, Status.ABORTED, delete_job=False)
                log.info("stalled_job_released", reason="already_queued", **fields)
                return "released"
            log.warning("stalled_job_retried", **fields)
            return "retried"
        if rule is Recovery.SWEEPER:
            await manager.finish_job(job, Status.ABORTED, delete_job=False)
            log.info("stalled_job_released", reason="sweeper", **fields)
            return "released"
        await manager.finish_job(job, Status.FAILED, delete_job=False)
    except exceptions.ConnectorException:
        # It finished, or another sweep settled it, since it was listed.
        log.info("stalled_job_moved_on", **fields)
        return "skipped"
    if rule is Recovery.RETRY:
        why = f"stalled again after {job.attempts} attempts"
    elif job.task_name in RECOVERY:
        why = "stalled, and not safe to run again"
    else:
        why = "stalled, and its task has no recovery rule"
    log.error("alert", kind="stalled_job", detail=f"{job.task_name} job {job.id} {why}", **fields)
    return "failed"
