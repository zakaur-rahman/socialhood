"""The stalled-job rules (jobs/recovery.py): every task has a class, and the timing holds.

A new task fails ``test_every_registered_task_is_classified`` until it is added to RECOVERY with
the class its code supports: RETRY (safe to run again from the start), SWEEPER (a domain sweeper
recovers its work) or FAIL (neither).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from socialhood.jobs.app import BULK, app
from socialhood.jobs.failed import PLATFORM_WRITE_TASKS, FailedJob
from socialhood.jobs.recovery import (
    HEARTBEAT_INTERVAL_S,
    RECOVERY,
    STALLED_AFTER_S,
    Recovery,
    recovery_for,
)

RENDER_YAML = Path(__file__).resolve().parents[4] / "infra" / "render.yaml"


def registered_tasks() -> set[str]:
    """This app's tasks (Procrastinate's built-in ones aside)."""
    app.perform_import_paths()
    return {
        name
        for name, task in app.tasks.items()
        if not task.func.__module__.startswith("procrastinate.")
    }


def test_every_registered_task_is_classified() -> None:
    missing = sorted(registered_tasks() - RECOVERY.keys())
    assert missing == [], (
        f"Add {missing} to RECOVERY in jobs/recovery.py: RETRY if the task is safe to run again "
        "from the start, SWEEPER if a sweeper recovers its work, else FAIL."
    )


def test_every_classified_task_exists() -> None:
    assert sorted(RECOVERY.keys() - registered_tasks()) == []


def test_an_unknown_task_is_never_rerun() -> None:
    assert recovery_for("no_such_task") is Recovery.FAIL


def test_platform_writes_are_never_retried_blindly() -> None:
    """A platform write is RETRY only where its code guards against sending twice (a recorded
    run, a message committed ``sending`` before the call); the others belong to a sweeper or
    fail."""
    guarded = {"run_automation", "drain_private_replies"}
    for task in PLATFORM_WRITE_TASKS - guarded:
        assert RECOVERY[task] is not Recovery.RETRY, task


def test_tasks_that_are_not_safe_to_rerun_are_not_retried_from_ops() -> None:
    for task, rule in RECOVERY.items():
        job = FailedJob(1, task, "interactive", {}, 1, datetime.now(UTC))
        if rule is Recovery.FAIL:
            assert not job.retryable_from_ops, task


def test_the_sweep_runs_every_two_minutes_on_the_bulk_lane() -> None:
    app.perform_import_paths()
    task = app.tasks["recover_stalled_jobs"]
    assert task.queue == BULK
    [periodic] = [p for p in app.periodic_registry.periodic_tasks.values() if p.task is task]
    assert periodic.cron == "*/2 * * * *"


def test_a_stopping_worker_is_never_taken_for_a_dead_one() -> None:
    """A worker asked to stop stops its heartbeat at once and may run jobs until Render kills
    it. That grace plus one heartbeat interval must stay under STALLED_AFTER_S, and a starting
    worker prunes other workers on the same threshold."""
    text = RENDER_YAML.read_text(encoding="utf-8")
    graces = [
        int(grace)
        for block in re.split(r"\n\s*- type: ", text)
        if block.startswith("worker")
        for grace in re.findall(r"maxShutdownDelaySeconds: (\d+)", block)
    ]
    assert len(graces) == 2  # production and staging
    assert max(graces) + HEARTBEAT_INTERVAL_S < STALLED_AFTER_S
    assert app.worker_defaults["stalled_worker_timeout"] == STALLED_AFTER_S
    assert app.worker_defaults["update_heartbeat_interval"] == HEARTBEAT_INTERVAL_S
    # No time limit of Procrastinate's own: a job it aborted would end ``aborted``, never
    # retried nor listed as failed; one Render kills is settled by recover_stalled_jobs.
    assert "shutdown_graceful_timeout" not in app.worker_defaults
