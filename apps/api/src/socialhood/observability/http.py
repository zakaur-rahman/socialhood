"""HTTP metrics, unhandled-error capture and the /metrics endpoint (TR-OPS-01, SEC-12, T9.3).

``MetricsMiddleware`` sits just inside ``RequestContextMiddleware``. It labels requests by route
template (``/v1/w/{workspace_id}/…``), never by raw path, and counts webhook POSTs by provider and
outcome. ``RequestContextMiddleware`` turns an unhandled exception into a problem+json 500 and
swallows it, so Sentry's own ASGI hook never sees it: this middleware reports it first.

``GET /metrics`` needs ``Authorization: Bearer {METRICS_TOKEN}`` (compared in constant time). With
no token configured it does not exist (404); a missing or wrong token gets 401.
"""

from __future__ import annotations

import hmac
import time

import sentry_sdk
from fastapi import APIRouter, Request, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from socialhood.errors import ApiError
from socialhood.observability import gauges
from socialhood.observability.metrics import (
    HTTP_DURATION,
    HTTP_REQUESTS,
    WEBHOOK_DELIVERIES,
    flush,
    render_stored,
)
from socialhood.settings import Settings

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
UNMATCHED = "unmatched"
_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})


def route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else UNMATCHED


def webhook_outcome(status: int) -> str:
    if 200 <= status < 300:
        return "accepted"
    if status == 401:
        return "signature_invalid"
    return "error" if status >= 500 else "rejected"


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = int(message["status"])
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as error:
            if not response_started:
                status = 500
            sentry_sdk.capture_exception(error)
            raise
        finally:
            method = scope.get("method", "")
            method = method if method in _METHODS else "OTHER"
            route = route_template(scope)
            HTTP_REQUESTS.inc(method=method, route=route, status=str(status))
            HTTP_DURATION.observe(time.perf_counter() - started, method=method, route=route)
            if method == "POST" and route.startswith("/webhooks/"):
                WEBHOOK_DELIVERIES.inc(
                    provider=route.split("/")[2] or UNMATCHED, outcome=webhook_outcome(status)
                )


router = APIRouter(include_in_schema=False)


def _authorized(settings: Settings, header: str) -> None:
    expected = settings.metrics_token.get_secret_value() if settings.metrics_token else ""
    if not expected:
        raise ApiError("not_found")
    scheme, _, supplied = header.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        expected.encode(), supplied.strip().encode()
    ):
        raise ApiError("unauthorized")


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    settings: Settings = request.app.state.settings
    _authorized(settings, request.headers.get("authorization", ""))
    redis = request.app.state.redis
    await flush(redis)  # this instance's own counts, so the scrape is current
    lines = await render_stored(redis)
    lines.extend(await gauges.collect(request.app.state.engine, redis, settings))
    return Response("\n".join(lines) + "\n", media_type=CONTENT_TYPE)
