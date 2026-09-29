"""Post tools (FR-AGT-02, TA.4; agent-architecture.html §5).

R1:
- get_posts(range, format, account): read; media items with comment stats, newest first, capped.
- get_latest_post(account): read; the account's most recent post with its age and format.
- search_posts(q): read; posts by caption.

Metrics and comparisons are the analytics tools (tools/analytics.py). No writes.
"""

from __future__ import annotations
