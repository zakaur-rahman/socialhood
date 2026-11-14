"""YouTube uploads and video calls (C-196; YouTube Data API v3, checked 2026-11-14).

- **Resumable uploads.** ``open_session`` POSTs the metadata to
  ``upload/youtube/v3/videos?uploadType=resumable&part=snippet,status`` with
  ``X-Upload-Content-Length`` and ``X-Upload-Content-Type``; the ``Location`` header is the
  session's address. The file then goes in pieces (``put_chunk``): ``Content-Range: bytes
  a-b/total``, each a multiple of 256 KiB but the last (``CHUNK_BYTES``, 8 MiB). 308 means go on
  (``Range: bytes=0-n`` says what arrived), 200 or 201 means done, with the video resource.
  ``progress`` asks what arrived with an empty PUT ``Content-Range: bytes */total``; a session
  that is gone answers 404 or 410 (None here). The session address is a capability for that one
  file: it is never logged, and the API hands it only to the member's own browser or AI app.
- **Browser uploads.** A session opened with an ``Origin`` header (the web app's) answers that
  origin's CORS preflight, so the browser can PUT to it directly (docs/verification.md: not yet
  tried against Google).
- **Quota.** videos.insert has its own bucket (100 a day per Google Cloud project); every other
  call shares 10,000 units: videos.list 1, playlistItems.list 1, channels.list 1, videos.update
  50, videos.delete 50. ``platforms/buckets.youtube_uploads`` counts inserts.
- ``Videos`` is what the services call; ``videos_for`` picks the implementation: Google
  (``HttpVideos``), the sandbox channel's (``SandboxVideos``: no Google, no state; see below) or a
  test's fake (``platforms/youtube/fake.FakeYouTube``).

The sandbox channel (C-196) short-circuits: its upload address is the API's dev route
``/v1/dev/sandbox/youtube-uploads/{token}`` (api/v1/youtube.py), which takes the pieces and
answers like Google; its video ids are ``sandbox_yt_{token}``; reads answer a processed video of
the channel for any such id, so the API process (which takes the upload) and the worker (which
reads it back at the time) need no shared state; the publish job's streaming from storage is
skipped.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.observability.metrics import record_platform_call
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.client import API, google_http, map_google_error
from socialhood.settings import Settings

log = get_logger("socialhood.platforms")

UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK_BYTES = 8 * 1024 * 1024  # a multiple of 256 KiB, as Google asks of every piece but the last
SANDBOX_CHUNK_BYTES = 512 * 1024  # the dev route sits behind the API's 1 MB body limit
SESSION_LIFETIME = timedelta(hours=24)  # ours: an unfinished direct upload ends then
CHUNK_TIMEOUT = httpx.Timeout(300.0, connect=10.0)  # one 8 MiB piece on a slow link
SANDBOX_PREFIX = "sandbox_"  # platforms/sandbox/adapter.SANDBOX_PREFIX (no import: a cycle)
SANDBOX_VIDEO = "sandbox_yt_"
SANDBOX_UPLOADS = "/v1/dev/sandbox/youtube-uploads/"
DEFAULT_CATEGORY = "22"  # People & Blogs: videos.update needs a category with the snippet


@dataclass(frozen=True, kw_only=True)
class Video:
    """What a videos.list read (or a finished upload) says about a video."""

    id: str
    channel_id: str | None = None
    title: str | None = None
    description: str | None = None
    category_id: str | None = None
    privacy: str | None = None  # status.privacyStatus: public, unlisted, private
    publish_at: datetime | None = None  # status.publishAt: YouTube makes it public then
    upload_status: str | None = None  # uploaded, processed, failed, rejected, deleted
    failure: str | None = None  # failureReason or rejectionReason
    processing: str | None = None  # processingDetails.processingStatus
    published_at: datetime | None = None  # snippet.publishedAt (the upload time while private)
    thumbnail_url: str | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None


@dataclass(frozen=True)
class Progress:
    """How much of the file YouTube holds; ``video`` once it holds all of it."""

    received: int
    video: Video | None = None


def _time(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _int(raw: Any) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def video_from(item: dict[str, Any]) -> Video:
    snippet = item.get("snippet") or {}
    status = item.get("status") or {}
    stats = item.get("statistics") or {}
    thumbs = snippet.get("thumbnails") or {}
    thumb = thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}
    return Video(
        id=str(item["id"]),
        channel_id=snippet.get("channelId"),
        title=snippet.get("title"),
        description=snippet.get("description"),
        category_id=snippet.get("categoryId"),
        privacy=status.get("privacyStatus"),
        publish_at=_time(status.get("publishAt")),
        upload_status=status.get("uploadStatus"),
        failure=status.get("failureReason") or status.get("rejectionReason"),
        processing=(item.get("processingDetails") or {}).get("processingStatus"),
        published_at=_time(snippet.get("publishedAt")),
        thumbnail_url=thumb.get("url"),
        views=_int(stats.get("viewCount")),
        likes=_int(stats.get("likeCount")),
        comments=_int(stats.get("commentCount")),
    )


# ---------------------------------------------------------------- the metadata we send


def snippet_body(meta: dict[str, Any], category_id: str | None = None) -> dict[str, Any]:
    """The video's snippet from our metadata (the target's options and the description)."""
    body: dict[str, Any] = {"title": meta["title"], "description": meta.get("description") or ""}
    if meta.get("tags"):
        body["tags"] = list(meta["tags"])
    category = meta.get("category_id") or category_id
    if category:
        body["categoryId"] = category
    return body


def status_body(meta: dict[str, Any]) -> dict[str, Any]:
    """The video's status. ``publishAt`` only on a private video (YouTube's rule): it makes the
    video public at that time."""
    body: dict[str, Any] = {
        "privacyStatus": meta["privacy"],
        "selfDeclaredMadeForKids": bool(meta["made_for_kids"]),
        "containsSyntheticMedia": bool(meta["synthetic_media"]),
    }
    if meta.get("publish_at") and meta["privacy"] == "private":
        body["publishAt"] = meta["publish_at"]
    return body


def match_recent(videos: list[Video], *, title: str, published_after: datetime) -> Video | None:
    """The upload a lost answer made: same title, uploaded since ``published_after`` (the
    newest such)."""
    found = [
        v
        for v in videos
        if v.title == title and v.published_at is not None and v.published_at >= published_after
    ]
    return max(found, key=lambda v: v.published_at or published_after) if found else None


# ---------------------------------------------------------------- the interface


class Videos(Protocol):
    chunk_bytes: int

    async def open_session(
        self,
        token: str,
        *,
        metadata: dict[str, Any],
        size: int | None,
        content_type: str,
        origin: str | None = None,
    ) -> str:
        """A resumable upload's address (``metadata``: snippet and status as we keep them;
        ``size`` None when the file's size isn't known yet)."""
        ...

    async def put_chunk(self, session_uri: str, data: bytes, *, start: int, total: int) -> Progress:
        """Send bytes ``start`` to ``start + len(data) - 1`` of ``total``."""
        ...

    async def progress(self, session_uri: str, *, total: int | None) -> Progress | None:
        """What arrived (``total`` None: not known here); None when the session is gone."""
        ...

    async def transfer(
        self, http: httpx.AsyncClient, session_uri: str, source_url: str, *, offset: int, total: int
    ) -> Video:
        """Send the file at ``source_url`` (from byte ``offset``) to the session."""
        ...

    async def get(self, token: str, video_id: str) -> Video | None:
        """videos.list (snippet, status, processing, statistics): None when there is no such
        video for this token's channel."""
        ...

    async def update(self, token: str, video_id: str, metadata: dict[str, Any]) -> None:
        """videos.update of the snippet and status (50 units)."""
        ...

    async def delete(self, token: str, video_id: str) -> None:
        """videos.delete (50 units); a video already gone is fine."""
        ...

    async def recent_uploads(self, token: str, channel_id: str, *, limit: int = 10) -> list[Video]:
        """The channel's newest uploads, private ones included (2 units)."""
        ...

    async def subscribers(self, token: str, channel_id: str) -> int | None:
        """channels.list statistics.subscriberCount; None when the channel hides it."""
        ...


