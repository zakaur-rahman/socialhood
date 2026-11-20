"""YouTube comments (YT4; YouTube Data API v3).

- **Read.** ``commentThreads.list`` (1 unit a page) with ``part=snippet,replies``, ``order=time``,
  ``textFormat=plainText``, ``maxResults=100``, and either ``allThreadsRelatedToChannelId`` (every
  thread on the channel's videos: the poll) or ``videoId`` (one video: the per-post backfill). A
  thread is its top-level comment and the replies YouTube includes with it (a few at most); a reply
  carries its top-level comment as its parent. Threads without a ``videoId`` (the channel's own
  discussion) are skipped.
- **Reply.** ``comments.insert`` (50 units) with ``snippet.parentId``: a top-level comment's id.
  A reply's id is ``<top-level id>.<suffix>``, so replying to a reply answers its thread.
- **Moderate.** ``comments.setModerationStatus`` (50 units): ``rejected`` hides a comment,
  ``published`` brings it back (YouTube does not always allow that).
- **Delete.** ``comments.delete`` (50 units) works for the channel's own comments only; the adapter
  falls back to rejecting a viewer's comment.

``comments_for`` picks the implementation: Google (``HttpComments``), the sandbox channel's
(``SandboxComments``, see its docstring) or a test's fake (platforms/youtube/fake.FakeYouTube).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, Protocol

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import CommentPage, PlatformComment
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.youtube.client import API, google_http
from socialhood.platforms.youtube.publishing import SANDBOX_VIDEO, is_sandbox_channel

PAGE_SIZE = 100


def top_level_id(comment_id: str) -> str:
    """The thread's top-level comment: a reply's id is ``<top-level id>.<suffix>``."""
    return comment_id.split(".", 1)[0]


def _time(raw: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _comment(
    item: dict[str, Any], *, video_id: str, channel_id: str, parent_id: str | None
) -> PlatformComment | None:
    snippet = item.get("snippet") or {}
    author = (snippet.get("authorChannelId") or {}).get("value")
    if not author or not item.get("id"):
        return None  # no commenter to keep it under
    return PlatformComment(
        account_ref=channel_id,
        occurred_at=_time(snippet.get("publishedAt")),
        platform_comment_id=str(item["id"]),
        media_id=video_id,
        parent_id=parent_id,
        author_ref=str(author),
        author_username=snippet.get("authorDisplayName"),
        text=str(snippet.get("textOriginal") or snippet.get("textDisplay") or ""),
        like_count=int(snippet.get("likeCount") or 0),
    )


def thread_comments(thread: dict[str, Any]) -> list[PlatformComment]:
    """A commentThreads item as comments: the top-level one, then its included replies."""
    snippet = thread.get("snippet") or {}
    video_id = snippet.get("videoId")
    top = snippet.get("topLevelComment") or {}
    if not video_id or not top:
        return []
    channel = str(snippet.get("channelId") or "")
    first = _comment(top, video_id=video_id, channel_id=channel, parent_id=None)
    if first is None:
        return []
    replies = [
        _comment(r, video_id=video_id, channel_id=channel, parent_id=first.platform_comment_id)
        for r in (thread.get("replies") or {}).get("comments") or []
    ]
    return [first, *(r for r in replies if r is not None)]


def page_from(body: Any) -> CommentPage:
    body = body if isinstance(body, dict) else {}
    found = [c for thread in body.get("items") or [] for c in thread_comments(thread)]
    return CommentPage(tuple(found), body.get("nextPageToken") or None)


class Comments(Protocol):
    async def threads(
        self,
        token: str,
        *,
        channel_id: str | None = None,
        video_id: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        """One page of threads, newest first: the channel's (``channel_id``) or one video's."""
        ...

    async def reply(self, token: str, parent_id: str, text: str) -> str:
        """Post a reply under the top-level comment ``parent_id``; returns the reply's id."""
        ...

    async def moderate(self, token: str, comment_id: str, status: str) -> None:
        """``rejected`` (hide) or ``published`` (show again)."""
        ...

    async def delete(self, token: str, comment_id: str) -> None: ...


