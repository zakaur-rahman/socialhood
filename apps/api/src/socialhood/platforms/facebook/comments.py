"""Facebook comment reads for the backfill on connect (GR-29; FR-CMT-01, F-12). The adapter's
``list_comments`` delegates here.

``GET /{post_id}/comments`` pages through a post's top-level comments; replies come from each
comment's ``comments`` edge, expanded in the same call (its first 50), and are returned right
after their comment with ``parent_id`` set. The next page is asked for with the ``after`` cursor.

Unverified until a real Page confirms them (docs/verification.md): the nested ``comments``
expansion with ``.limit()``, ``from`` on comments (a person who limits who sees their profile
may come without it, and is left out), and ``is_hidden``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import CommentPage, PlatformComment
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import parse as instagram
from socialhood.platforms.instagram.reads import GRAPH_ID

PAGE_SIZE = 50
REPLIES_PER_COMMENT = 50
COMMENT_FIELDS = "id,message,created_time,from{id,name},like_count,is_hidden"
FIELDS = f"{COMMENT_FIELDS},comments.limit({REPLIES_PER_COMMENT}){{{COMMENT_FIELDS}}}"


def _comment(
    raw: Mapping[str, Any], *, account_ref: str, media_ref: str, parent_id: str | None
) -> PlatformComment | None:
    comment_id = instagram._str(raw.get("id"))
    at = instagram.graph_time(raw.get("created_time"))
    author = instagram._dict(raw.get("from"))
    author_ref = instagram._id(author)
    if not comment_id or at is None or not author_ref:
        return None
    return PlatformComment(
        account_ref=account_ref,
        occurred_at=at,
        platform_comment_id=comment_id,
        media_id=media_ref,
        parent_id=parent_id,
        author_ref=author_ref,
        author_username=instagram._str(author.get("name")),
        text=str(raw.get("message") or ""),
        like_count=instagram._count(raw.get("like_count")) or 0,
        hidden=raw.get("is_hidden") is True,
    )


def comment_page(body: object, *, account_ref: str, media_ref: str) -> CommentPage:
    """One page of ``GET /{post_id}/comments``: each top-level comment followed by its replies."""
    comments: list[PlatformComment] = []
    for raw in instagram._data(body):
        top = _comment(raw, account_ref=account_ref, media_ref=media_ref, parent_id=None)
        if top is None:
            continue
        comments.append(top)
        for reply in instagram._data(raw.get("comments")):
            parsed = _comment(
                reply,
                account_ref=account_ref,
                media_ref=media_ref,
                parent_id=top.platform_comment_id,
            )
            if parsed is not None:
                comments.append(parsed)
    paging = instagram._dict(instagram._dict(body).get("paging"))
    cursors = instagram._dict(paging.get("cursors"))
    after = instagram._str(cursors.get("after")) if paging.get("next") else None
    return CommentPage(comments=tuple(comments), next_cursor=after)


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
        raise PlatformError("platform_rejected", message="Not a Facebook post id")
    params: dict[str, object] = {"fields": FIELDS, "limit": PAGE_SIZE, "filter": "toplevel"}
    if cursor:
        params["after"] = cursor
    body = await http.request(
        "GET",
        graph(f"{media_ref}/comments"),
        endpoint="post.comments",
        token=token,
        params=params,
    )
    return comment_page(body, account_ref=acct.platform_account_id, media_ref=media_ref)
