"""Digest unsubscribe tokens (FR-NOT-04, T8.7): only the server can make one, each names one
member of one workspace, and rotating TOKEN_ENCRYPTION_KEYS keeps old links working until the old
key is removed."""

from __future__ import annotations

import base64
import uuid

import pytest

from socialhood.notify.unsubscribe import UnsubscribeClaim, make_token, read_token
from socialhood.security.crypto import new_key
from socialhood.settings import ConfigurationError

OLD, NEW = new_key(), new_key()
WORKSPACE, USER = uuid.uuid4(), uuid.uuid4()


def test_a_token_reads_back_as_its_member_and_workspace() -> None:
    token = make_token(WORKSPACE, USER, [NEW])
    assert read_token(token, [NEW]) == UnsubscribeClaim(workspace_id=WORKSPACE, user_id=USER)
    assert len(token) == 66
    assert token.replace("-", "").replace("_", "").isalnum()  # safe in a URL as it is


def test_rotation_keeps_old_links_until_the_old_key_is_removed() -> None:
    old_link = make_token(WORKSPACE, USER, [OLD])
    assert read_token(old_link, [NEW, OLD]) is not None
    assert read_token(make_token(WORKSPACE, USER, [NEW, OLD]), [NEW]) is not None  # newest signs
    assert read_token(old_link, [NEW]) is None


def test_a_changed_or_foreign_token_reads_as_nothing() -> None:
    token = make_token(WORKSPACE, USER, [NEW])
    raw = bytearray(base64.urlsafe_b64decode(token + "=="))
    raw[20] ^= 1  # another user id, same MAC
    tampered = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()
    assert read_token(tampered, [NEW]) is None
    assert read_token(token, [OLD]) is None  # signed by a key this server doesn't have
    for garbage in ("", "x", token[:-2], token + "AA", "!" * 66, "A" * 500):
        assert read_token(garbage, [NEW]) is None
    raw = bytearray(base64.urlsafe_b64decode(token + "=="))
    raw[0] = 2  # an unknown version
    assert read_token(base64.urlsafe_b64encode(bytes(raw)).decode(), [NEW]) is None


def test_a_token_is_not_made_without_a_key() -> None:
    with pytest.raises(ConfigurationError):
        make_token(WORKSPACE, USER, [])
    with pytest.raises(ConfigurationError):
        make_token(WORKSPACE, USER, ["not a fernet key"])
    assert read_token(make_token(WORKSPACE, USER, [NEW]), ["not a fernet key", NEW]) is not None
