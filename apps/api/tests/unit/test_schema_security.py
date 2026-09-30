"""SEC-02: no response ever carries a token or secret; SEC-10: no library logs request URLs."""

from __future__ import annotations

import logging
import re
from typing import Any

from socialhood.main import create_app
from socialhood.observability.logging import QUIET_LOGGERS, configure_logging

FORBIDDEN = re.compile(r"token|secret|password|_enc$", re.IGNORECASE)
ALLOWED = {"token_expires_at"}  # when the connection lapses, not a credential


def _property_names(schema: Any) -> list[str]:
    names: list[str] = []
    if isinstance(schema, dict):
        for key, value in schema.get("properties", {}).items():
            names.append(key)
            names.extend(_property_names(value))
        for value in schema.values():
            if isinstance(value, (dict, list)):
                names.extend(_property_names(value))
    elif isinstance(schema, list):
        for item in schema:
            names.extend(_property_names(item))
    return names


def test_no_schema_property_looks_like_a_credential(api_settings: Any) -> None:
    openapi = create_app(api_settings).openapi()
    names = set(_property_names(openapi["components"]["schemas"]))
    leaked = sorted(n for n in names if FORBIDDEN.search(n) and n not in ALLOWED)
    assert leaked == []


# Strings bounded by their format.
BOUNDED_FORMATS = {"uuid", "date-time", "date", "time", "duration"}


def _unbounded_strings(
    node: Any, schemas: dict[str, Any], where: str, seen: frozenset[str] = frozenset()
) -> list[str]:
    if not isinstance(node, dict):
        return []
    if ref := node.get("$ref"):
        name = ref.rsplit("/", 1)[-1]
        return (
            [] if name in seen else _unbounded_strings(schemas[name], schemas, name, seen | {name})
        )
    found = []
    if node.get("type") == "string" and not (
        "maxLength" in node
        or "enum" in node
        or "const" in node
        or node.get("format") in BOUNDED_FORMATS
    ):
        found.append(where)
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in node.get(key, []):
            found += _unbounded_strings(sub, schemas, where, seen)
    found += _unbounded_strings(node.get("items"), schemas, f"{where}[]", seen)
    for prop, sub in node.get("properties", {}).items():
        found += _unbounded_strings(sub, schemas, f"{where}.{prop}", seen)
    found += _unbounded_strings(node.get("additionalProperties"), schemas, f"{where}{{}}", seen)
    return found


def test_every_request_string_has_a_maximum_length(api_settings: Any) -> None:
    """SEC-08: every string a client sends (bodies, query, path and headers) has a maxLength in
    the schema, or is an enum, a constant, a UUID or a date."""
    openapi = create_app(api_settings).openapi()
    schemas = openapi["components"]["schemas"]
    unbounded = []
    for path, operations in openapi["paths"].items():
        for method, operation in operations.items():
            route = f"{method.upper()} {path}"
            for param in operation.get("parameters", []):
                where = f"{route} {param['in']}:{param['name']}"
                unbounded += _unbounded_strings(param.get("schema"), schemas, where)
            for media in operation.get("requestBody", {}).get("content", {}).values():
                unbounded += _unbounded_strings(media.get("schema"), schemas, f"{route} body")
    assert sorted(set(unbounded)) == []


def test_http_client_request_logs_are_silenced() -> None:
    configure_logging("DEBUG")
    try:
        for name in QUIET_LOGGERS:
            assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
    finally:
        configure_logging("INFO")
