"""Billing jobs (T8.3; TR-BIL-03, TR-JOB-02…06). Thin tasks: the work is in billing/.

- reconcile_subscriptions: periodic, every 6 hours (``0 */6 * * *``, bulk lane, queueing lock
  ``reconcile_subscriptions``, timeout 300 s). Lists the subscriptions that aren't Free across
  workspaces (the tenant bypass is allowed in jobs/, TR-TEN-04), then for each calls
  ``billing.reconcile.reconcile_one`` in that workspace's scope with ``billing.registry.get_dodo``:
  drift is corrected and logged, and a subscription past grace_until still on hold goes to Free
  (with the downgrade effects). A Dodo error skips that workspace until the next run.

Dodo webhook events are processed by the shared process_webhook_event job
(services/webhook_handlers/dodo.py), not here.
"""

from __future__ import annotations
