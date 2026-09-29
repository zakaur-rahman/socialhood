"""snapshot_post_metrics and snapshot_account_daily (T6.5; FR-ANL-01). Thin tasks: the work
belongs in services.

- snapshot_post_metrics(media_item_id, window): one post_metric_snapshots row per post and window
  (1 h, 6 h, 24 h, 72 h, 7 d, 30 d after publishing; models/analytics.py WINDOW_AGES). 1 h and 6 h
  hold the live counts only; insights start at 24 h, behind IG_REQUEST_INSIGHTS_SCOPE; the 72 h
  run re-reads the 24 h insights and marks both final. Each window is captured once.
- snapshot_account_daily(account_id): one account_daily_metrics row per account per day in the
  workspace time zone (followers, and that day's account insights when granted).
"""

from __future__ import annotations
