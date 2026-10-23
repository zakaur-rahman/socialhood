"""GR-11: conversation starters (pure: no database): the payload a tap carries, which triggers a
tap can start, how Instagram's profile is read, and the sandbox adapter that keeps what was set."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from socialhood.platforms.base import IceBreaker
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram.profile import parse_ice_breakers
from socialhood.platforms.sandbox import outbox
from socialhood.platforms.sandbox.adapter import SandboxAdapter
from socialhood.services import ice_breakers
from socialhood.services.automations import matching, runtime


def tap(payload: str | None, **values: Any) -> Any:
    return SimpleNamespace(
        kind="text", text="Hours?", attachments=[], postback_payload=payload, **values
    )


def test_a_payload_names_a_starter_only_in_our_format() -> None:
    starter_id = uuid.uuid4()
    assert ice_breakers.payload_id(f"ib:{starter_id}") == starter_id
    for other in (None, "", "HOURS", "ib:", "ib:not-a-uuid", f"shr:{starter_id}"):
        assert ice_breakers.payload_id(other) is None
    assert not ice_breakers.is_tap("HOURS")


def test_a_tapped_starter_starts_ice_breaker_automations_only() -> None:
    assert runtime.dm_triggers(tap(f"ib:{uuid.uuid4()}")) == ("ice_breaker",)
    assert runtime.dm_triggers(tap("OTHER_BUTTON")) == ("dm_keyword",)
    assert runtime.dm_triggers(tap(None)) == ("dm_keyword",)


def test_an_ice_breaker_automation_answers_without_keywords() -> None:
    candidate = matching.Candidate(
        id=uuid.uuid4(),
        trigger="ice_breaker",
        match_mode="word",
        keywords=(),
        priority=100,
        created_at=datetime.now(UTC),
    )
    assert matching.matches_anything(candidate)
    assert [m.automation_id for m in matching.matches("Opening hours?", [candidate])] == [
        candidate.id
    ]


def test_the_default_locale_starters_are_read_from_the_profile() -> None:
    body = {
        "data": [
            {
                "ice_breakers": [
                    {
                        "locale": "default",
                        "call_to_actions": [
                            {"question": "Hours?", "payload": "ib:1"},
                            {"question": "Ship abroad?", "payload": "ib:2"},
                        ],
                    },
                    {
                        "locale": "fr_FR",
                        "call_to_actions": [{"question": "Horaires ?", "payload": "ib:3"}],
                    },
                ]
            }
        ]
    }
    assert parse_ice_breakers(body) == [
        IceBreaker("Hours?", "ib:1"),
        IceBreaker("Ship abroad?", "ib:2"),
    ]
    assert parse_ice_breakers({"data": []}) == []
    assert parse_ice_breakers(None) == []


@pytest.fixture(autouse=True)
def _clean_outbox() -> Any:
    outbox.reset()
    yield
    outbox.reset()


async def test_the_sandbox_shows_what_was_synced_and_can_fail() -> None:
    adapter: Any = SandboxAdapter.__new__(SandboxAdapter)
    acct: Any = SimpleNamespace(platform="instagram", platform_account_id="sandbox_ref")
    starters = [IceBreaker("Hours?", "ib:1")]
    assert await adapter.set_ice_breakers(acct, starters) == starters
    assert outbox.ICE_BREAKERS["sandbox_ref"] == starters
    assert await adapter.set_ice_breakers(acct, []) == []
    assert outbox.ICE_BREAKERS["sandbox_ref"] == []

    with pytest.raises(PlatformError) as caught:
        await adapter.set_ice_breakers(
            acct, [IceBreaker("Where? [sandbox:fail=platform_rejected]", "ib:2")]
        )
    assert caught.value.code == "platform_rejected"
