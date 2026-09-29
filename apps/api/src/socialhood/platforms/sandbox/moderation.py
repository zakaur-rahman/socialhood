"""Sandbox comment moderation (T6.3, T6.2 auto-hide; TR-PL-07): hides, unhides and deletes are
recorded for tests to read, with failures injectable like sends (see ``outbox``). The adapter's
``hide_comment``, ``unhide_comment`` and ``delete_comment`` delegate here."""

from __future__ import annotations

from socialhood.models.connections import SocialAccount


def set_hidden(acct: SocialAccount, comment_ref: str, *, hidden: bool) -> None:
    raise NotImplementedError("T6.3")


def delete(acct: SocialAccount, comment_ref: str) -> None:
    raise NotImplementedError("T6.3")
