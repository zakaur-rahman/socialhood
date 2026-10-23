"""Activity alerts (GR-05): tell the owners and admins when an automation keeps failing.

An automation whose runs fail (or only half work) FAILING_RUNS times within the last hour gets
one in-app notification, pushed to members with the "Needs you" switch on (PUSH_EVENT_OF_TYPE),
that links to the Activity page filtered to it. A repeat inside the same ALERT_BUCKET is one
notification (dedupe_key), so a long outage reminds every six hours, not every tick.

An account that needs reconnecting is not alerted here: ``connections.mark_needs_reconnect``
already notifies (and emails) once per broken connection, with a link to Settings, Connections.
Failed webhook deliveries alert through GR-04's endpoint-disabled notification.

The job (jobs/tasks/activity.py) finds the automations across workspaces, in tenant_bypass_scope,
and calls ``alert`` inside each workspace's scope.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.services.activity import reasons
from socialhood.services.notifications import notify_admins

FAILING_RUNS = 5  # failed or partial runs of one automation within the window
WINDOW = timedelta(hours=1)
ALERT_BUCKET = timedelta(hours=6)  # at most one notification per automation per bucket


def dedupe_key(automation_id: object, now: datetime) -> str:
    bucket = int(now.timestamp() // ALERT_BUCKET.total_seconds())
    return f"automation_failing:{automation_id}:{bucket}"


async def alert(session: AsyncSession, row: Any, now: datetime) -> bool:
    """Notify the current workspace's owners and admins about one failing automation (a row of
    repositories/activity.failing_automations). False when this bucket already had its alert."""
    reason = reasons.explain(row.common_code, platform=row.platform)
    created = await notify_admins(
        session,
        type="automation_failing",
        severity="warning",
        title=f"{row.automation_name} keeps failing",
        body=(
            f"{row.failures} of its replies failed in the last hour. {reason.text} "
            "See Activity for each one."
        ),
        link=f"/settings/activity?automation={row.automation_id}",
        dedupe_key=dedupe_key(row.automation_id, now),
    )
    return created > 0
