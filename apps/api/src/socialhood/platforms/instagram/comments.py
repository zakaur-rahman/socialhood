"""Instagram comment reads for the backfill on connect (T6.1; FR-CMT-01, F-12). The adapter's
``list_comments`` delegates here; payload shapes belong in ``parse.py``.

``GET /{media_id}/comments`` pages through a post's top-level comments; replies come from each
comment's ``replies`` edge and are returned with ``parent_id`` set.
"""

from __future__ import annotations

from collections.abc import Callable

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import CommentPage
from socialhood.platforms.http import PlatformHttp


async def list_comments(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    media_ref: str,
    *,
    cursor: str | None,
) -> CommentPage:
    raise NotImplementedError("T6.1")
