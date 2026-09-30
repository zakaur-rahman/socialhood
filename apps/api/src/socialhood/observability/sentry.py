"""Sentry on the API and the worker (TR-OPS-01, SEC-12, T9.3).

Nothing happens without ``SENTRY_DSN``: local runs and tests send nothing, and every
``sentry_sdk`` call is a no-op. With a DSN, every event and transaction passes ``scrub_event``:

- the request keeps only its method and its URL without the query string: no headers (so no
  Authorization or cookies), no body, no client IP;
- the user keeps only the internal id;
- no local variables are captured, and span and breadcrumb URLs lose their query strings (Meta's
  token endpoints take secrets as query parameters);
- free-text fields (``text``, ``body``, ``caption``…) are dropped by name, secret-looking keys are
  redacted, and emails, bearer tokens, JWTs and long token-like strings are masked in any text.

Customer message text is never attached on purpose; the scrubber is the safety net. The Gemini and
Pydantic AI integrations are off, so prompts never become span data.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any, Literal, cast

import sentry_sdk
import structlog
from sentry_sdk.integrations.asyncio import enable_asyncio_integration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.google_genai import GoogleGenAIIntegration
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.integrations.pydantic_ai import PydanticAIIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber
from sentry_sdk.transport import Transport

from socialhood import __version__
from socialhood.observability.logging import REDACTED, is_secret_key
from socialhood.settings import Settings

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint

Component = Literal["api", "worker"]

# Keys whose values are customer or user content: dropped wherever they appear.
TEXT_KEYS = frozenset(
    {
        "text",
        "body",
        "caption",
        "content",
        "contents",
        "prompt",
        "reply",
        "message_text",
        "comment_text",
        "first_comment",
        "email",
        "phone",
        "raw",
        "payload",
        "data",
    }
)
# Keys the logging redactor does not already treat as secret.
EXTRA_SECRET_KEYS = frozenset(
    {"cookie", "cookies", "set-cookie", "set_cookie", "session", "dsn", "api_key", "apikey"}
)
# Context the scrubber must never touch: Sentry's own trace and runtime blocks.
_SAFE_CONTEXTS = frozenset({"trace", "runtime", "os", "device", "app", "response"})

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
# 40+ characters with letters and digits: platform tokens, keys, signatures. UUIDs (36) survive.
_LONG_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_-])(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{40,}"
    r"(?![A-Za-z0-9_-])"
)
_QUERY = re.compile(r"\?[^\s\"'#]*")

_initialized: Component | None = None


def init_sentry(
    settings: Settings, *, component: Component, transport: Transport | None = None
) -> bool:
    """Start Sentry for this process once. Returns False (and does nothing) without a DSN.

    ``transport`` is for tests. The asyncio integration needs the running loop, so callers turn
    it on with ``instrument_running_loop`` from inside it (the API's lifespan, the first job).
    """
    global _initialized
    if not settings.sentry_dsn:
        return False
    if _initialized is not None and sentry_sdk.get_client().is_active():
        return True
    options: dict[str, Any] = {}
    if transport is not None:
        options["transport"] = transport
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env.value,
        release=settings.sentry_release or f"socialhood-api@{__version__}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=_before_send,
        before_send_transaction=_before_send,
        before_breadcrumb=scrub_breadcrumb,
        event_scrubber=EventScrubber(
            denylist=[*DEFAULT_DENYLIST, *EXTRA_SECRET_KEYS], recursive=True
        ),
        integrations=[
            StarletteIntegration(transaction_style="url"),
            FastApiIntegration(transaction_style="url"),
        ],
        disabled_integrations=[GoogleGenAIIntegration(), PydanticAIIntegration()],
        **options,
    )
    sentry_sdk.get_global_scope().set_tag("component", component)
    # Job failures are reported by the job middleware with the job's tags; the worker's own
    # error log line for the same failure would be a duplicate without them.
    ignore_logger("procrastinate.worker")
    _initialized = component
    return True


def _before_send(event: Event, hint: Hint) -> Event | None:
    return cast("Event", scrub_event(cast("dict[str, Any]", event), hint))


def instrument_running_loop() -> None:
    """Capture errors in background asyncio tasks. Call from inside the running loop."""
    if sentry_sdk.get_client().is_active():
        enable_asyncio_integration()


def reset_for_tests() -> None:
    global _initialized
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)  # back to the no-op client
    _initialized = None


# ---------------------------------------------------------------- structlog → Sentry

_ERROR_METHODS = frozenset({"error", "exception", "critical", "fatal"})
_LOG_FIELDS_SKIPPED = frozenset({"event", "level", "timestamp", "exc_info"})


class SentryLogProcessor:
    """Send error-level log events to Sentry: alerts (``log.error("alert", kind=…)``, which the
    maintenance jobs raise) and logged exceptions. structlog prints straight to stdout, so Sentry's
    logging integration never sees them. A no-op while Sentry is off."""

    def __call__(
        self, logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        if method_name not in _ERROR_METHODS or not sentry_sdk.get_client().is_active():
            return event_dict
        name = str(event_dict.get("event", "log"))
        fields = {k: v for k, v in event_dict.items() if k not in _LOG_FIELDS_SKIPPED}
        error = _exception_of(event_dict.get("exc_info"), method_name)
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("log_event", name)
            kind = fields.get("kind")
            if isinstance(kind, str):
                scope.set_tag("alert_kind" if name == "alert" else "kind", kind)
            scope.set_extra("log", scrub_value(fields))
            if error is not None:
                sentry_sdk.capture_exception(error)
            else:
                detail = fields.get("detail")
                scope.fingerprint = ["log", name, kind if isinstance(kind, str) else ""]
                message = f"{name}: {detail}" if isinstance(detail, str) else name
                sentry_sdk.capture_message(message, level="error")
        return event_dict


def _exception_of(exc_info: Any, method_name: str) -> BaseException | None:
    if isinstance(exc_info, BaseException):
        return exc_info
    if isinstance(exc_info, tuple) and len(exc_info) == 3:
        return exc_info[1] if isinstance(exc_info[1], BaseException) else None
    if exc_info is True or method_name == "exception":
        return sys.exc_info()[1]
    return None


# ---------------------------------------------------------------- scrubbing


def scrub_text(value: str) -> str:
    """Mask emails, credentials and query strings inside free text."""
    value = _EMAIL.sub("[email]", value)
    value = _BEARER.sub(r"\1 [redacted]", value)
    value = _JWT.sub("[jwt]", value)
    value = _LONG_TOKEN.sub("[token]", value)
    return value


def strip_query(url: str) -> str:
    return _QUERY.sub("", url)


def _is_secret(key: str) -> bool:
    lowered = key.lower()
    return is_secret_key(key) or lowered in EXTRA_SECRET_KEYS


def scrub_value(value: Any) -> Any:
    """Recursively drop content keys, redact secret keys and mask text."""
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name.lower() in TEXT_KEYS:
                continue
            out[key] = REDACTED if _is_secret(name) else scrub_value(item)
        return out
    if isinstance(value, list | tuple):
        return [scrub_value(item) for item in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


def _scrub_url_fields(data: dict[str, Any]) -> dict[str, Any]:
    data.pop("http.query", None)
    data.pop("http.fragment", None)
    for key in ("url", "http.url", "server.address.full"):
        if isinstance(data.get(key), str):
            data[key] = strip_query(data[key])
    return data


def scrub_breadcrumb(crumb: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(crumb.get("message"), str):
        crumb["message"] = scrub_text(strip_query(crumb["message"]))
    if isinstance(crumb.get("data"), dict):
        crumb["data"] = scrub_value(_scrub_url_fields(dict(crumb["data"])))
    return crumb


def _context_tags() -> dict[str, str]:
    """Ids bound for logging (TR-OPS-01): request, workspace, user and job."""
    bound = structlog.contextvars.get_contextvars()
    return {
        key: str(bound[key])
        for key in ("request_id", "workspace_id", "user_id", "job")
        if bound.get(key) is not None
    }


def scrub_event(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """``before_send`` and ``before_send_transaction``: see the module docstring."""
    request = event.get("request")
    if isinstance(request, dict):
        kept: dict[str, Any] = {}
        if isinstance(request.get("method"), str):
            kept["method"] = request["method"]
        if isinstance(request.get("url"), str):
            kept["url"] = strip_query(request["url"])
        event["request"] = kept

    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if user.get("id") else {}

    for key in ("message", "transaction"):
        if isinstance(event.get(key), str):
            event[key] = scrub_text(event[key])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("message", "formatted"):
            if isinstance(logentry.get(key), str):
                logentry[key] = scrub_text(logentry[key])
        logentry.pop("params", None)

    for exception in (event.get("exception") or {}).get("values") or []:
        if isinstance(exception.get("value"), str):
            exception["value"] = scrub_text(exception["value"])
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    for thread in (event.get("threads") or {}).get("values") or []:
        for frame in (thread.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        breadcrumbs["values"] = [scrub_breadcrumb(c) for c in breadcrumbs.get("values") or []]

    if "extra" in event:
        event["extra"] = scrub_value(event["extra"])
    contexts = event.get("contexts")
    if isinstance(contexts, dict):
        for name, block in list(contexts.items()):
            if name not in _SAFE_CONTEXTS:
                contexts[name] = scrub_value(block)

    for span in event.get("spans") or []:
        if isinstance(span.get("description"), str):
            span["description"] = scrub_text(strip_query(span["description"]))
        if isinstance(span.get("data"), dict):
            span["data"] = scrub_value(_scrub_url_fields(dict(span["data"])))

    tags = event.setdefault("tags", {})
    if isinstance(tags, dict):
        for key, value in _context_tags().items():
            tags.setdefault(key, value)
    return event
