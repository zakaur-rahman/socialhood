from __future__ import annotations

from socialhood.observability.logging import REDACTED, TEXT_LIMIT, RedactProcessor


def run(event: dict[str, object], *, truncate: bool = True) -> dict[str, object]:
    return dict(RedactProcessor(truncate=truncate)(None, "info", dict(event)))


def test_redaction_removes_token_fields() -> None:
    out = run(
        {
            "event": "oauth_exchange",
            "access_token": "IGQV-secret",
            "headers": {"Authorization": "Bearer abc", "accept": "json"},
            "code": "oauth-code",
            "client_secret": "s",
            "status_code": 200,
            "error_code": "platform_rate_limited",
        }
    )
    assert out["access_token"] == REDACTED
    assert out["headers"] == {"Authorization": REDACTED, "accept": "json"}
    assert out["code"] == REDACTED
    assert out["client_secret"] == REDACTED
    assert out["status_code"] == 200
    assert out["error_code"] == "platform_rate_limited"


def test_redaction_reaches_lists_of_mappings() -> None:
    out = run({"calls": [{"password": "p", "ok": True}]})
    assert out["calls"] == [{"password": REDACTED, "ok": True}]


def test_text_and_body_are_truncated_at_info() -> None:
    long = "x" * 100
    out = run({"text": long, "body": long, "other": long})
    assert out["text"] == "x" * TEXT_LIMIT + "…"
    assert out["body"] == "x" * TEXT_LIMIT + "…"
    assert out["other"] == long


def test_text_is_kept_at_debug() -> None:
    long = "x" * 100
    assert run({"text": long}, truncate=False)["text"] == long
