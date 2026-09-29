"""Push jobs (T8.6; FR-NOT-03, TR-FE-09, TR-JOB-02…06). Thin tasks: the work is in
notify/push_delivery.py.

- deliver_push(notification_id, workspace_id): interactive lane, queueing lock ``push:{id}``,
  timeout 30 s, 3 tries on retryable PushErrors. Enqueued after a notification with the ``push``
  channel commits. Calls ``notify.push_delivery.deliver`` in the workspace's scope with
  ``notify.registry.get_push_sender``; subscriptions that answer 404 or 410 are deleted.
- A lost enqueue is picked up by a sweep of recent push notifications with no ``pushed_at``
  (T8.6 decides whether that is worth it for an alert that is only useful when prompt).
"""

from __future__ import annotations
