"""An in-memory Google for YouTube, for tests and for running without Google
(``YOUTUBE_PROVIDER=fake``; refused in production).

- ``authorize_url`` points straight back at the redirect address with a fake code, so a browser
  "signs in" without leaving the app; ``exchange_code`` accepts that code.
- ``channels`` lists ``self.channel_list`` (one channel unless a test changes it).
- ``revoke`` (and ``revoke_access``) make minting with that refresh token fail as ``invalid_grant``
  (``account_needs_reconnect``); ``fail_next(error)`` raises ``error`` on the next call,
  ``fail_on(name, error)`` on the next call of that name. Every call is recorded in ``calls``.
- Videos (C-196, platforms/youtube/publishing.Videos): resumable sessions (``sessions``) that count
  the bytes they get, videos (``videos``) with what was last sent for them (``metadata``),
  ``videos.update`` and ``videos.delete`` (``deleted``), the channel's recent uploads and its
  subscribers. ``processing_reads`` sets how many reads a new video stays processing;
  ``lose_next_answer()`` makes the next piece arrive but its answer fail (a cut connection);
  ``expire_sessions()`` makes every open session answer 404; ``fail_processing(id)`` fails a video.
- Comments (YT4, platforms/youtube/comments.Comments): ``comment_threads`` holds them (``items``);
  ``comment_threads.add(video_id, text, ...)`` is a viewer's comment (or reply, with
  ``parent_id``), ``page_size`` sets the threads per page. Moderation keeps a ``status``; deleting
  a viewer's comment is refused as ``forbidden``, like Google. The calls are named
  ``comment_threads``, ``reply_comment``, ``moderate_comment`` and ``delete_comment``.

shortcut: state lives in this process only (unlike google/fake.py's Redis mode): enough for tests,
where the API and the jobs run in one process. The e2e sandbox channel uses
publishing.SandboxVideos (no state), so the worker needs none of it.
"""

from __future__ import annotations

import secrets
from collections import deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from socialhood.platforms.base import CommentPage
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.client import Channel
from socialhood.platforms.youtube.comments import page_from, top_level_id
from socialhood.platforms.youtube.oauth import SCOPES, Grant
from socialhood.platforms.youtube.publishing import (
    CHUNK_BYTES,
    Progress,
    Video,
    stream_from_source,
)
from socialhood.settings import Settings

CODE = "fake-youtube-code"
REFRESH_PREFIX = "fake-yt-refresh:"
ACCESS_PREFIX = "fake-yt-access:"
SESSION_PREFIX = "https://upload.yt.test/session/"
PIECE = 256 * 1024
CHANNEL = Channel(
    id="UCfakeChannel0000000000001",
    title="Maple Bakery",
    handle="maplebakery",
    avatar_url="https://yt.test/maple.jpg",
)


@dataclass
class FakeSession:
    uri: str
    token: str
    metadata: dict[str, Any]
    size: int | None
    content_type: str
    origin: str | None
    received: int = 0
    video_id: str | None = None
    gone: bool = False


def _invalid_grant() -> PlatformError:
    return PlatformError(
        "account_needs_reconnect", platform_code="invalid_grant", message="Token has been revoked"
    )


def _when(meta: dict[str, Any]) -> datetime | None:
    if meta.get("publish_at") and meta.get("privacy") == "private":
        return datetime.fromisoformat(str(meta["publish_at"]))
    return None


