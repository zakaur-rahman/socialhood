"""Email jobs (T8.5, T8.7; FR-NOT-02, FR-NOT-04, TR-JOB-02…06). Thin tasks: the work is in
notify/outbox.py.

- deliver_email(delivery_id, workspace_id): interactive lane, queueing lock ``email:{id}``,
  timeout 30 s, 5 tries with backoff on retryable EmailErrors (timeouts, 429, 5xx). Enqueued
  after the email_deliveries row commits. Calls ``notify.outbox.send_queued`` in the workspace's
  scope with ``notify.registry.get_email_sender``. The spec's catalogue keys it by notification
  id; it takes the outbox row instead, because digest emails have no notification.
- sweep_email_outbox: periodic, every minute (interactive lane, singleton): re-enqueues
  deliveries still ``queued`` a minute after they were created (a lost enqueue).
"""

from __future__ import annotations
