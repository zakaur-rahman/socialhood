"""The sandbox's existing comments for the backfill on connect (T6.1; TR-PL-07, FR-CMT-01): a few
made-up comments on each of ``history.posts``, with ids derived from the post so a second backfill
stores nothing new. The adapter's ``list_comments`` delegates here."""

from __future__ import annotations

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import CommentPage


def page(acct: SocialAccount, media_ref: str, *, cursor: str | None) -> CommentPage:
    raise NotImplementedError("T6.1")
