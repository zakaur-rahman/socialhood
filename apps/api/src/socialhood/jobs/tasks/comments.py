"""backfill_comments (T6.1; FR-CMT-01), analyze_comments and summarize_post (T6.2; TR-AI-11,
FR-CMT-02, FR-CMT-05). Thin tasks: the work belongs in services.

- backfill_comments(account_id): after connect, the 25 most recent posts and up to 200 comments
  each, through the adapter's ``list_comments`` and the same intake as comment webhooks (F-12).
- analyze_comments(account_id): up to 50 pending comments of one account, oldest first, in one
  model call; stores comment_analyses, updates media_items.comment_stats, hides spam when the
  account's auto-hide is on, publishes comment.updated and post.updated. Bulk lane, in a
  per-workspace bulk slot (TR-JOB-06).
- summarize_post(media_item_id): after 20 newly analysed comments or 24 h, the post's summary and
  at most 6 topic labels. Bulk lane.
"""

from __future__ import annotations
