"""The one way adapters call a platform (TR-PL-05): shared client, token in the header, every call
logged by endpoint name (never the full URL or the token), failures mapped (TR-PL-03)."""

from __future__ import annotations

import time
from typing import Any

import httpx

from socialhood.observability.logging import get_logger
from socialhood.platforms.errors import PlatformError, map_graph_error

log = get_logger("socialhood.platforms")


class PlatformHttp:
    def __init__(self, client: httpx.AsyncClient, platform: str) -> None:
        self.client = client
        self.platform = platform

    async def request(
        self,
        method: str,
        url: str,
        *,
        endpoint: str,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        started = time.perf_counter()
        try:
            response = await self.client.request(
                method,
                url,
                params=params,
                data=data,
                json=json,
                headers=headers,
            )
        except httpx.TimeoutException as error:
            self._log(endpoint, None, started, "timeout")
            raise PlatformError(
                "platform_unavailable", message="The platform did not respond"
            ) from error
        except httpx.HTTPError as error:
            self._log(endpoint, None, started, "network")
            raise PlatformError(
                "platform_unavailable", message="Could not reach the platform"
            ) from error

        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400:
            mapped = map_graph_error(response.status_code, body, dict(response.headers))
            self._log(endpoint, response.status_code, started, mapped.code, mapped.platform_code)
            raise mapped
        self._log(endpoint, response.status_code, started, "ok")
        return body

    def _log(
        self,
        endpoint: str,
        status: int | None,
        started: float,
        outcome: str,
        platform_code: str | None = None,
    ) -> None:
        log.info(
            "platform_call",
            platform=self.platform,
            endpoint=endpoint,
            status_code=status,
            outcome=outcome,
            platform_code=platform_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