class HttpComments:
    def __init__(self, deps: PlatformDeps) -> None:
        self.http = google_http(deps.http)

    async def threads(
        self,
        token: str,
        *,
        channel_id: str | None = None,
        video_id: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        params: dict[str, Any] = {
            "part": "snippet,replies",
            "maxResults": PAGE_SIZE,
            "order": "time",
            "textFormat": "plainText",
        }
        if video_id:
            params["videoId"] = video_id
        else:
            params["allThreadsRelatedToChannelId"] = channel_id
        if cursor:
            params["pageToken"] = cursor
        body = await self.http.request(
            "GET",
            f"{API}/commentThreads",
            endpoint="commentThreads.list",
            token=token,
            params=params,
        )
        return page_from(body)

    async def reply(self, token: str, parent_id: str, text: str) -> str:
        body = await self.http.request(
            "POST",
            f"{API}/comments",
            endpoint="comments.insert",
            token=token,
            params={"part": "snippet"},
            json={"snippet": {"parentId": parent_id, "textOriginal": text}},
        )
        return str((body or {}).get("id") or "")

    async def moderate(self, token: str, comment_id: str, status: str) -> None:
        await self.http.request(
            "POST",
            f"{API}/comments/setModerationStatus",
            endpoint="comments.setModerationStatus",
            token=token,
            params={"id": comment_id, "moderationStatus": status},
        )

    async def delete(self, token: str, comment_id: str) -> None:
        await self.http.request(
            "DELETE",
            f"{API}/comments",
            endpoint="comments.delete",
            token=token,
            params={"id": comment_id},
        )


# ---------------------------------------------------------------- the sandbox channel

SANDBOX_COMMENT = "sandbox_ytc_"
SANDBOX_VIEWER = "UCsandboxViewer000000001"
SANDBOX_VIEWER_NAME = "Sandbox Viewer"
SANDBOX_TEXT = "Love this! Where can I buy the starter you used?"
SANDBOX_LIKES = 12


class SandboxComments:
    """The sandbox channel's comments: no Google and no state. Every sandbox video
    (``sandbox_yt_{token}``) has one viewer comment, ``sandbox_ytc_{video id}`` by "Sandbox Viewer"
    (channel ``UCsandboxViewer000000001``), "Love this! Where can I buy the starter you used?",
    with 12 likes (so it is important before any analysis). It is read per video (``video_id``):
    the channel poll passes the channel's stored videos one at a time. Replies answer
    ``{parent}.sandbox{hex}``; hiding, showing and deleting succeed and change nothing."""

    async def threads(
        self,
        token: str,
        *,
        channel_id: str | None = None,
        video_id: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        if not video_id or not video_id.startswith(SANDBOX_VIDEO):
            return CommentPage(())
        seeded = PlatformComment(
            account_ref=channel_id or "",
            occurred_at=datetime.now(UTC),
            platform_comment_id=SANDBOX_COMMENT + video_id,
            media_id=video_id,
            parent_id=None,
            author_ref=SANDBOX_VIEWER,
            author_username=SANDBOX_VIEWER_NAME,
            text=SANDBOX_TEXT,
            like_count=SANDBOX_LIKES,
        )
        return CommentPage((seeded,))

    async def reply(self, token: str, parent_id: str, text: str) -> str:
        return f"{parent_id}.sandbox{secrets.token_hex(4)}"

    async def moderate(self, token: str, comment_id: str, status: str) -> None:
        return None

    async def delete(self, token: str, comment_id: str) -> None:
        return None


def comments_for(acct: SocialAccount, deps: PlatformDeps) -> Comments:
    """The sandbox channel's, a test's fake (``use_youtube``, or ``YOUTUBE_PROVIDER=fake``), else
    Google's."""
    if is_sandbox_channel(acct):
        return SandboxComments()
    from socialhood.platforms.youtube.oauth import youtube_for

    client = youtube_for(deps)
    if hasattr(client, "comment_threads"):  # the fake serves comments too
        return client.comment_threads  # type: ignore[no-any-return]
    return HttpComments(deps)
