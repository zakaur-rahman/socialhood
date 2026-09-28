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
    await _send_problem(send, "internal", request_id)


async def _send_problem(send: Send, code: str, request_id: str | None) -> None:
    payload = problem_body(code, detail=None, request_id=request_id)
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": payload["status"],
            "headers": [
                (b"content-type", b"application/problem+json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


WEBHOOK_BODY_LIMIT = 5 * 1024 * 1024
API_BODY_LIMIT = 1024 * 1024


class _BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """SEC-09: 5 MB for webhook deliveries, 1 MB for everything else. Checks Content-Length up
    front and counts streamed bytes, so a chunked body cannot get past the limit either."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        limit = WEBHOOK_BODY_LIMIT if path.startswith("/webhooks/") else API_BODY_LIMIT

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > limit:
                    await _send_problem(send, "payload_too_large", current_request_id.get())
                    return
                break

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await _send_problem(send, "payload_too_large", current_request_id.get())
