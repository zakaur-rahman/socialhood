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


def test_http_client_request_logs_are_silenced() -> None:
    configure_logging("DEBUG")
    try:
        for name in QUIET_LOGGERS:
            assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
    finally:
        configure_logging("INFO")
