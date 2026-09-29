"""Metric snapshots and post analytics (T6.5; FR-ANL-01, FR-ANL-02, TR-AGT-05, TR-REPO-02).

Collection (the snapshot jobs call these; they never call AI):
- ``snapshots``: post metric snapshots at 1 h, 6 h, 24 h, 72 h, 7 d and 30 d after publishing.
- ``account_daily``: one row of account metrics per account per day.

Reads (the analytics routes and Ask Social Hood's analytics tools call the same functions,
agent-architecture §6):
- ``queries``: ``post_performance``, ``compare_post``, ``top_posts``.
- ``sentiment``: ``sentiment_distribution``.

Shared: ``ages`` (windows, the age a figure is at, formats), ``stats`` (engagement rate, the
comparison numbers), ``common`` (the view, date ranges, loading a post or account).
"""
