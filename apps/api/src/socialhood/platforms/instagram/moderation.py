"""Instagram comment moderation (T6.3 actions, T6.2 auto-hide; FR-CMT-04, FR-CMT-05). The adapter's
``hide_comment``, ``unhide_comment`` and ``delete_comment`` delegate here.

``POST /{comment_id}?hide=true|false`` hides or shows a comment; ``DELETE /{comment_id}`` deletes
it. Both are writes: map failures with ``platforms.outcome.for_write``.
"""

from __future__ import annotations

from collections.abc import Callable

from socialhood.platforms.http import PlatformHttp


async def set_hidden(
    http: PlatformHttp, graph: Callable[[str], str], token: str, comment_ref: str, *, hidden: bool
) -> None:
    raise NotImplementedError("T6.3")


async def delete(
    http: PlatformHttp, graph: Callable[[str], str], token: str, comment_ref: str
) -> None:
    raise NotImplementedError("T6.3")