async def stream_from_source(
    videos: Videos,
    http: httpx.AsyncClient,
    session_uri: str,
    source_url: str,
    *,
    offset: int,
    total: int,
) -> Video:
    """Read the file from storage from ``offset`` (an HTTP Range request) and send it in pieces
    of ``videos.chunk_bytes``, never holding more than a piece and what YouTube didn't take of
    the last one. A piece YouTube took only partly is sent again from where it stopped."""
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    async with http.stream("GET", source_url, headers=headers, timeout=CHUNK_TIMEOUT) as response:
        if response.status_code not in (200, 206):
            raise PlatformError(
                "platform_unavailable", message="Couldn't read the video from storage."
            )
        skip = offset if offset and response.status_code == 200 else 0  # Range was ignored
        position = offset
        buffer = bytearray()
        async for piece in _pieces(response.aiter_bytes(), skip):
            buffer += piece
            while len(buffer) >= videos.chunk_bytes:
                position, buffer = await _send(videos, session_uri, buffer, position, total)
        while buffer or position < total:
            if not buffer:
                raise PlatformError(
                    "platform_unavailable", message="The video in storage ended early."
                )
            done = await videos.put_chunk(session_uri, bytes(buffer), start=position, total=total)
            if done.video is not None:
                return done.video
            taken = done.received - position
            position, buffer = done.received, buffer[taken:]
    progress = await videos.progress(session_uri, total=total)
    if progress is None or progress.video is None:
        raise PlatformError("platform_unavailable", message="YouTube didn't finish the upload.")
    return progress.video


