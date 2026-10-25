"""GR-28: visitor secrets and session tokens. Only the server can make a token, it names one
widget, workspace, visitor and site, it expires, and rotating the keys keeps live ones working."""

from __future__ import annotations

import uuid

import pytest

from socialhood.security import widget_tokens as tokens
from socialhood.security.crypto import new_key
from socialhood.settings import ConfigurationError

OLD, NEW = new_key(), new_key()
ACCOUNT, WORKSPACE = uuid.uuid4(), uuid.uuid4()
NOW = 1_800_000_000.0


def issue(keys: list[str], *, visitor: str = "v_abc", host: str = "example.com") -> str:
    token, _ = tokens.issue(
        account_id=ACCOUNT, workspace_id=WORKSPACE, visitor=visitor, host=host, keys=keys, now=NOW
    )
    return token


def test_a_token_reads_back_as_its_claim() -> None:
    claim = tokens.read_token(issue([NEW]), [NEW], now=NOW + 60)
    assert claim == tokens.VisitorClaim(
        ACCOUNT, WORKSPACE, "v_abc", "example.com", int(NOW + tokens.TOKEN_TTL_S)
    )


def test_a_token_expires() -> None:
    token = issue([NEW])
    assert tokens.read_token(token, [NEW], now=NOW + tokens.TOKEN_TTL_S - 1) is not None
    assert tokens.read_token(token, [NEW], now=NOW + tokens.TOKEN_TTL_S) is None


def test_rotation_keeps_old_tokens_until_the_old_key_is_removed() -> None:
    old = issue([OLD])
    assert tokens.read_token(old, [NEW, OLD], now=NOW) is not None
    assert tokens.read_token(issue([NEW, OLD]), [NEW], now=NOW) is not None  # the newest signs
    assert tokens.read_token(old, [NEW], now=NOW) is None


def test_a_changed_or_foreign_token_reads_as_nothing() -> None:
    token = issue([NEW])
    body, _, mac = token.partition(".")
    swapped = issue([NEW], visitor="v_other").partition(".")[0]
    assert tokens.read_token(f"{swapped}.{mac}", [NEW], now=NOW) is None  # another claim, same MAC
    assert tokens.read_token(f"{body}.{mac[:-2]}AA", [NEW], now=NOW) is None
    assert tokens.read_token(token, [OLD], now=NOW) is None
    for junk in ("", "x", "a.b.c", "...", "!!!.???", "a" * 800):
        assert tokens.read_token(junk, [NEW], now=NOW) is None


@pytest.mark.parametrize("keys", [[], ["not-a-key"]])
def test_signing_needs_a_usable_key(keys: list[str]) -> None:
    with pytest.raises(ConfigurationError):
        issue(keys)


def test_a_visitor_id_hides_the_secret_it_comes_from() -> None:
    secret = tokens.new_secret()
    visitor = tokens.visitor_id(secret)
    assert tokens.valid_secret(secret)
    assert visitor.startswith("v_")
    assert len(visitor) == 26
    assert secret not in visitor
    assert tokens.visitor_id(secret) == visitor
    assert tokens.visitor_id(tokens.new_secret()) != visitor


def test_only_well_formed_secrets_are_accepted() -> None:
    assert not tokens.valid_secret("short")
    assert not tokens.valid_secret("x" * 101)
    assert not tokens.valid_secret("has spaces in it and more " * 2)
    assert not tokens.valid_secret("é" * 30)
    assert tokens.valid_secret("A" * 20)
