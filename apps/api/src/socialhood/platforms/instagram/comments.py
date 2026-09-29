"""Instagram comment reads for the backfill on connect (T6.1; FR-CMT-01, F-12). The adapter's
``list_comments`` delegates here; payload shapes belong in ``parse.py``.

``GET /{media_id}/comments`` pages through a post's top-level comments, 50 at a time; replies come
from each comment's ``replies`` edge, expanded in the same call (its first 50), and are returned
right after their comment with ``parent_id`` set. The next page is asked for with the ``after``
cursor Instagram returned.

Unverified until a real account confirms them (docs/verification.md): the nested ``replies``
expansion with ``.limit()``, ``from`` on comments read through Instagram Login (the commenter's
IGSID, as in webhooks), and ``hidden`` on the account's own posts.
"""

from __future__ import annotations

from collections.abc import Callable

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import CommentPage
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import parse
from socialhood.platforms.instagram.reads import GRAPH_ID

PAGE_SIZE = 50
REPLIES_PER_COMMENT = 50
COMMENT_FIELDS = "id,text,timestamp,username,from,like_count,hidden,parent_id"
FIELDS = f"{COMMENT_FIELDS},replies.limit({REPLIES_PER_COMMENT}){{{COMMENT_FIELDS}}}"


async def list_comments(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    media_ref: str,
    *,
    cursor: str | None,
) -> CommentPage:
    if not GRAPH_ID.match(media_ref):
        raise PlatformError("platform_rejected", message="Not an Instagram media id")
    params: dict[str, object] = {"fields": FIELDS, "limit": PAGE_SIZE}
    if cursor:
        params["after"] = cursor
    body = await http.request(
        "GET",
        graph(f"{media_ref}/comments"),
        endpoint="media.comments",
        token=token,
        params=params,
    )
    return parse.comment_page(body, account_ref=acct.platform_account_id, media_ref=media_ref)
