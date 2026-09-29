"""Comment tools (FR-AGT-02, FR-AGT-03, TA.4; agent-architecture.html §5).

R1:
- get_post_comments(post, sentiment, intent, spam, range): read; the comments service (P6) with
  its analyses (TR-AI-11). Unanalysed comments are counted, not guessed (FR-AGT-06).
- search_comments(q, range): read; comment search (trigram / full text).
- prepare_comment_reply(comment_id, text, private): draft; an action card that opens the post
  detail's reply box on that comment (FR-CMT-04), private replies only within 7 days of the
  comment and once per comment.

R2: reply_to_comment (low), reply_to_comments (high, bulk, capped by bulk_max) and hide_comment
(low); capability send_replies (bulk_actions for many), through the comment actions.
"""

from __future__ import annotations
