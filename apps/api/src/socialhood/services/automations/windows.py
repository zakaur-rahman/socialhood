"""Run windows (T4.7; FR-AUT-17): an optional start and end time.

Before its start an active automation shows as Scheduled and does not fire (the runtime only
loads automations inside their window, ``in_window``). At its end the run-window job
(jobs/tasks/automation_windows.py) pauses it and tells the workspace's owners and admins, which
include its creator (automations are admin-only); from then on it shows as Ended.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import Automation, AutomationStatus
from socialhood.schemas.automations import DisplayStatus
from socialhood.services.notifications import notify_admins


def display_status(automation: Automation, now: datetime) -> DisplayStatus:
    """Draft, Scheduled (active, before its start), Active, Paused, or Ended (after its end)."""
    status = automation.status
    if status == AutomationStatus.DRAFT:
        return "draft"
    if automation.ends_at is not None and automation.ends_at <= now:
        return "ended"
    if status == AutomationStatus.ACTIVE:
        if automation.starts_at is not None and automation.starts_at > now:
            return "scheduled"
        return "active"
    return "paused"


def in_window(automation: Automation, now: datetime) -> bool:
    """Whether ``now`` is inside the automation's run window (no window: always)."""
    if automation.starts_at is not None and now < automation.starts_at:
        return False
    return automation.ends_at is None or now < automation.ends_at


async def end_window(session: AsyncSession, automation: Automation, now: datetime) -> None:
    """Pause an automation whose window has ended and announce it once. Runs in the
    automation's workspace scope; the caller has locked the row and commits."""
    automation.status = AutomationStatus.PAUSED
    automation.paused_at = now
    ends_at = automation.ends_at or now
    await notify_admins(
        session,
        type="automation_ended",
        severity="info",
        title=f"{automation.name} ended",
        body="Its run window ended, so it stopped replying. Change the end time to run it again.",
        link=f"/automations/{automation.id}",
        dedupe_key=f"automation_ended:{automation.id}:{ends_at.isoformat()}",
    )