class FakeYouTube:
    def __init__(
        self, redirect_uri: str = "http://localhost:8000/v1/oauth/youtube/callback"
    ) -> None:
        self.redirect_uri = redirect_uri
        self.channel_list: list[Channel] = [CHANNEL]
        self.scopes: tuple[str, ...] = SCOPES
        self.revoked: set[str] = set()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._failures: deque[PlatformError] = deque()
        self._named: dict[str, deque[PlatformError]] = {}
        # C-196 videos
        self.chunk_bytes = CHUNK_BYTES
        self.sessions: dict[str, FakeSession] = {}
        self.videos: dict[str, Video] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.deleted: list[str] = []
        self.processing_reads = 0
        self.subscriber_count: int | None = 1200
        self._reads_left: dict[str, int] = {}
        self._lose_answers = 0
        # YT4 comments
        self.comment_threads = FakeComments(self)

    def fail_next(self, error: PlatformError) -> None:
        self._failures.append(error)

    def fail_on(self, name: str, error: PlatformError, times: int = 1) -> None:
        """Raise ``error`` on the next ``times`` calls named ``name`` (open_session, put_chunk,
        progress, get, update, delete, recent_uploads, subscribers...)."""
        self._named.setdefault(name, deque()).extend([error] * times)

    def lose_next_answer(self, times: int = 1) -> None:
        self._lose_answers += times

    def expire_sessions(self) -> None:
        for session in self.sessions.values():
            session.gone = True

    def fail_processing(self, video_id: str, reason: str = "codec") -> None:
        self.videos[video_id] = replace(
            self.videos[video_id], upload_status="failed", failure=reason, processing="failed"
        )

    @property
    def inserts(self) -> int:
        return len(self.sessions)

    def named(self, name: str) -> list[dict[str, Any]]:
        return [args for called, args in self.calls if called == name]

    def revoke_access(self, refresh_token: str) -> None:
        self.revoked.add(refresh_token)

    def _enter(self, name: str, **args: Any) -> None:
        self.calls.append((name, args))
        if self._failures:
            raise self._failures.popleft()
        named = self._named.get(name)
        if named:
            raise named.popleft()

    def authorize_url(self, state: str) -> str:
        return f"{self.redirect_uri}?{urlencode({'code': CODE, 'state': state})}"

    async def exchange_code(self, code: str) -> Grant:
        self._enter("exchange_code", code=code)
        if code != CODE:
            raise _invalid_grant()
        refresh = f"{REFRESH_PREFIX}{secrets.token_hex(4)}"
        return Grant(
            refresh_token=refresh, access_token=ACCESS_PREFIX + refresh, scopes=self.scopes
        )

    async def access_token(self, refresh_token: str) -> str:
        self._enter("access_token")
        if not refresh_token.startswith(REFRESH_PREFIX) or refresh_token in self.revoked:
            raise _invalid_grant()
        return ACCESS_PREFIX + refresh_token

    async def revoke(self, refresh_token: str) -> None:
        self._enter("revoke", token=refresh_token)
        self.revoke_access(refresh_token)

    async def channels(self, access_token: str) -> list[Channel]:
        self._enter("channels")
        if not access_token.startswith(ACCESS_PREFIX):
            raise PlatformError("account_needs_reconnect", platform_code="401")
        return list(self.channel_list)

    # ---------------------------------------------------------------- videos (C-196)

    def _channel_of(self, token: str) -> str:
        refresh = token[len(ACCESS_PREFIX) :]
        if not token.startswith(ACCESS_PREFIX) or refresh in self.revoked:
            raise PlatformError("account_needs_reconnect", platform_code="401")
        return self.channel_list[0].id

    async def open_session(
        self,
        token: str,
        *,
        metadata: dict[str, Any],
        size: int | None,
        content_type: str,
        origin: str | None = None,
    ) -> str:
        self._enter("open_session", metadata=dict(metadata), size=size, origin=origin)
        self._channel_of(token)
        uri = f"{SESSION_PREFIX}{secrets.token_hex(8)}"
        self.sessions[uri] = FakeSession(uri, token, dict(metadata), size, content_type, origin)
        return uri

    def _finish(self, session: FakeSession) -> Video:
        if session.video_id is None:
            video_id = f"vid{secrets.token_hex(4)}"
            meta = session.metadata
            self.videos[video_id] = Video(
                id=video_id,
                channel_id=self._channel_of(session.token),
                title=meta.get("title"),
                description=meta.get("description"),
                category_id=meta.get("category_id") or "22",
                privacy=meta.get("privacy"),
                publish_at=_when(meta),
                upload_status="uploaded",
                processing="processing",
                published_at=datetime.now(UTC),
                views=0,
                likes=0,
                comments=0,
            )
            self.metadata[video_id] = dict(meta)
            self._reads_left[video_id] = self.processing_reads
            session.video_id = video_id
        return self.videos[session.video_id]

    def finish_upload(self, session_uri: str) -> Video:
        """A test's browser: send the whole file at once."""
        session = self.sessions[session_uri]
        session.received = session.size or 1
        session.size = session.received
        return self._finish(session)

    def _session(self, uri: str) -> FakeSession | None:
        session = self.sessions.get(uri)
        return None if session is None or session.gone else session

    async def put_chunk(self, session_uri: str, data: bytes, *, start: int, total: int) -> Progress:
        self._enter("put_chunk", start=start, length=len(data), total=total)
        session = self._session(session_uri)
        if session is None:
            raise PlatformError("platform_rejected", platform_code="404", message="No session")
        if start != session.received:
            raise PlatformError("platform_rejected", platform_code="400", message="Bad range")
        if start + len(data) < total and len(data) % PIECE:
            raise PlatformError("platform_rejected", platform_code="400", message="Not 256 KiB")
        session.received = start + len(data)
        video = self._finish(session) if session.received >= total else None
        if self._lose_answers:
            self._lose_answers -= 1
            raise PlatformError("platform_unavailable", message="The connection was cut")
        return Progress(session.received, video)

    async def progress(self, session_uri: str, *, total: int | None) -> Progress | None:
        self._enter("progress")
        session = self._session(session_uri)
        if session is None:
            return None
        if session.video_id is not None or (total is not None and session.received >= total):
            return Progress(session.received, self._finish(session))
        return Progress(session.received)

    async def transfer(
        self, http: httpx.AsyncClient, session_uri: str, source_url: str, *, offset: int, total: int
    ) -> Video:
        return await stream_from_source(
            self, http, session_uri, source_url, offset=offset, total=total
        )

    async def get(self, token: str, video_id: str) -> Video | None:
        self._enter("get", video_id=video_id)
        channel = self._channel_of(token)
        video = self.videos.get(video_id)
        if video is None or video.channel_id != channel:
            return None
        if video.upload_status == "uploaded":
            left = self._reads_left.get(video_id, 0)
            if left > 0:
                self._reads_left[video_id] = left - 1
            else:
                video = replace(video, upload_status="processed", processing="succeeded")
        if (
            video.privacy == "private"
            and video.publish_at is not None
            and video.publish_at <= datetime.now(UTC)
        ):
            video = replace(video, privacy="public", publish_at=None)  # YouTube's publishAt
        self.videos[video_id] = video
        return video

    async def update(self, token: str, video_id: str, metadata: dict[str, Any]) -> None:
        self._enter("update", video_id=video_id, metadata=dict(metadata))
        channel = self._channel_of(token)
        video = self.videos.get(video_id)
        if video is None or video.channel_id != channel:
            raise PlatformError("platform_rejected", platform_code="videoNotFound")
        self.metadata[video_id] = dict(metadata)
        self.videos[video_id] = replace(
            video,
            title=metadata.get("title"),
            description=metadata.get("description"),
            privacy=metadata.get("privacy"),
            publish_at=_when(metadata),
        )

    async def delete(self, token: str, video_id: str) -> None:
        self._enter("delete", video_id=video_id)
        self._channel_of(token)
        if self.videos.pop(video_id, None) is not None:
            self.deleted.append(video_id)

    async def recent_uploads(self, token: str, channel_id: str, *, limit: int = 10) -> list[Video]:
        self._enter("recent_uploads", channel_id=channel_id)
        mine = [v for v in self.videos.values() if v.channel_id == channel_id]
        mine.sort(key=lambda v: v.published_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return mine[:limit]

    async def subscribers(self, token: str, channel_id: str) -> int | None:
        self._enter("subscribers", channel_id=channel_id)
        return self.subscriber_count


@dataclass
class FakeComment:
    id: str
    video_id: str
    author: str
    name: str
    text: str
    likes: int
    at: datetime
    parent_id: str | None = None
    status: str = "published"  # or rejected (hidden)


class FakeComments:
    """The fake's comments (see the module docstring)."""

    def __init__(self, youtube: FakeYouTube) -> None:
        self.youtube = youtube
        self.items: dict[str, FakeComment] = {}
        self.page_size = 100

    def add(
        self,
        video_id: str,
        text: str,
        *,
        author: str = "UCviewer000000000000001",
        name: str = "Viewer",
        parent_id: str | None = None,
        likes: int = 0,
        at: datetime | None = None,
    ) -> str:
        comment_id = (
            f"{top_level_id(parent_id)}.r{secrets.token_hex(4)}"
            if parent_id
            else f"Ug{secrets.token_hex(6)}"
        )
        self.items[comment_id] = FakeComment(
            comment_id,
            video_id,
            author,
            name,
            text,
            likes,
            at or datetime.now(UTC),
            top_level_id(parent_id) if parent_id else None,
        )
        return comment_id

    def _json(self, c: FakeComment) -> dict[str, Any]:
        snippet: dict[str, Any] = {
            "videoId": c.video_id,
            "authorDisplayName": c.name,
            "authorChannelId": {"value": c.author},
            "textDisplay": c.text,
            "likeCount": c.likes,
            "publishedAt": c.at.isoformat(),
        }
        if c.parent_id:
            snippet["parentId"] = c.parent_id
        return {"id": c.id, "snippet": snippet}

    async def threads(
        self,
        token: str,
        *,
        channel_id: str | None = None,
        video_id: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        self.youtube._enter(
            "comment_threads", channel_id=channel_id, video_id=video_id, cursor=cursor
        )
        channel = self.youtube._channel_of(token)
        shown = [c for c in self.items.values() if c.status == "published"]
        tops = sorted(
            (c for c in shown if c.parent_id is None and video_id in (None, c.video_id)),
            key=lambda c: c.at,
            reverse=True,
        )
        start = int(cursor or 0)
        page = tops[start : start + self.page_size]
        items = [
            {
                "id": top.id,
                "snippet": {
                    "channelId": channel,
                    "videoId": top.video_id,
                    "topLevelComment": self._json(top),
                },
                "replies": {
                    "comments": [self._json(r) for r in shown if r.parent_id == top.id],
                },
            }
            for top in page
        ]
        more = start + self.page_size < len(tops)
        return page_from(
            {"items": items, "nextPageToken": str(start + self.page_size) if more else None}
        )

    async def reply(self, token: str, parent_id: str, text: str) -> str:
        self.youtube._enter("reply_comment", parent_id=parent_id, text=text)
        channel = self.youtube._channel_of(token)
        parent = self.items.get(parent_id)
        if parent is None or parent.parent_id is not None:
            raise PlatformError("platform_rejected", platform_code="invalidParentId")
        return self.add(
            parent.video_id, text, author=channel, name=CHANNEL.title, parent_id=parent_id
        )

    async def moderate(self, token: str, comment_id: str, status: str) -> None:
        self.youtube._enter("moderate_comment", comment_id=comment_id, status=status)
        self.youtube._channel_of(token)
        if comment_id not in self.items:
            raise PlatformError("platform_rejected", platform_code="commentNotFound")
        self.items[comment_id].status = status

    async def delete(self, token: str, comment_id: str) -> None:
        self.youtube._enter("delete_comment", comment_id=comment_id)
        channel = self.youtube._channel_of(token)
        comment = self.items.get(comment_id)
        if comment is None:
            raise PlatformError("platform_rejected", platform_code="commentNotFound")
        if comment.author != channel:
            raise PlatformError("platform_rejected", platform_code="forbidden")
        del self.items[comment_id]


_process: list[FakeYouTube] = []


def process_fake(settings: Settings) -> FakeYouTube:
    if not _process:
        redirect = settings.youtube_redirect_uri
        _process.append(FakeYouTube(redirect) if redirect else FakeYouTube())
    return _process[0]
