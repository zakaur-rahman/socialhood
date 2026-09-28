"""Instagram reads for inbound media, post sync and conversation backfill (T3.3, T3.14;
TR-MED-02, TR-MED-03, TR-PL-05, FR-CON-01). The adapter's ``download_media``, ``list_media`` and
``list_threads`` delegate here; payload shapes are parsed in ``parse.py``.

Unverified until T0.9 (item 7 and the echo items): the Conversations API fields, how the account
itself appears in ``from`` and ``participants``, and whether CDN media URLs need a token (they
are signed URLs, so none is sent).
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import MediaDownload, PlatformMedia, PlatformThread
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import parse

log = get_logger("socialhood.platforms")

MB = 1024 * 1024
# TR-MED-02 caps (images 8 MB, video 100 MB); audio and files take Instagram's 25 MB DM limit.
MAX_BYTES = {"image": 8 * MB, "sticker": 8 * MB, "video": 100 * MB, "audio": 25 * MB}
DEFAULT_MAX_BYTES = 25 * MB
DOWNLOAD_TIMEOUT = httpx.Timeout(60.0, connect=5.0)  # TR-PL-05: 60 s for media downloads

MEDIA_FIELDS = (
    "id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,"
    "like_count,comments_count"
)
THREAD_LIST_FIELDS = "participants,updated_time"
THREAD_FIELDS = "messages{id,created_time,from,to,message,attachments}"
CONVERSATIONS_PACE_S = 0.5  # TR-PL-09: the Conversations API allows 2 calls a second
GRAPH_ID = re.compile(r"^[A-Za-z0-9_=-]{1,512}$")


def _items(body: Any, key: str | None = None) -> list[dict[str, Any]]:
    container = body.get(key) if key and isinstance(body, dict) else body
    data = container.get("data") if isinstance(container, dict) else None
    return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []


# ---------------------------------------------------------------- media download


def _log(status: int | None, started: float, outcome: str) -> None:
    log.info(
        "platform_call",
        platform="instagram",
        endpoint="media_download",
        status_code=status,
        outcome=outcome,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )


async def download(client: httpx.AsyncClient, ref: InboundMediaRef) -> MediaDownload:
    """Fetch an attachment from Instagram's CDN, refusing anything over its size cap."""
    if not ref.url or not ref.url.startswith("https://"):
        raise PlatformError("platform_rejected", message="The attachment has no media URL")
    limit = MAX_BYTES.get(ref.kind, DEFAULT_MAX_BYTES)
    too_large = PlatformError(
        "unsupported_media", retryable=False, message=f"The attachment is over {limit // MB} MB"
    )
    started = time.perf_counter()
    try:
        async with client.stream(
            "GET", ref.url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True
        ) as response:
            status = response.status_code
            if status >= 400:  # 403 or 404: the signed URL expired, retrying will not help
                _log(status, started, "http_error")
                retryable = status >= 500 or status == 429
                raise PlatformError(
                    "platform_unavailable" if retryable else "platform_rejected",
                    message=f"The platform returned HTTP {status} for the media",
                )
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > limit:
                _log(status, started, "too_large")
                raise too_large
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > limit:
                    _log(status, started, "too_large")
                    raise too_large
                chunks.append(chunk)
            mime = response.headers.get("content-type", "").split(";")[0].strip() or None
    except httpx.TimeoutException as error:
        _log(None, started, "timeout")
        raise PlatformError(
            "platform_unavailable", message="The media download timed out"
        ) from error
    except httpx.HTTPError as error:
        _log(None, started, "network")
        raise PlatformError(
            "platform_unavailable", message="Could not download the media"
        ) from error
    _log(status, started, "ok")
    return MediaDownload(content=b"".join(chunks), mime_type=mime)


# ---------------------------------------------------------------- posts (sync_media)


async def list_media(
    http: PlatformHttp, graph: Callable[[str], str], token: str, *, limit: int
) -> list[PlatformMedia]:
    body = await http.request(
        "GET",
        graph("me/media"),
        endpoint="me.media",
        token=token,
        params={"fields": MEDIA_FIELDS, "limit": limit},
    )
    return [m for m in map(parse.media_item, _items(body)) if m is not None][:limit]


# ---------------------------------------------------------------- conversations (backfill)


async def list_threads(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    limit: int,
) -> list[PlatformThread]:
    """Recent threads with their latest messages (Instagram returns at most 20 per thread).
    A thread Instagram refuses is skipped; a retryable failure fails the whole call."""
    body = await http.request(
        "GET",
        graph("me/conversations"),
        endpoint="me.conversations",
        token=token,
        params={"platform": "instagram", "fields": THREAD_LIST_FIELDS, "limit": limit},
    )
    own_ids = frozenset(i for i in (acct.platform_account_id, acct.app_scoped_id) if i)
    threads: list[PlatformThread] = []
    for conversation in _items(body)[:limit]:
        conversation_id = str(conversation.get("id") or "")
        if not GRAPH_ID.match(conversation_id):
            continue
        await asyncio.sleep(CONVERSATIONS_PACE_S)
        try:
            detail = await http.request(
                "GET",
                graph(conversation_id),
                endpoint="conversation.messages",
                token=token,
                params={"fields": THREAD_FIELDS},
            )
        except PlatformError as error:
            if error.retryable:
                raise
            log.warning("backfill_thread_skipped", error_code=error.code)
            continue
        parsed = parse.thread(
            conversation,
            _items(detail, "messages"),
            account_ref=acct.platform_account_id,
            own_ids=own_ids,
            own_username=acct.username,
        )
        if parsed is not None:
            threads.append(parsed)
    return threads
