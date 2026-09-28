"""Exception handlers: every non-2xx response is application/problem+json (TR-API-03)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from socialhood.errors import STATUS_TO_CODE, ApiError, FieldError, problem_body
from socialhood.observability.request_id import current_request_id

PROBLEM_JSON = "application/problem+json"


def problem_response(
    code: str,
    *,
    detail: str | None = None,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = problem_body(code, detail=detail, errors=errors, request_id=current_request_id.get())
    return JSONResponse(body, status_code=body["status"], media_type=PROBLEM_JSON, headers=headers)


def _field_name(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc]
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]
    return ".".join(parts) or "request"


async def _api_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return problem_response(exc.code, detail=exc.detail, errors=exc.errors, headers=exc.headers)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        FieldError(_field_name(tuple(e.get("loc", ()))), str(e.get("msg", "")))
        for e in exc.errors()
    ]
    return problem_response("validation_error", errors=errors)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = STATUS_TO_CODE.get(exc.status_code)
    if code is None:
        code = "internal" if exc.status_code >= 500 else "bad_request"
    headers = dict(exc.headers) if exc.headers else None
    return problem_response(code, headers=headers)


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
