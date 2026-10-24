"""GR-19: every write route in a workspace declares a permission, so a new route can't forget.

Like the tenancy walk, this reads the app's routes: a POST, PUT, PATCH or DELETE under
/v1/w/{wid} must depend on ``require_permission(...)``. Write routes outside a workspace are
listed below with the reason they need none.
"""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute, _iter_routes_with_context

from socialhood.auth.permissions import Permission
from socialhood.main import create_app

WRITE = {"POST", "PUT", "PATCH", "DELETE"}
# Write routes with no workspace in the path: the caller's own account, or a signed webhook.
NO_WORKSPACE = {
    ("POST", "/v1/me/push-subscriptions"),
    ("DELETE", "/v1/me/push-subscriptions"),
    ("POST", "/v1/digest/unsubscribe"),
}


def _permissions(dependant: Any) -> set[Permission]:
    found: set[Permission] = set()
    for sub in dependant.dependencies:
        permission = getattr(sub.call, "permission", None)
        if permission is not None:
            found.add(permission)
        found |= _permissions(sub)
    return found


def _write_routes(app: Any) -> list[tuple[str, str, APIRoute]]:
    """FastAPI 0.141 keeps included routers as `_IncludedRouter` objects in `app.routes`, so the
    real routes are reached through its route iterator, not by reading `app.routes` directly."""
    routes = [route for route, _ in _iter_routes_with_context(app.routes)]
    found = [
        (method, route.path, route)
        for route in routes
        if isinstance(route, APIRoute) and route.path.startswith("/v1/")
        for method in sorted(route.methods & WRITE)
    ]
    # A walk that finds almost nothing passes for the wrong reason (it did, before this check).
    assert len(found) > 100, f"only {len(found)} write routes found: is the router walk broken?"
    return found


def test_every_workspace_write_route_declares_a_permission(api_settings: Any) -> None:
    app = create_app(api_settings)
    missing = [
        f"{method} {path}"
        for method, path, route in _write_routes(app)
        if path.startswith("/v1/w/{wid}") and not _permissions(route.dependant)
    ]
    assert missing == [], "Write routes without require_permission:\n" + "\n".join(missing)


def test_write_routes_outside_a_workspace_are_known(api_settings: Any) -> None:
    app = create_app(api_settings)
    outside = {
        (method, path)
        for method, path, _ in _write_routes(app)
        if not path.startswith("/v1/w/{wid}")
    }
    unknown = sorted(outside - NO_WORKSPACE)
    assert unknown == [], (
        f"Write routes outside a workspace need a reason in NO_WORKSPACE: {unknown}"
    )
