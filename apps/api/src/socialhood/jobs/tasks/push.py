"""Push jobs (T8.6; FR-NOT-03, TR-FE-09, TR-JOB-02…06). Thin tasks: the work is in
notify/push_delivery.py.

- deliver_push(notification_id, workspace_id): interactive lane, queueing lock ``push:{id}``,
  3 tries on retryable PushErrors when no device was reached (10 s, then 20 s). Deferred when a
  notification with the ``push`` channel commits and its member has an enabled device
  (services/notifications.py, notify/dispatch.py). Calls ``notify.push_delivery.deliver`` in the
  workspace's scope with ``notify.registry.get_push_sender``; subscriptions that answer 404 or
  410 are deleted.
- No sweeper: a lost enqueue leaves the notification in-app only. A push is worth sending only
  while it is prompt, and notifications have no index to find unpushed rows cheaply.
"""

from __future__ import annotations

import uuid

from procrastinate import JobContext

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.runtime import runtime
from socialhood.jobs.tasks.emails import DeliveryRetry
from socialhood.notify import push_delivery
from socialhood.notify.push import PushError
from socialhood.notify.registry import get_push_sender

PUSH_RETRY = DeliveryRetry(max_attempts=3)


@app.task(name="deliver_push", queue=INTERACTIVE, retry=PUSH_RETRY, pass_context=True)
async def deliver_push(context: JobContext, notification_id: str, workspace_id: str) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: PushError) -> bool:
        return PUSH_RETRY.get_retry_decision(exception=error, job=job) is not None

    with workspace_scope(uuid.UUID(workspace_id)):
        await push_delivery.deliver(
            rt.sessionmaker,
            uuid.UUID(notification_id),
            sender=get_push_sender(rt.http, rt.settings),
            will_retry=will_retry,
        )
