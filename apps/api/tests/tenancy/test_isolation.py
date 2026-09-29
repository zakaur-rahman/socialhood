"""TR-TEN-03: every route with an id in its path hides other workspaces.

Workspaces A and B each get one of every resource. For every such route in the OpenAPI document,
a member of A calls it with B's ids: the answer must be 404 and B must be unchanged. Routes with ids
below the workspace are called a second time with A's own workspace and B's resource ids, which
tests the row filter rather than membership. A route whose path parameters (or request body) have
no seed entry fails the suite, so new routes cannot slip through without coverage. Public routes
(no workspace, no session) are listed in ``PUBLIC_ROUTES`` and tested on their own.

When a phase adds a resource, extend ``Seed`` with B's id for it, map the path parameter in
``PARAM_TO_SEED``, and add an example body for any new write route in ``EXAMPLE_BODIES``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.ai import (
    make_analysis,
    make_decision,
    make_gap,
    make_source,
    make_suggestion,
)
from tests.support.api import Clerk, sign_in
from tests.support.automations import make_automation
from tests.support.inbox import make_asset, make_scheduled, make_thread

METHODS = ("get", "post", "put", "patch", "delete")

# Path parameter name -> Seed attribute holding workspace B's id for it.
PARAM_TO_SEED: dict[str, str] = {
    "wid": "workspace_id",
    "account_id": "account_id",
    "conversation_id": "conversation_id",
    "message_id": "message_id",
    "scheduled_message_id": "scheduled_message_id",
    "asset_id": "asset_id",
    "automation_id": "automation_id",
    "analysis_id": "analysis_id",
    "suggestion_id": "suggestion_id",
    "source_id": "source_id",
    "gap_id": "gap_id",
    "decision_id": "decision_id",
}

# Public routes keyed by something other than a workspace; each has its own tests.
PUBLIC_ROUTES = frozenset({"/v1/data-deletion/{code}"})

# A valid body for each write route, so the call fails on tenancy, not validation.
# A string "{param}" in a body is replaced by B's id for that parameter.
EXAMPLE_BODIES: dict[tuple[str, str], dict[str, Any]] = {
    ("PATCH", "/v1/w/{wid}"): {"name": "Taken over", "timezone": "UTC"},
    ("PATCH", "/v1/w/{wid}/social-accounts/{account_id}"): {"auto_hide_spam": True},
    ("POST", "/v1/w/{wid}/dev/sandbox/inbound"): {
        "account_id": "{account_id}",
        "kind": "dm",
        "text": "Injected into B",
    },
    ("POST", "/v1/w/{wid}/notifications/read"): {"all": True},
    ("PATCH", "/v1/w/{wid}/conversations/{conversation_id}"): {"status": "archived"},
    ("POST", "/v1/w/{wid}/conversations/{conversation_id}/messages"): {
        "client_id": "5f0c3c1e-2d7a-4b43-9d35-9d7f0b0c2a11",
        "text": "Sent into B",
    },
    ("POST", "/v1/w/{wid}/conversations/{conversation_id}/scheduled-messages"): {
        "text": "Scheduled into B",
        "send_at": "2030-01-01T09:00:00Z",
    },
    ("PATCH", "/v1/w/{wid}/scheduled-messages/{scheduled_message_id}"): {"text": "Changed"},
    ("POST", "/v1/w/{wid}/media-assets/upload-signature"): {
        "resource_type": "image",
        "purpose": "message",
    },
    ("POST", "/v1/w/{wid}/media-assets"): {
        "public_id": "ws/not-yours/message/x",
        "resource_type": "image",
    },
    ("POST", "/v1/w/{wid}/social-accounts/whatsapp/embedded-signup"): {
        "code": "c",
        "waba_id": "1",
        "phone_number_id": "2",
    },
}

EXAMPLE_BODIES.update(
    {
        ("POST", "/v1/w/{wid}/automations"): {"name": "Taken over"},
        ("PUT", "/v1/w/{wid}/automations/priorities"): {
            "social_account_id": "{account_id}",
            "ordered_ids": ["{automation_id}"],
        },
        ("POST", "/v1/w/{wid}/automations/pause"): {"ids": ["{automation_id}"]},
        ("PUT", "/v1/w/{wid}/automations/{automation_id}"): {"name": "Taken over"},
        ("POST", "/v1/w/{wid}/automations/{automation_id}/test"): {"kind": "dm", "text": "link"},
    }
)

EXAMPLE_BODIES.update(
    {
        ("PATCH", "/v1/w/{wid}/message-analyses/{analysis_id}"): {"intent": "complaint"},
        ("PATCH", "/v1/w/{wid}/knowledge-sources/{source_id}"): {"title": "Taken over"},
        ("POST", "/v1/w/{wid}/ai-decisions/{decision_id}/feedback"): {"feedback": "bad"},
    }
)

# Knowledge (T5.3, T5.10): answering B's gap from A's workspace must be 404 and leave it open.
EXAMPLE_BODIES.update(
    {
        ("POST", "/v1/w/{wid}/knowledge-sources"): {
            "type": "faq",
            "question": "Do you ship to Dubai?",
            "body": "Yes.",
            "gap_id": "{gap_id}",
        },
        ("POST", "/v1/w/{wid}/knowledge/test"): {"question": "Do you ship to Dubai?"},
    }
)

# Headers a route requires, so the call fails on tenancy, not validation.
EXAMPLE_HEADERS: dict[tuple[str, str], dict[str, str]] = {
    ("POST", "/v1/w/{wid}/conversations/{conversation_id}/messages"): {
        "Idempotency-Key": "isolation-test-key"
    },
}

# Tables snapshotted for workspace B before and after every call.
B_TABLES = (
    "workspaces",
    "workspace_members",
    "subscriptions",
    "ai_settings",
    "usage_counters",
    "social_accounts",
    "notifications",
    "contacts",
    "conversations",
    "messages",
    "scheduled_messages",
    "media_assets",
    "automations",
    "automation_keywords",
    "automation_runs",
    "comments",
    "message_analyses",
    "reply_suggestions",
    "knowledge_sources",
    "knowledge_chunks",
    "knowledge_gaps",
    "ai_decisions",
    "ai_usage_events",
)


@dataclass(frozen=True)
class Seed:
    workspace_id: str
    account_id: str = ""
    conversation_id: str = ""
    message_id: str = ""
    scheduled_message_id: str = ""
    asset_id: str = ""
    automation_id: str = ""
    analysis_id: str = ""
    suggestion_id: str = ""
    source_id: str = ""
    gap_id: str = ""
    decision_id: str = ""


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    url: str
    body: dict[str, Any] | None
    headers: dict[str, str]


def _fill(body: dict[str, Any] | None, seed: Seed) -> tuple[dict[str, Any] | None, bool]:
    """Resolve "{param}" placeholders; report whether the body refers to another resource."""
    if body is None:
        return None, False
    refers = False

    def resolve(value: Any) -> Any:
        nonlocal refers
        if isinstance(value, list):
            return [resolve(item) for item in value]
        match = re.fullmatch(r"{(\w+)}", value) if isinstance(value, str) else None
        if match:
            refers = True
            return getattr(seed, PARAM_TO_SEED[match.group(1)])
        return value

    filled = {key: resolve(value) for key, value in body.items()}
    return filled, refers


def plan_calls(
    openapi: dict[str, Any], seed: Seed, *, nested_only: bool = False
) -> tuple[list[Call], list[str]]:
    """Return the calls to make and the routes that lack seed data.

    ``nested_only`` keeps the routes that name a resource besides the workspace (in the path or
    the body), for the pass that uses the caller's own workspace.
    """
    calls: list[Call] = []
    uncovered: list[str] = []
    for path, operations in openapi.get("paths", {}).items():
        params = re.findall(r"{(\w+)}", path)
        if not params or path in PUBLIC_ROUTES:
            continue
        for method in METHODS:
            operation = operations.get(method)
            if operation is None or "x-pending" in operation:
                continue  # stubs of routes not built yet (see the route module)
            key = (method.upper(), path)
            missing = [p for p in params if p not in PARAM_TO_SEED]
            needs_body = "requestBody" in operation and key not in EXAMPLE_BODIES
            if missing or needs_body:
                reason = f"params {missing}" if missing else "no example body"
                uncovered.append(f"{method.upper()} {path} ({reason})")
                continue
            body, refers = _fill(EXAMPLE_BODIES.get(key), seed)
            if nested_only and params == ["wid"] and not refers:
                continue
            url = path.format(**{p: getattr(seed, PARAM_TO_SEED[p]) for p in params})
            calls.append(Call(method.upper(), path, url, body, EXAMPLE_HEADERS.get(key, {})))
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


async def seed_workspace_b(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Seed:
    """Workspace B with one of every resource, created through the API."""
    owner_b, b = await sign_in(client, clerk, email="b@example.com", first_name="Ben")
    wid = b["workspaces"][0]["id"]
    account = await client.post(f"/v1/w/{wid}/dev/sandbox/accounts", headers=clerk.headers(owner_b))
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    thread = await make_thread(engine, workspace_id=wid, account_id=account_id)
    scheduled = await make_scheduled(
        engine, workspace_id=wid, conversation_id=thread.conversation_id
    )
    asset = await make_asset(engine, workspace_id=wid)
    automation = await make_automation(engine, workspace_id=wid, account_id=account_id)
    on = {
        "workspace_id": wid,
        "conversation_id": thread.conversation_id,
        "message_id": thread.message_ids[0],
    }
    analysis = await make_analysis(engine, **on)
    suggestion = await make_suggestion(engine, **on)
    decision = await make_decision(engine, **on)
    source = await make_source(engine, workspace_id=wid)
    gap = await make_gap(engine, workspace_id=wid)
    return Seed(
        workspace_id=wid,
        account_id=account_id,
        conversation_id=str(thread.conversation_id),
        message_id=str(thread.message_ids[0]),
        scheduled_message_id=str(scheduled),
        asset_id=str(asset),
        automation_id=str(automation),
        analysis_id=str(analysis),
        suggestion_id=str(suggestion),
        source_id=str(source),
        gap_id=str(gap),
        decision_id=str(decision),
    )


async def test_every_route_with_a_path_id_hides_other_workspaces(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    member_a, a = await sign_in(client, clerk, email="a@example.com", first_name="Anna")
    seed = await seed_workspace_b(client, clerk, engine)
    own = replace(seed, workspace_id=a["workspaces"][0]["id"])

    calls, uncovered = plan_calls(app.openapi(), seed)
    assert not uncovered, "Routes without isolation seed data:\n" + "\n".join(uncovered)
    assert calls, "no routes with path ids found; is the router mounted?"
    nested, _ = plan_calls(app.openapi(), own, nested_only=True)
    assert nested, "no nested routes found"

    headers = clerk.headers(member_a)
    for call in calls + nested:
        before = await snapshot(engine, seed.workspace_id)
        response = await client.request(
            call.method, call.url, json=call.body, headers={**headers, **call.headers}
        )
        assert response.status_code == 404, f"{call.method} {call.url}: {response.text}"
        assert response.json()["code"] == "not_found"
        assert await snapshot(engine, seed.workspace_id) == before, f"{call.method} {call.url}"


def test_a_new_route_without_seed_data_fails_the_suite() -> None:
    openapi = {
        "paths": {
            "/v1/w/{wid}": {"get": {}},
            "/v1/w/{wid}/widgets/{widget_id}": {"get": {}},
            "/v1/w/{wid}/things": {"post": {"requestBody": {}}},
        }
    }
    calls, uncovered = plan_calls(openapi, Seed(workspace_id="b"))
    assert [c.url for c in calls] == ["/v1/w/b"]
    assert plan_calls(openapi, Seed(workspace_id="b"), nested_only=True)[0] == []
    assert uncovered == [
        "GET /v1/w/{wid}/widgets/{widget_id} (params ['widget_id'])",
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
