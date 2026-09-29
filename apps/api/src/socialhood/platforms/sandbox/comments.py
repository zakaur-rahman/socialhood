"""The sandbox's existing comments for the backfill on connect (T6.1; TR-PL-07, FR-CMT-01): a few
made-up comments on each of ``history.posts`` (as many as the post's ``comments_count``), with ids
derived from the post so a second backfill stores nothing new. The adapter's ``list_comments``
delegates here.

Tests can give a post any comments with ``seed(media_ref, comments)`` (``outbox.reset()`` forgets
them); pages hold ``PAGE_SIZE`` comments like Instagram's.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import CommentPage, PlatformComment
from socialhood.platforms.sandbox import history

PAGE_SIZE = 50

# (text, commenter username): praise, a price question, spam, a shipping question.
MADE_UP = (
    ("Love this colour! 😍", "happy.customer"),
    ("How much is this one?", "price.asker"),
    ("Get 10k followers FREE, check my profile!!!", "growth.hacks.4u"),
    ("Do you ship to Pune?", "pune.shopper"),
)

SEEDED: dict[str, tuple[PlatformComment, ...]] = {}


def seed(media_ref: str, comments: Sequence[PlatformComment]) -> None:
    """Tests: the post's comments on Instagram, in page order."""
    SEEDED[media_ref] = tuple(comments)


def made_up(acct: SocialAccount, media_ref: str) -> tuple[PlatformComment, ...]:
    """The comments a sandbox post "already has"; none on posts the sandbox did not make."""
    post = next(
        (
            p
            for p in history.posts(acct, limit=len(history.POSTS))
            if p.platform_media_id == media_ref
        ),
        None,
    )
    if post is None:
        return ()
    return tuple(
        PlatformComment(
            account_ref=acct.platform_account_id,
            occurred_at=post.posted_at + timedelta(minutes=30 * (j + 1)),
            platform_comment_id=f"{media_ref}_comment_{j}",
            media_id=media_ref,
            parent_id=None,
            author_ref=f"sandbox_commenter_{j}",
            author_username=MADE_UP[j % len(MADE_UP)][1],
            text=MADE_UP[j % len(MADE_UP)][0],
            like_count=j,
        )
        for j in range(post.comments_count or 0)
    )


def page(acct: SocialAccount, media_ref: str, *, cursor: str | None) -> CommentPage:
    items = SEEDED[media_ref] if media_ref in SEEDED else made_up(acct, media_ref)
    start = int(cursor) if cursor and cursor.isdigit() else 0
    end = start + PAGE_SIZE
    return CommentPage(
        comments=items[start:end], next_cursor=str(end) if end < len(items) else None
    )
