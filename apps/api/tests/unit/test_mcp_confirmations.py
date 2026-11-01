"""C-169: the confirmation token (mcp/confirmations.py): what it is bound to, expiry, and key
rotation, without a database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel

from socialhood.errors import ApiError
from socialhood.mcp import confirmations

OLD_KEY, NEW_KEY = Fernet.generate_key().decode(), Fernet.generate_key().decode()
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
WORKSPACE, CREDENTIAL = uuid.uuid4(), uuid.uuid4()


class Args(BaseModel):
    name: str = "A"
    turn_on: bool = False
    confirmed: bool = False
    confirmation_token: str | None = None
    idempotency_key: str | None = None


def call(**values: Any) -> Any:
    return SimpleNamespace(
        tool_name=values.get("tool", "create_automation"),
        workspace=SimpleNamespace(id=values.get("workspace", WORKSPACE)),
        principal=SimpleNamespace(credential_id=values.get("credential", CREDENTIAL)),
        settings=SimpleNamespace(token_encryption_keys=values.get("keys", [NEW_KEY])),
        now=values.get("now", NOW),
    )


def refused(the_call: Any, args: BaseModel, token: str | None, **resolved: object) -> str:
    with pytest.raises(ApiError) as caught:
        confirmations.require(the_call, args, token, **resolved)
    assert caught.value.code == "validation_error"
    assert caught.value.errors[0].field == "confirmation_token"
    return str(caught.value.detail)


def test_a_token_opens_exactly_what_was_previewed() -> None:
    token = confirmations.issue(call(), Args(), post="p1")
    confirmations.require(call(), Args(), token, post="p1")
    # What says it's confirmed, and the retry key, aren't part of what is confirmed.
    retry = "retry-0001"
    same = Args(confirmed=True, confirmation_token=token, idempotency_key=retry)
    confirmations.require(call(), same, token, post="p1")


@pytest.mark.parametrize(
    "the_call",
    [
        call(tool="update_automation"),
        call(workspace=uuid.uuid4()),
        call(credential=uuid.uuid4()),
        call(keys=[OLD_KEY]),
    ],
)
def test_another_tool_workspace_credential_or_key_is_refused(the_call: Any) -> None:
    token = confirmations.issue(call(), Args())
    assert "isn't for this change" in refused(the_call, Args(), token)


def test_changed_arguments_or_what_they_resolved_to_are_refused() -> None:
    token = confirmations.issue(call(), Args(), post="p1")
    refused(call(), Args(name="B"), token, post="p1")
    refused(call(), Args(turn_on=True), token, post="p1")
    refused(call(), Args(), token, post="p2")


def test_it_expires_after_about_15_minutes() -> None:
    token = confirmations.issue(call(), Args())
    confirmations.require(call(now=NOW + timedelta(minutes=14)), Args(), token)
    assert "expired" in refused(call(now=NOW + timedelta(minutes=15)), Args(), token)


def test_the_expiry_can_t_be_moved() -> None:
    token = confirmations.issue(call(), Args())
    expiry, _, mac = token.partition(".")
    assert "isn't for this change" in refused(call(), Args(), f"{int(expiry) + 900}.{mac}")


@pytest.mark.parametrize(
    "token", ["x", ".", "1.", ".abc", "abc.def", "-1.abc", "٣.abc", "1.é", "9" * 50 + ".abc"]
)
def test_a_malformed_token_is_a_refusal_not_a_crash(token: str) -> None:
    refused(call(), Args(), token)


def test_no_token_says_to_preview_first() -> None:
    message = refused(call(), Args(), None)
    assert "preview first" in message
    assert "Nothing was changed" in message
    assert "show it to the member" in message


def test_a_rotated_key_still_verifies_a_live_preview() -> None:
    token = confirmations.issue(call(keys=[OLD_KEY]), Args())
    confirmations.require(call(keys=[NEW_KEY, OLD_KEY]), Args(), token)
