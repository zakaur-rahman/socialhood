"""Error codes and the exception every layer raises for an API error (TR-API-03)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ERROR_TYPE_BASE = "https://api.socialhood.com/errors/"


@dataclass(frozen=True)
class ErrorCode:
    status: int
    title: str


# TR-API-03 codes, plus the four generic HTTP ones recorded in docs/QUESTIONS.md (Q-001).
ERROR_CODES: dict[str, ErrorCode] = {
    "validation_error": ErrorCode(422, "The request is not valid"),
    "unauthorized": ErrorCode(401, "Sign-in required"),
    "forbidden": ErrorCode(403, "Not allowed"),
    "not_found": ErrorCode(404, "Not found"),
    "conflict": ErrorCode(409, "Conflict"),
    "idempotency_conflict": ErrorCode(409, "Idempotency key reused with a different request"),
    "reply_window_closed": ErrorCode(409, "The reply window has closed"),
    "account_needs_reconnect": ErrorCode(409, "The account needs reconnecting"),
    "capability_unavailable": ErrorCode(409, "This account can't do that"),
    "account_in_use": ErrorCode(409, "The account is connected to another workspace"),  # F-04
    "entitlement_required": ErrorCode(402, "Upgrade required"),
    "quota_exceeded": ErrorCode(402, "Plan limit reached"),
    "unsupported_media": ErrorCode(415, "Unsupported media"),
    "rate_limited": ErrorCode(429, "Too many requests"),
    "platform_error": ErrorCode(502, "The platform returned an error"),
    "internal": ErrorCode(500, "Something went wrong"),
    "bad_request": ErrorCode(400, "Bad request"),
    "method_not_allowed": ErrorCode(405, "Method not allowed"),
    "payload_too_large": ErrorCode(413, "Request body too large"),
    "service_unavailable": ErrorCode(503, "Service unavailable"),
}

STATUS_TO_CODE: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media",
    422: "validation_error",
    429: "rate_limited",
    503: "service_unavailable",
}


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


class ApiError(Exception):
    """Raise anywhere in a request; rendered as application/problem+json."""

    def __init__(
        self,
        code: str,
        detail: str | None = None,
        *,
        errors: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code {code!r}")
        super().__init__(detail or code)
        self.code = code
        self.detail = detail
        self.errors = errors or []
        self.headers = headers or {}

    @property
    def status(self) -> int:
        return ERROR_CODES[self.code].status


def problem_body(
    code: str,
    *,
    detail: str | None,
    request_id: str | None,
    errors: list[FieldError] | None = None,
) -> dict[str, Any]:
    spec = ERROR_CODES[code]
    body: dict[str, Any] = {
        "type": ERROR_TYPE_BASE + code,
        "title": spec.title,
        "status": spec.status,
        "code": code,
    }
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = [{"field": e.field, "message": e.message} for e in errors]
    body["request_id"] = request_id
    return body
