"""The public API's own OpenAPI document (GR-25): only /public/v1, served as JSON at
``GET /public/v1/openapi.json`` and rendered by the web app's docs page.

It is built from the app's routes under /public/v1 and cached on the app. Each operation says
which scope it needs (``x-required-scope``, and in its description), every operation is marked as
needing the API key, and errors are described as problem+json like the app's own document.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from socialhood import __version__
from socialhood.api.openapi_errors import describe_problems
from socialhood.schemas.api_keys import SCOPE_DESCRIPTIONS

DESCRIPTION = (
    "The Amplychat public API reads and updates a workspace's contacts, tags, conversations "
    "and automation runs, sends messages inside the platform's reply window, and subscribes "
    "REST hooks. Make a key in Settings, Integrations, and send it as "
    "`Authorization: Bearer <key>`. The public API is part of the Pro and Max plans. Each key "
    "can make 120 requests a minute; sending also counts against the workspace's 60 sends a "
    "minute. Errors are `application/problem+json`."
)


def _required_scopes(routes: list[APIRoute]) -> dict[tuple[str, str], str]:
    found: dict[tuple[str, str], str] = {}
    for route in routes:
        scopes = [
            scope
            for sub in route.dependant.dependencies
            if (scope := getattr(sub.call, "required_scope", None))
        ]
        for method in route.methods or ():
            if scopes:
                found[(route.path, method.lower())] = scopes[0]
    return found


def public_openapi(app: FastAPI) -> dict[str, Any]:
    cached: dict[str, Any] | None = getattr(app.state, "public_openapi_schema", None)
    if cached is not None:
        return cached
    from socialhood.api import public, public_hooks

    routes = [
        r
        for router in (public.router, public_hooks.router)
        for r in router.routes
        if isinstance(r, APIRoute)
    ]
    schema = describe_problems(
        get_openapi(
            title="Amplychat public API",
            version=__version__,
            description=DESCRIPTION,
            routes=routes,
        )
    )
    scopes = _required_scopes(routes)
    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
            operation["security"] = [{"ApiKey": []}]
            scope = scopes.get((path, method))
            if scope:
                operation["x-required-scope"] = scope
                operation["description"] = (
                    f"{operation.get('description', '')}\n\nRequires the `{scope}` scope."
                ).strip()
    schema.setdefault("components", {})["securitySchemes"] = {
        "ApiKey": {
            "type": "http",
            "scheme": "bearer",
            "description": "A workspace API key, made in Settings, Integrations.",
        }
    }
    schema["x-scopes"] = SCOPE_DESCRIPTIONS
    app.state.public_openapi_schema = schema
    return schema
