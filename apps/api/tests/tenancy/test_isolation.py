"""TR-TEN-03: every route with an id in its path hides other workspaces.

Workspaces A and B each get one of every resource. For every such route in the OpenAPI document,
a member of A calls it with B's ids: the answer must be 404 and B must be unchanged. A route whose
path parameters (or request body) have no seed entry fails the suite, so new routes cannot slip
through without coverage.

When a phase adds a resource, extend ``Seed`` with B's id for it, map the path parameter in
``PARAM_TO_SEED``, and add an example body for any new write route in ``EXAMPLE_BODIES``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk, sign_in

METHODS = ("get", "post", "put", "patch", "delete")

# Path parameter name -> Seed attribute holding workspace B's id for it.
PARAM_TO_SEED: dict[str, str] = {
    "wid": "workspace_id",
}

# A valid body for each write route, so the call fails on tenancy, not validation.
EXAMPLE_BODIES: dict[tuple[str, str], dict[str, Any]] = {
    ("PATCH", "/v1/w/{wid}"): {"name": "Taken over", "timezone": "UTC"},
}

# Tables snapshotted for workspace B before and after every call.
B_TABLES = ("workspaces", "workspace_members", "subscriptions", "ai_settings", "usage_counters")


@dataclass(frozen=True)
class Seed:
    workspace_id: str


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    url: str
    body: dict[str, Any] | None


def plan_calls(openapi: dict[str, Any], seed: Seed) -> tuple[list[Call], list[str]]:
    """Return the calls to make and the routes that lack seed data."""
    calls: list[Call] = []
    uncovered: list[str] = []
    for path, operations in openapi.get("paths", {}).items():
        params = re.findall(r"{(\w+)}", path)
        if not params:
            continue
        for method in METHODS:
            operation = operations.get(method)
            if operation is None:
                continue
            key = (method.upper(), path)
            missing = [p for p in params if p not in PARAM_TO_SEED]
            needs_body = "requestBody" in operation and key not in EXAMPLE_BODIES
            if missing or needs_body:
                reason = f"params {missing}" if missing else "no example body"
                uncovered.append(f"{method.upper()} {path} ({reason})")
                continue
            url = path.format(**{p: getattr(seed, PARAM_TO_SEED[p]) for p in params})
            calls.append(Call(method.upper(), path, url, EXAMPLE_BODIES.get(key)))
    return calls, uncovered


async def snapshot(engine: AsyncEngine, workspace_id: str) -> str:
    parts = {}
    async with engine.connect() as conn:
        for table in B_TABLES:
            column = "id" if table == "workspaces" else "workspace_id"
            rows = await conn.execute(
                text(f"SELECT * FROM {table} WHERE {column} = :w ORDER BY id"),  # noqa: S608
                {"w": workspace_id},
            )
            parts[table] = [dict(row._mapping) for row in rows]
    return json.dumps(parts, default=str, sort_keys=True)


async def test_every_route_with_a_path_id_hides_other_workspaces(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    member_a, _ = await sign_in(client, clerk, email="a@example.com", first_name="Anna")
    _, b = await sign_in(client, clerk, email="b@example.com", first_name="Ben")
    seed = Seed(workspace_id=b["workspaces"][0]["id"])

    calls, uncovered = plan_calls(app.openapi(), seed)
    assert not uncovered, "Routes without isolation seed data:\n" + "\n".join(uncovered)
    assert calls, "no routes with path ids found; is the router mounted?"

    headers = clerk.headers(member_a)
    for call in calls:
        before = await snapshot(engine, seed.workspace_id)
        response = await client.request(call.method, call.url, json=call.body, headers=headers)
        assert response.status_code == 404, f"{call.method} {call.path}: {response.text}"
        assert response.json()["code"] == "not_found"
        assert await snapshot(engine, seed.workspace_id) == before, f"{call.method} {call.path}"


def test_a_new_route_without_seed_data_fails_the_suite() -> None:
    openapi = {
        "paths": {
            "/v1/w/{wid}": {"get": {}},
            "/v1/w/{wid}/automations/{automation_id}": {"get": {}},
            "/v1/w/{wid}/things": {"post": {"requestBody": {}}},
        }
    }
    calls, uncovered = plan_calls(openapi, Seed(workspace_id="b"))
    assert [c.url for c in calls] == ["/v1/w/b"]
    assert uncovered == [
        "GET /v1/w/{wid}/automations/{automation_id} (params ['automation_id'])",
        "POST /v1/w/{wid}/things (no example body)",
    ]


@pytest.mark.parametrize("path", ["/v1/me", "/v1/workspaces"])
async def test_user_level_routes_only_list_the_callers_workspaces(
    client: httpx.AsyncClient, clerk: Clerk, path: str
) -> None:
    member_a, a = await sign_in(client, clerk, email="a@example.com")
    await sign_in(client, clerk, email="b@example.com")
    body = (await client.get(path, headers=clerk.headers(member_a))).json()
    listed = body["workspaces"] if path == "/v1/me" else body["items"]
    assert [w["id"] for w in listed] == [a["workspaces"][0]["id"]]
