"""GR-25, GR-26: key hashing and shape, scope checks, the rate limit, plan gating, and the public
API's own OpenAPI document (every route needs a scope; request strings are bounded; nothing in
the app's own document)."""

from __future__ import annotations

import uuid
from typing import Any, get_args

import pytest

from socialhood.auth.api_key import ApiKeyContext, require_scope
from socialhood.billing.plans import ENTITLEMENTS, PLANS, entitlement
from socialhood.errors import ApiError
from socialhood.main import create_app
from socialhood.schemas.api_keys import MCP_ONLY_SCOPES, SCOPE_DESCRIPTIONS, ApiScopeName
from socialhood.security.ratelimit import LIMITS
from socialhood.services import api_keys
from tests.unit.test_schema_security import (
    ALLOWED,
    FORBIDDEN,
    _property_names,
    _unbounded_strings,
)


def test_a_key_is_long_random_and_prefixed() -> None:
    first, second = api_keys.generate_key(), api_keys.generate_key()
    assert first != second
    assert first.startswith("shk_")
    assert len(first) == 4 + 43
    assert api_keys.looks_like_key(first)


def test_only_the_hash_identifies_a_key() -> None:
    key = api_keys.generate_key()
    digest = api_keys.hash_key(key)
    assert digest == api_keys.hash_key(key)
    assert len(digest) == 64
    assert key not in digest
    assert digest != api_keys.hash_key(key + "x")


@pytest.mark.parametrize(
    "value", ["", "shk_", "shk_short", "Bearer", "sk_" + "a" * 40, "shk_" + "a" * 200]
)
def test_malformed_keys_are_rejected_before_any_lookup(value: str) -> None:
    assert not api_keys.looks_like_key(value)


def test_the_catalogue_describes_every_scope() -> None:
    assert set(SCOPE_DESCRIPTIONS) == set(get_args(ApiScopeName))
    assert [s.scope for s in api_keys.scope_catalogue()] == list(SCOPE_DESCRIPTIONS)


def _context(*scopes: str) -> ApiKeyContext:
    return ApiKeyContext(key_id=uuid.uuid4(), workspace=None, scopes=frozenset(scopes))  # type: ignore[arg-type]


async def test_a_key_without_the_scope_is_forbidden() -> None:
    gate = require_scope("contacts:write")
    with pytest.raises(ApiError) as refused:
        await gate(_context("contacts:read"))
    assert refused.value.code == "forbidden"
    assert "contacts:write" in (refused.value.detail or "")
    ctx = _context("contacts:read", "contacts:write")
    assert await gate(ctx) is ctx
    assert gate.required_scope == "contacts:write"  # type: ignore[attr-defined]


def test_each_key_has_its_own_limit_of_120_a_minute() -> None:
    limit = LIMITS["api_key"]
    assert (limit.max_requests, limit.window_s) == (120, 60)
    assert LIMITS["sends"].max_requests == 60  # sending also counts against the workspace


def test_the_public_api_is_pro_and_max_only_and_webhooks_stay_on_every_plan() -> None:
    assert [entitlement(plan, "public_api") for plan in PLANS] == [False, True, True]
    assert [entitlement(plan, "webhook_endpoints") for plan in PLANS] == [1, 5, 20]
    assert "public_api" in ENTITLEMENTS


# ---------------------------------------------------------------- the public document


@pytest.fixture
def documents(api_settings: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    from socialhood.api.public_openapi import public_openapi

    app = create_app(api_settings)
    return app.openapi(), public_openapi(app)


def test_the_apps_document_leaves_the_public_routes_out(
    documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    main, _ = documents
    assert not [path for path in main["paths"] if path.startswith("/public/")]
    assert "HookSubscribe" not in main["components"]["schemas"]
    assert "/v1/w/{wid}/api-keys" in main["paths"]


def test_every_public_operation_needs_a_known_scope(
    documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    _, public = documents
    assert public["paths"], "no public routes"
    ids: list[str] = []
    used: set[str] = set()
    for path, operations in public["paths"].items():
        assert path.startswith("/public/v1/")
        assert "/openapi.json" not in path
        for method, operation in operations.items():
            where = f"{method.upper()} {path}"
            assert operation["security"] == [{"ApiKey": []}], where
            if operation["operationId"] == "get_key":  # any valid key (how a tool tests it)
                assert "x-required-scope" not in operation, where
            else:
                assert operation["x-required-scope"] in SCOPE_DESCRIPTIONS, where
                assert operation["x-required-scope"] in operation["description"], where
                used.add(operation["x-required-scope"])
            assert operation["responses"]["default"]["content"]["application/problem+json"], where
            ids.append(operation["operationId"])
    assert len(ids) == len(set(ids))
    # No scope a key can carry opens nothing (webhooks:subscribe: tests/unit/test_zapier_hooks.py;
    # the MCP server's own scopes: tests/unit/test_mcp_registry.py).
    assert used >= set(SCOPE_DESCRIPTIONS) - {"webhooks:subscribe", *MCP_ONLY_SCOPES}
    assert public["components"]["securitySchemes"]["ApiKey"]["scheme"] == "bearer"


def test_the_public_document_covers_the_plan(
    documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    _, public = documents
    operations = {(method.upper(), path) for path, ops in public["paths"].items() for method in ops}
    assert {
        ("GET", "/public/v1/contacts"),
        ("POST", "/public/v1/contacts"),
        ("GET", "/public/v1/contacts/{contact_id}"),
        ("PATCH", "/public/v1/contacts/{contact_id}"),
        ("POST", "/public/v1/contacts/{contact_id}/tags"),
        ("GET", "/public/v1/conversations"),
        ("GET", "/public/v1/conversations/{conversation_id}"),
        ("POST", "/public/v1/conversations/{conversation_id}/messages"),
        ("GET", "/public/v1/automation-runs"),
    } <= operations


def test_no_public_response_carries_a_credential(
    documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    _, public = documents
    names = set(_property_names(public["components"]["schemas"]))
    assert sorted(n for n in names if FORBIDDEN.search(n) and n not in ALLOWED) == []


def test_every_public_request_string_has_a_maximum_length(
    documents: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    _, public = documents
    schemas = public["components"]["schemas"]
    unbounded: list[str] = []
    for path, operations in public["paths"].items():
        for method, operation in operations.items():
            route = f"{method.upper()} {path}"
            for param in operation.get("parameters", []):
                where = f"{route} {param['in']}:{param['name']}"
                unbounded += _unbounded_strings(param.get("schema"), schemas, where)
            for media in operation.get("requestBody", {}).get("content", {}).values():
                unbounded += _unbounded_strings(media.get("schema"), schemas, f"{route} body")
    assert sorted(set(unbounded)) == []
