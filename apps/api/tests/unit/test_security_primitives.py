"""SEC-03 token encryption and TR-WH-02 signature checks."""

from __future__ import annotations

import pytest

from socialhood.security.crypto import TokenCipher, new_key
from socialhood.security.signatures import (
    parse_signed_request,
    sign_request,
    verify_hub_signature,
)
from socialhood.settings import ConfigurationError
from tests.support.instagram import hub_signature


def test_a_token_round_trips_and_is_not_stored_in_clear() -> None:
    cipher = TokenCipher([new_key()])
    blob = cipher.encrypt("IGQVJsecret")
    assert b"IGQVJsecret" not in blob
    assert cipher.decrypt(blob) == "IGQVJsecret"


def test_rotation_keeps_old_tokens_readable_and_moves_them_to_the_new_key() -> None:
    old, new = new_key(), new_key()
    blob = TokenCipher([old]).encrypt("IGQVJsecret")

    rotating = TokenCipher([new, old])  # newest first
    assert rotating.decrypt(blob) == "IGQVJsecret"
    rotated = rotating.rotate(blob)

    assert TokenCipher([new]).decrypt(rotated) == "IGQVJsecret"
    with pytest.raises(ValueError, match="cannot be decrypted"):
        TokenCipher([old]).decrypt(rotated)


def test_a_missing_or_malformed_key_fails_at_startup() -> None:
    with pytest.raises(ConfigurationError, match="empty"):
        TokenCipher([])
    with pytest.raises(ConfigurationError, match="invalid Fernet key"):
        TokenCipher(["not-a-key"])


@pytest.mark.parametrize(
    ("header", "ok"),
    [
        (hub_signature(b'{"a":1}', "s3cret"), True),
        (hub_signature(b'{"a":2}', "s3cret"), False),  # different body
        (hub_signature(b'{"a":1}', "other"), False),  # different secret
        ("sha1=" + "0" * 40, False),
        ("", False),
        (None, False),
    ],
)
def test_hub_signature(header: str | None, ok: bool) -> None:
    assert verify_hub_signature(b'{"a":1}', header, "s3cret") is ok


def test_hub_signature_needs_a_secret() -> None:
    assert verify_hub_signature(b"x", hub_signature(b"x", ""), "") is False


def test_signed_request_verifies_with_any_configured_secret() -> None:
    payload = {"algorithm": "HMAC-SHA256", "user_id": "26000000000000001", "issued_at": 1}
    signed = sign_request(payload, "meta-secret")
    assert parse_signed_request(signed, ["ig-secret", "meta-secret"]) == payload
    assert parse_signed_request(signed, ["ig-secret"]) is None


@pytest.mark.parametrize(
    "value",
    [None, "", "no-dot", "!!!.???", sign_request({"user_id": "1"}, "s")[:-2] + "xx"],
)
def test_signed_request_rejects_garbage(value: str | None) -> None:
    assert parse_signed_request(value, ["s"]) is None


def test_signed_request_rejects_another_algorithm() -> None:
    signed = sign_request({"algorithm": "none", "user_id": "1"}, "s")
    assert parse_signed_request(signed, ["s"]) is None
