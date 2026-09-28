"""Calls to graph.facebook.com for WhatsApp (TR-PL-02, TR-PL-05).

Every call goes through PlatformHttp (shared client, token in the header, logged by endpoint
name) with WhatsApp's error codes applied on top. Media bytes have their own call: the body is not
JSON and a download may take up to 60 seconds.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from socialhood.observability.logging import get_logger
from socialhood.platforms.base import MediaDownload
from socialhood.platforms.errors import PlatformError, map_graph_error
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.whatsapp.errors import remap
from socialhood.settings import Settings

GRAPH = "https://graph.facebook.com"
MEDIA_TIMEOUT = httpx.Timeout(60.0, connect=5.0)

log = get_logger("socialhood.platforms")


class WhatsAppHttp:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.http = PlatformHttp(client, "whatsapp")
        self.version = settings.meta_graph_version

    def url(self, path: str) -> str:
        return f"{GRAPH}/{self.version}/{path}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        endpoint: str,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        try:
            return await self.http.request(
                method, self.url(path), endpoint=endpoint, token=token, params=params, json=json
            )
        except PlatformError as error:
            mapped = remap(error)
            if mapped is error:
                raise
            raise mapped from error

    async def download(self, url: str, *, token: str) -> MediaDownload:
        """GET a media URL WhatsApp issued (valid for 5 minutes), with the token in the header."""
        started = time.perf_counter()
        try:
            response = await self.client.get(
                url, headers={"Authorization": f"Bearer {token}"}, timeout=MEDIA_TIMEOUT
            )
        except httpx.TimeoutException as error:
            self._log(started, None, "timeout")
            raise PlatformError(
                "platform_unavailable", message="WhatsApp did not send the file in time"
            ) from error
        except httpx.HTTPError as error:
            self._log(started, None, "network")
            raise PlatformError(
                "platform_unavailable", message="Could not reach WhatsApp's media server"
            ) from error
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = None
            mapped = remap(map_graph_error(response.status_code, body, dict(response.headers)))
            self._log(started, response.status_code, mapped.code, mapped.platform_code)
            raise mapped
        self._log(started, response.status_code, "ok")
        return MediaDownload(response.content, response.headers.get("content-type"))

    def _log(
        self,
        started: float,
        status: int | None,
        outcome: str,
        platform_code: str | None = None,
    ) -> None:
        log.info(
            "platform_call",
            platform="whatsapp",
            endpoint="media.download",
            status_code=status,
            outcome=outcome,
            platform_code=platform_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
