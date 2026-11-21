from __future__ import annotations

import ast
from pathlib import Path

import socialhood
from socialhood.observability.logging import REDACTED, TEXT_LIMIT, RedactProcessor, is_secret_key

LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


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


def test_emails_and_phone_numbers_are_masked() -> None:
    out = run(
        {
            "event": "send_failed",
            "detail": "No user priya@example.com at +91 98765 43210",
            "text": "Reach me on priya.sharma@example.com please, thanks so much",
            "args": ["+14155550100", 17840000000000000],
            "wa_id": "919876543210",
            "phone_number_id": "106540352242922",
        }
    )
    assert out["detail"] == "No user [email] at [phone]"
    assert out["text"] == "Reach me on [email] please, thanks so mu…"
    assert out["args"] == ["[phone]", 17840000000000000]
    assert out["wa_id"] == REDACTED
    assert out["phone_number_id"] == "106540352242922"  # a Meta id, not a number


def test_text_is_kept_at_debug() -> None:
    long = "x" * 100
    assert run({"text": long}, truncate=False)["text"] == long


def test_no_log_call_names_a_diagnostic_code_field_the_redaction_blanks() -> None:
    """A field named ``code`` (or ``*_code`` outside the safe list) is blanked as a possible
    OAuth code, so an error code logged under it is lost: log it as ``error_code``."""
    root = Path(socialhood.__file__).parent
    blanked = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr not in LOG_METHODS or not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id != "log":
                continue
            blanked += [
                f"{path.relative_to(root)}:{kw.value.lineno} {kw.arg}"
                for kw in node.keywords
                if kw.arg and kw.arg.lower().endswith("code") and is_secret_key(kw.arg)
            ]
    assert blanked == []
