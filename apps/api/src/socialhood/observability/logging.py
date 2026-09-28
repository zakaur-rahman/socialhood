"""JSON logging with redaction (SEC-07, TR-OPS-01).

Values of keys that look like secrets are replaced, and free text (``text``, ``body``) is cut to
40 characters unless the log level is DEBUG. Context such as ``request_id`` is bound through
structlog's context variables.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

REDACTED = "[redacted]"
TEXT_LIMIT = 40

_SECRET_KEY = re.compile(r"token|secret|authorization|password|signature|(?:^|_)code$", re.I)
# Keys ending in "_code" that carry diagnostics, not credentials.
_SAFE_KEYS = frozenset({"status_code", "error_code", "platform_code", "http_status_code"})
_TEXT_KEYS = frozenset({"text", "body"})


def _is_secret_key(key: str) -> bool:
    return key.lower() not in _SAFE_KEYS and bool(_SECRET_KEY.search(key))


def redact(value: Any, *, truncate: bool) -> Any:
    """Return a copy of ``value`` with secret values removed and long text shortened."""
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            name = str(key)
            if _is_secret_key(name):
                out[key] = REDACTED
            elif truncate and name.lower() in _TEXT_KEYS and isinstance(item, str):
                out[key] = item if len(item) <= TEXT_LIMIT else item[:TEXT_LIMIT] + "…"
            else:
                out[key] = redact(item, truncate=truncate)
        return out
    if isinstance(value, list | tuple):
        return type(value)(redact(item, truncate=truncate) for item in value)
    return value


class RedactProcessor:
    def __init__(self, *, truncate: bool) -> None:
        self.truncate = truncate

    def __call__(
        self, logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        cleaned = redact(dict(event_dict), truncate=self.truncate)
        event_dict.clear()
        event_dict.update(cleaned)
        return event_dict


def configure_logging(level: str = "INFO") -> None:
    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):
        numeric = logging.INFO
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
        RedactProcessor(truncate=numeric > logging.DEBUG),
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=numeric, format="%(message)s", stream=sys.stdout, force=True)


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
