"""Sandbox comment moderation (T6.3, T6.2 auto-hide; TR-PL-07): hides, unhides and deletes are
recorded for tests to read (``outbox.MODERATION``), with failures injectable like sends
(``outbox.fail_next(code, kind="moderation")``). The adapter's ``hide_comment``,
``unhide_comment`` and ``delete_comment`` delegate here."""

from __future__ import annotations

from socialhood.models.connections import SocialAccount
from socialhood.platforms.sandbox import outbox


def _fail_if_injected() -> None:
    failure = outbox.failure_for_text(None, "moderation")
    if failure is not None:
        raise failure


def set_hidden(acct: SocialAccount, comment_ref: str, *, hidden: bool) -> None:
    _fail_if_injected()
    outbox.record_moderation(acct.platform_account_id, comment_ref, "hide" if hidden else "unhide")


def delete(acct: SocialAccount, comment_ref: str) -> None:
    _fail_if_injected()
    outbox.record_moderation(acct.platform_account_id, comment_ref, "delete")
