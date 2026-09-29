"""Comment intelligence (P6; FR-CMT-01…05, TR-AI-11, F-12): the comment backfill on connect, comment
analysis and post summaries, the posts and comments API, and comment actions.

- ``views``: the API projections (schemas/posts.py) and the comment.* and post.updated events.
- ``backfill``: backfill_comments (T6.1).
- ``analysis``: analyze_comments and its dispatch (T6.2).
- ``summaries``: summarize_post (T6.2).
- ``queries``: post detail and a post's comments (T6.3).
- ``actions`` and ``private_replies``: reply, private reply, hide, unhide and delete (T6.3).
"""
