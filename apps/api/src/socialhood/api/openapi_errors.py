"""Describe errors truthfully in the OpenAPI document (TR-API-03, TR-API-08).

FastAPI documents 422 as its own ``HTTPValidationError`` shape, but every non-2xx response here
is application/problem+json. This replaces that with a ``Problem`` schema and adds a ``default``
problem response to each operation, so generated client types match what the API sends.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi

PROBLEM_SCHEMA: dict[str, Any] = {
    "title": "Problem",
    "type": "object",
    "required": ["type", "title", "status", "code"],
    "properties": {
        "type": {"type": "string", "title": "Type"},
        "title": {"type": "string", "title": "Title"},
        "status": {"type": "integer", "title": "Status"},
        "code": {"type": "string", "title": "Code"},
        "detail": {"type": "string", "title": "Detail"},
        "errors": {
            "type": "array",
            "title": "Errors",
            "items": {
                "type": "object",
                "required": ["field", "message"],
                "properties": {
                    "field": {"type": "string", "title": "Field"},
                    "message": {"type": "string", "title": "Message"},
                },
            },
        },
        # 402 only (entitlement_required, quota_exceeded; errors.PlanLimit): the §1.7 key and,
        # for quota_exceeded, the plan's limit (null = the plan has none, e.g. a missing feature).
        "entitlement": {"type": "string", "title": "Entitlement"},
        "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "title": "Limit"},
        "request_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Request Id"},
    },
}

_PROBLEM_RESPONSE: dict[str, Any] = {
    "description": "Problem details (application/problem+json)",
    "content": {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}},
}


def problem_openapi(app: FastAPI, hidden: tuple[APIRouter, ...] = ()) -> dict[str, Any]:
    """The app's document, without the routers in ``hidden`` (the public API's)."""
    if app.openapi_schema:
        return app.openapi_schema
    routes = [r for r in app.routes if getattr(r, "original_router", None) not in hidden]
    schema = get_openapi(title=app.title, version=app.version, routes=routes)
    app.openapi_schema = describe_problems(schema)
    return app.openapi_schema


def describe_problems(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace FastAPI's 422 shape with ``Problem`` and add the ``default`` problem response."""
    schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    schemas["Problem"] = PROBLEM_SCHEMA
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            responses = operation.setdefault("responses", {})
            if "422" in responses:
                responses["422"] = {**_PROBLEM_RESPONSE, "description": "Validation error"}
            responses["default"] = _PROBLEM_RESPONSE
    return schema
