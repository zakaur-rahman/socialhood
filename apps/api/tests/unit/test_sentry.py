"""T9.3, SEC-12: Sentry stays off without a DSN, and what it sends carries no PII or secrets."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import sentry_sdk
import structlog
from fastapi import FastAPI
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from socialhood.api.middleware import RequestContextMiddleware
from socialhood.observability import sentry as observability_sentry
from socialhood.observability.http import MetricsMiddleware
from socialhood.observability.logging import configure_logging, get_logger
from socialhood.observability.sentry import (
    init_sentry,
    reset_for_tests,
    scrub_breadcrumb,
    scrub_event,
    scrub_text,
)
from socialhood.settings import AppEnv, Settings

DSN = "https://public@o0.ingest.sentry.io/0"
IG_TOKEN = "IGQWRPa1ZAabcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"


def fake_jwt() -> str:
    """A JWT-shaped string built at runtime, so the secret scanner has nothing to flag."""

    def part(value: dict[str, str]) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    return f"{part({'alg': 'RS256'})}.{part({'sub': 'user_123'})}.c2lnbmF0dXJl"


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "_env_file": None,
        "app_env": AppEnv.STAGING,
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "database_url_direct": "postgresql://u:p@localhost/db",
        "redis_url": "redis://localhost:6379/3",
    }
    return Settings(**{**base, **overrides})


class Capture(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        for item in envelope.items:
            if item.type in ("event", "transaction") and item.payload.json is not None:
                self.events.append(item.payload.json)


@pytest.fixture
def sentry() -> Iterator[Capture]:
    transport = Capture()
    assert init_sentry(make_settings(sentry_dsn=DSN), component="api", transport=transport)
    yield transport
    reset_for_tests()


def test_no_dsn_means_no_sentry() -> None:
    reset_for_tests()
    assert init_sentry(make_settings(), component="api") is False
    assert not sentry_sdk.get_client().is_active()


def test_environment_release_and_sample_rate_come_from_settings() -> None:
    transport = Capture()
    settings = make_settings(
        sentry_dsn=DSN, sentry_release="abc123", sentry_traces_sample_rate=0.25
    )
    try:
        init_sentry(settings, component="worker", transport=transport)
        options = sentry_sdk.get_client().options
        assert (options["environment"], options["release"]) == ("staging", "abc123")
        assert options["traces_sample_rate"] == 0.25
        assert options["send_default_pii"] is False
        assert options["include_local_variables"] is False
        sentry_sdk.capture_message("hello")
        assert transport.events[0]["tags"]["component"] == "worker"
    finally:
        reset_for_tests()


def test_render_git_commit_is_the_default_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "deadbeef")
    assert make_settings().sentry_release == "deadbeef"


def test_text_scrubbing_masks_emails_and_credentials() -> None:
    jwt = fake_jwt()
    out = scrub_text(
        f"asha@example.com sent Bearer abc.def token {IG_TOKEN} jwt {jwt} "
        "workspace 5b1f7c1e-2c1b-4c0e-9a57-2f3f4a5b6c7d"
    )
    assert "asha@example.com" not in out
    assert "abc.def" not in out
    assert IG_TOKEN not in out
    assert jwt not in out
    assert "5b1f7c1e-2c1b-4c0e-9a57-2f3f4a5b6c7d" in out  # ids stay readable


def test_events_lose_headers_bodies_queries_user_details_and_text() -> None:
    event: dict[str, Any] = {
        "request": {
            "method": "POST",
            "url": "https://api.test/v1/oauth/instagram/callback?code=abc&state=xyz",
            "query_string": "code=abc&state=xyz",
            "headers": {"Authorization": "Bearer secret", "Cookie": "session=1"},
            "cookies": {"session": "1"},
            "data": {"text": "Do you ship to Pune?"},
            "env": {"REMOTE_ADDR": "203.0.113.9"},
        },
        "user": {"id": "u-1", "email": "asha@example.com", "ip_address": "203.0.113.9"},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "bad reply for asha@example.com",
                    "stacktrace": {"frames": [{"function": "f", "vars": {"text": "hi"}}]},
                }
            ]
        },
        "extra": {
            "log": {
                "text": "Do you ship to Pune?",
                "access_token": IG_TOKEN,
                "status_code": 500,
                "nested": [{"password": "p", "caption": "New drop"}],
            }
        },
        "contexts": {"trace": {"trace_id": "t"}, "job": {"id": 1, "body": "hello"}},
        "breadcrumbs": {
            "values": [
                {
                    "category": "httplib",
                    "data": {
                        "url": "https://graph.instagram.com/access_token?client_secret=s",
                        "http.query": "client_secret=s&access_token=t",
                    },
                }
            ]
        },
    }
    out = scrub_event(event)
    assert out["request"] == {
        "method": "POST",
        "url": "https://api.test/v1/oauth/instagram/callback",
    }
    assert out["user"] == {"id": "u-1"}
    exception = out["exception"]["values"][0]
    assert exception["value"] == "bad reply for [email]"
    assert "vars" not in exception["stacktrace"]["frames"][0]
    assert out["extra"]["log"] == {
        "access_token": "[redacted]",
        "status_code": 500,
        "nested": [{"password": "[redacted]"}],
    }
    assert out["contexts"]["job"] == {"id": 1}
    assert out["contexts"]["trace"] == {"trace_id": "t"}
    crumb = out["breadcrumbs"]["values"][0]["data"]
    assert crumb == {"url": "https://graph.instagram.com/access_token"}


def test_transaction_spans_lose_query_strings() -> None:
    event: dict[str, Any] = {
        "type": "transaction",
        "spans": [
            {
                "description": "GET https://graph.facebook.com/oauth?client_secret=s&code=c",
                "data": {"http.query": "client_secret=s", "url": "https://x.test/a?token=t"},
            }
        ],
    }
    span = scrub_event(event)["spans"][0]
    assert span["description"] == "GET https://graph.facebook.com/oauth"
    assert span["data"] == {"url": "https://x.test/a"}


def test_breadcrumb_messages_are_scrubbed() -> None:
    crumb = scrub_breadcrumb({"message": "GET /x?access_token=abc by asha@example.com"})
    assert crumb["message"] == "GET /x by [email]"


def test_bound_log_ids_become_tags() -> None:
    with structlog.contextvars.bound_contextvars(request_id="01REQ", workspace_id="w-1"):
        tags = scrub_event({})["tags"]
    assert tags == {"request_id": "01REQ", "workspace_id": "w-1"}


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/v1/w/{wid}/boom")
    async def boom(wid: str) -> None:
        raise RuntimeError(f"cannot reply to asha@example.com with {IG_TOKEN}")

    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestContextMiddleware)
    return app


async def test_an_unhandled_api_error_is_captured_without_pii(sentry: Capture) -> None:
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
        response = await client.get(
            "/v1/w/w1/boom?access_token=secret",
            headers={
                "Authorization": "Bearer user-jwt",
                "Cookie": "a=b",
                "X-Request-ID": "req-123456",
            },
        )
    assert response.status_code == 500
    [event] = [e for e in sentry.events if e.get("exception")]
    exception = event["exception"]["values"][-1]
    assert exception["type"] == "RuntimeError"
    assert "asha@example.com" not in exception["value"]
    assert IG_TOKEN not in exception["value"]
    request = event.get("request", {})
    assert set(request) <= {"method", "url"}
    assert "access_token" not in str(event)
    assert "user-jwt" not in str(event)
    assert event["tags"]["request_id"] == "req-123456"
    assert event["tags"]["component"] == "api"


async def test_error_logs_and_alerts_reach_sentry(sentry: Capture) -> None:
    configure_logging("INFO")
    log = get_logger("test")
    log.info("fine")  # not an error: nothing sent
    log.error("alert", kind="webhook_health", detail="instagram webhook failures 3 of 10")
    try:
        raise ValueError("broken for asha@example.com")
    except ValueError:
        log.exception("send_message_unexpected_error", text="Do you ship to Pune?")

    assert len(sentry.events) == 2
    alert, error = sentry.events
    assert alert["message"] == "alert: instagram webhook failures 3 of 10"
    assert alert["tags"]["alert_kind"] == "webhook_health"
    assert error["exception"]["values"][0]["value"] == "broken for [email]"
    assert error["extra"]["log"] == {}  # the message text was dropped


def test_sentry_processor_is_quiet_without_a_client() -> None:
    reset_for_tests()
    processor = observability_sentry.SentryLogProcessor()
    event = {"event": "alert", "kind": "x"}
    assert processor(None, "error", dict(event)) == event
