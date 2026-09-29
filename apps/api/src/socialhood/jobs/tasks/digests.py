"""Weekly digest job (T8.7; FR-NOT-04, TR-JOB-02…06). Thin task: the work is in notify/digest.py.

- send_weekly_digests: periodic, hourly at minute 0 (``0 * * * *``, bulk lane, queueing lock
  ``send_weekly_digests``, timeout 300 s). Lists active workspaces with their time zones across
  workspaces (the tenant bypass is allowed in jobs/, TR-TEN-04); for each where
  ``notify.digest.due_week_start`` says it is Monday 09:00-09:59 locally, calls
  ``notify.digest.send_digest`` in that workspace's scope. weekly_digests' unique (workspace,
  week_start) makes a second run in the same hour, or a retry, send nothing twice; the emails go
  out through deliver_email.
"""

from __future__ import annotations
