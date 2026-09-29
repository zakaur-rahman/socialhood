"""run_automation(kind, id) and drain_private_replies(account_id) (T4.4, T4.6, T4.8; F-11
runtime, TR-JOB-07, FR-AUT-22). Thin tasks: the work is in services/automations/runtime.py and
queue.py.

run_automation: a DM, a comment, or (kind "nudge", a run's id) a run's follow nudge; 3 tries
(job catalogue). A retry is safe: a run recorded for the event (or a handled DM, or a queued
nudge) means it was handled, so it sends nothing twice. drain_private_replies: 1 try; it
re-defers itself while runs are queued, and after a crash it comes back in a minute.
"""

from __future__ import annotations

import uuid

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.retry import BackoffRetry
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.services.automations import queue
from socialhood.services.automations import runtime as automations

log = get_logger(__name__)


def _deps() -> PlatformDeps:
    rt = runtime()
    return deps_from(rt.http, rt.settings)


@app.task(name="run_automation", queue=INTERACTIVE, retry=BackoffRetry(max_attempts=3))
async def run_automation(kind: str, trigger_id: str, workspace_id: str, not_found: int = 0) -> None:
    rt = runtime()
    wid = uuid.UUID(workspace_id)
    with workspace_scope(wid):
        await automations.run(
            rt.sessionmaker,
            rt.redis,
            _deps(),
            kind=kind,
            trigger_id=uuid.UUID(trigger_id),
            workspace_id=wid,
            not_found=not_found,
        )


@app.task(name="drain_private_replies", queue=INTERACTIVE)
async def drain_private_replies(workspace_id: str, account_id: str) -> None:
    rt = runtime()
    wid, aid = uuid.UUID(workspace_id), uuid.UUID(account_id)
    with workspace_scope(wid):
        try:
            await queue.run_drain(
                rt.sessionmaker, rt.redis, _deps(), workspace_id=wid, account_id=aid
            )
        except Exception:
            log.exception("drain_private_replies_failed", account_id=account_id)
            await queue.enqueue_drain(aid, wid, delay_s=queue.RETRY_AFTER_S)
            raise
