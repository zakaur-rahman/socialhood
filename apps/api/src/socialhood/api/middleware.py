"""Outermost HTTP middleware: request ids, security headers, access log, last-resort errors.

One pure ASGI middleware so that even an unhandled exception's 500 carries the request id and
the security headers (SEC-11, TR-OPS-01).
"""

from __future__ import annotations

import json
import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from socialhood.errors import problem_body
from socialhood.observability.logging import get_logger
from socialhood.observability.request_id import accept_or_new, current_request_id

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"strict-transport-security", b"max-age=63072000; includeSubDomains"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"content-security-policy", b"frame-ancestors 'none'"),
)

log = get_logger("socialhood.http")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = accept_or_new(incoming)
        token = current_request_id.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {h for h, _ in SECURITY_HEADERS}
                ]
                headers.extend(SECURITY_HEADERS)
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("unhandled_error", path=scope.get("path"), method=scope.get("method"))
            if not response_started:
                await _send_internal_error(send_wrapper, request_id)
        finally:
            route = scope.get("route")
            log.info(
                "http_request",
                method=scope.get("method"),
                route=getattr(route, "path", scope.get("path")),
                status_code=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.unbind_contextvars("request_id")
            current_request_id.reset(token)


async def _send_internal_error(send: Send, request_id: str) -> None:
    body = json.dumps(problem_body("internal", detail=None, request_id=request_id)).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 500,
            "headers": [
                (b"content-type", b"application/problem+json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
