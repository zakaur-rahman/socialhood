"""Instagram comment moderation (T6.3 actions, T6.2 auto-hide; FR-CMT-04, FR-CMT-05). The adapter's
``hide_comment``, ``unhide_comment`` and ``delete_comment`` delegate here.

``POST /{comment_id}?hide=true|false`` hides or shows a comment; ``DELETE /{comment_id}`` deletes
it. Both answer ``{"success": true}``. Both are writes: failures are mapped with
``platforms.outcome.for_write``, so a timeout after the request left is ``delivery_unknown``.

A delete of a comment that no longer exists counts as done. Meta answers that with error 100,
subcode 33 ("does not exist, cannot be loaded due to missing permissions, or does not support this
operation"); unverified on a real account (docs/verification.md).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram.reads import GRAPH_ID
from socialhood.platforms.outcome import for_write

ALREADY_GONE = frozenset({"100/33"})


def _comment_id(comment_ref: str) -> str:
    """A platform id placed in a Graph path; anything else could change the path."""
    if not GRAPH_ID.match(comment_ref):
        raise PlatformError("platform_rejected", message="Not an Instagram comment id")
    return comment_ref


def _confirmed(body: Any) -> None:
    if not (isinstance(body, dict) and body.get("success")):
        raise PlatformError("platform_rejected", message="Instagram did not confirm the change")


async def set_hidden(
    http: PlatformHttp, graph: Callable[[str], str], token: str, comment_ref: str, *, hidden: bool
) -> None:
    try:
        body = await http.request(
            "POST",
            graph(_comment_id(comment_ref)),
            endpoint="comment.hide" if hidden else "comment.unhide",
            token=token,
            params={"hide": "true" if hidden else "false"},
        )
    except PlatformError as error:
        raise for_write(error) from error.__cause__
    _confirmed(body)


async def delete(
    http: PlatformHttp, graph: Callable[[str], str], token: str, comment_ref: str
) -> None:
    try:
        body = await http.request(
            "DELETE", graph(_comment_id(comment_ref)), endpoint="comment.delete", token=token
        )
    except PlatformError as error:
        if error.platform_code in ALREADY_GONE:
            return
        raise for_write(error) from error.__cause__
    _confirmed(body)