async def _pieces(chunks: AsyncIterator[bytes], skip: int) -> AsyncIterator[bytes]:
    async for piece in chunks:
        if skip >= len(piece):
            skip -= len(piece)
            continue
        yield piece[skip:]
        skip = 0


async def _send(
    videos: Videos, session_uri: str, buffer: bytearray, position: int, total: int
) -> tuple[int, bytearray]:
    piece = bytes(buffer[: videos.chunk_bytes])
    progress = await videos.put_chunk(session_uri, piece, start=position, total=total)
    if progress.video is not None:  # the file was an exact number of pieces: read it after
        return total, bytearray()
    taken = max(0, progress.received - position)
    return progress.received, buffer[taken:]


# ---------------------------------------------------------------- Google


class HttpVideos:
    chunk_bytes = CHUNK_BYTES

    def __init__(self, deps: PlatformDeps) -> None:
        self.client = deps.http
        self.http = google_http(deps.http)

    async def _raw(
        self,
        method: str,
        url: str,
        *,
        endpoint: str,
        ok: tuple[int, ...] = (200, 201),
        gone: tuple[int, ...] = (),
        **kwargs: Any,
    ) -> httpx.Response | None:
        """One call whose headers matter (Location, Range). Failures are mapped like every
        Google call; ``gone`` statuses return None."""
        started = time.perf_counter()
        try:
            response = await self.client.request(method, url, **kwargs)
        except httpx.TimeoutException as error:
            self._log(endpoint, None, started, "timeout")
            raise PlatformError(
                "platform_unavailable", message="YouTube did not respond"
            ) from error
        except httpx.HTTPError as error:
            self._log(endpoint, None, started, "network")
            raise PlatformError(
                "platform_unavailable", message="Could not reach YouTube"
            ) from error
        if response.status_code in gone:
            self._log(endpoint, response.status_code, started, "gone")
            return None
        if response.status_code not in ok:
            try:
                body = response.json()
            except ValueError:
                body = None
            mapped = map_google_error(response.status_code, body, dict(response.headers))
            if response.status_code < 400:  # pragma: no cover - an unexpected redirect
                mapped = PlatformError("platform_unavailable", message="YouTube answered oddly")
            self._log(endpoint, response.status_code, started, mapped.code, mapped.platform_code)
            raise mapped
        self._log(endpoint, response.status_code, started, "ok")
        return response

    def _log(
        self,
        endpoint: str,
        status: int | None,
        started: float,
        outcome: str,
        platform_code: str | None = None,
    ) -> None:
        record_platform_call("youtube", endpoint, outcome)
        log.info(
            "platform_call",
            platform="youtube",
            endpoint=endpoint,
            status_code=status,
            outcome=outcome,
            platform_code=platform_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    async def open_session(
        self,
        token: str,
        *,
        metadata: dict[str, Any],
        size: int | None,
        content_type: str,
        origin: str | None = None,
    ) -> str:
        headers = {"Authorization": f"Bearer {token}", "X-Upload-Content-Type": content_type}
        if size is not None:
            headers["X-Upload-Content-Length"] = str(size)
        if origin:
            headers["Origin"] = origin
        response = await self._raw(
            "POST",
            UPLOAD_API,
            endpoint="videos.insert",
            params={
                "uploadType": "resumable",
                "part": "snippet,status",
                "notifySubscribers": (
                    "true" if metadata.get("notify_subscribers", True) else "false"
                ),
            },
            json={"snippet": snippet_body(metadata), "status": status_body(metadata)},
            headers=headers,
        )
        location = response.headers.get("location") if response is not None else None
        if not location:
            raise PlatformError("platform_unavailable", message="YouTube didn't open the upload.")
        return str(location)

    @staticmethod
    def _progress(response: httpx.Response, total: int | None) -> Progress:
        if response.status_code in (200, 201):
            return Progress(total or 0, video_from(response.json()))
        received = 0
        raw = response.headers.get("range")  # "bytes=0-524287"
        if raw and "-" in raw:
            try:
                received = int(raw.rsplit("-", 1)[1]) + 1
            except ValueError:
                received = 0
        return Progress(received)

    async def put_chunk(self, session_uri: str, data: bytes, *, start: int, total: int) -> Progress:
        response = await self._raw(
            "PUT",
            session_uri,
            endpoint="videos.upload",
            ok=(200, 201, 308),
            content=data,
            headers={"Content-Range": f"bytes {start}-{start + len(data) - 1}/{total}"},
            timeout=CHUNK_TIMEOUT,
        )
        assert response is not None
        return self._progress(response, total)

    async def progress(self, session_uri: str, *, total: int | None) -> Progress | None:
        response = await self._raw(
            "PUT",
            session_uri,
            endpoint="videos.upload_status",
            ok=(200, 201, 308),
            gone=(404, 410),
            content=b"",
            headers={"Content-Range": f"bytes */{total if total is not None else '*'}"},
        )
        return self._progress(response, total) if response is not None else None

    async def transfer(
        self, http: httpx.AsyncClient, session_uri: str, source_url: str, *, offset: int, total: int
    ) -> Video:
        return await stream_from_source(
            self, http, session_uri, source_url, offset=offset, total=total
        )

    async def get(self, token: str, video_id: str) -> Video | None:
        body = await self.http.request(
            "GET",
            f"{API}/videos",
            endpoint="videos.list",
            token=token,
            params={"part": "snippet,status,processingDetails,statistics", "id": video_id},
        )
        items = (body or {}).get("items") or []
        return video_from(items[0]) if items else None

    async def update(self, token: str, video_id: str, metadata: dict[str, Any]) -> None:
        current = await self.get(token, video_id)  # its category, which the snippet must carry
        if current is None:
            raise PlatformError("platform_rejected", message="The video is no longer on YouTube.")
        await self.http.request(
            "PUT",
            f"{API}/videos",
            endpoint="videos.update",
            token=token,
            params={"part": "snippet,status"},
            json={
                "id": video_id,
                "snippet": snippet_body(metadata, current.category_id or DEFAULT_CATEGORY),
                "status": status_body(metadata),
            },
        )

    async def delete(self, token: str, video_id: str) -> None:
        response = await self._raw(
            "DELETE",
            f"{API}/videos",
            endpoint="videos.delete",
            ok=(200, 204),
            gone=(404,),
            params={"id": video_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        del response

    async def recent_uploads(self, token: str, channel_id: str, *, limit: int = 10) -> list[Video]:
        uploads = "UU" + channel_id[2:]  # a channel's uploads playlist
        body = await self.http.request(
            "GET",
            f"{API}/playlistItems",
            endpoint="playlistItems.list",
            token=token,
            params={"part": "contentDetails", "playlistId": uploads, "maxResults": limit},
        )
        ids = [
            str((item.get("contentDetails") or {}).get("videoId"))
            for item in (body or {}).get("items") or []
            if (item.get("contentDetails") or {}).get("videoId")
        ]
        if not ids:
            return []
        listed = await self.http.request(
            "GET",
            f"{API}/videos",
            endpoint="videos.list",
            token=token,
            params={"part": "snippet,status", "id": ",".join(ids)},
        )
        return [video_from(item) for item in (listed or {}).get("items") or []]

    async def subscribers(self, token: str, channel_id: str) -> int | None:
        body = await self.http.request(
            "GET",
            f"{API}/channels",
            endpoint="channels.list",
            token=token,
            params={"part": "statistics", "id": channel_id},
        )
        items = (body or {}).get("items") or []
        if not items:
            return None
        stats = items[0].get("statistics") or {}
        return None if stats.get("hiddenSubscriberCount") else _int(stats.get("subscriberCount"))


# ---------------------------------------------------------------- the sandbox channel


def sandbox_upload_url(settings: Settings, token: str) -> str:
    base = (settings.api_base_url or "http://localhost:8000").rstrip("/")
    return f"{base}{SANDBOX_UPLOADS}{token}"


@dataclass
class SandboxVideos:
    """The sandbox channel's YouTube (see the module docstring): no Google and no state."""

    settings: Settings
    channel_id: str
    chunk_bytes: int = SANDBOX_CHUNK_BYTES
    sessions: dict[str, int] = field(default_factory=dict)

    async def open_session(
        self,
        token: str,
        *,
        metadata: dict[str, Any],
        size: int | None,
        content_type: str,
        origin: str | None = None,
    ) -> str:
        return sandbox_upload_url(self.settings, secrets.token_hex(12))

    @staticmethod
    def _token(session_uri: str) -> str:
        return session_uri.rsplit("/", 1)[-1]

    def _video(self, video_id: str) -> Video:
        return Video(
            id=video_id,
            channel_id=self.channel_id,
            privacy="public",
            upload_status="processed",
            processing="succeeded",
            published_at=datetime.now(UTC),
            views=0,
            likes=0,
            comments=0,
        )

    async def put_chunk(self, session_uri: str, data: bytes, *, start: int, total: int) -> Progress:
        end = start + len(data)
        if end >= total:
            return Progress(total, self._video(SANDBOX_VIDEO + self._token(session_uri)))
        return Progress(end)

    async def progress(self, session_uri: str, *, total: int | None) -> Progress | None:
        return Progress(0)

    async def transfer(
        self, http: httpx.AsyncClient, session_uri: str, source_url: str, *, offset: int, total: int
    ) -> Video:
        return self._video(SANDBOX_VIDEO + self._token(session_uri))  # nothing is read or sent

    async def get(self, token: str, video_id: str) -> Video | None:
        return self._video(video_id) if video_id.startswith(SANDBOX_VIDEO) else None

    async def update(self, token: str, video_id: str, metadata: dict[str, Any]) -> None:
        return None

    async def delete(self, token: str, video_id: str) -> None:
        return None

    async def recent_uploads(self, token: str, channel_id: str, *, limit: int = 10) -> list[Video]:
        return []

    async def subscribers(self, token: str, channel_id: str) -> int | None:
        return 0


def is_sandbox_channel(acct: SocialAccount) -> bool:
    return acct.platform_account_id.startswith(SANDBOX_PREFIX)


def videos_for(acct: SocialAccount, deps: PlatformDeps) -> Videos:
    """The sandbox channel's, a test's fake (``use_youtube`` with a FakeYouTube), the fake with
    ``YOUTUBE_PROVIDER=fake``, else Google's."""
    if is_sandbox_channel(acct):
        return SandboxVideos(deps.settings, acct.platform_account_id)
    from socialhood.platforms.youtube.oauth import youtube_for

    client = youtube_for(deps)
    if hasattr(client, "open_session"):  # the fake serves both
        return client  # type: ignore[return-value]
    return HttpVideos(deps)


def web_origin(settings: Settings) -> str | None:
    """The web app's origin, sent when a session is opened for a browser (CORS)."""
    base = (settings.web_base_url or "").rstrip("/")
    if not base:
        return None
    scheme, _, rest = base.partition("://")
    return f"{scheme}://{rest.split('/', 1)[0]}" if rest else None
