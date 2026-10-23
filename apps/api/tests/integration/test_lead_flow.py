"""GR-18: leads in the flow engine. The lead stage is a branch condition, and an email captured
by a question qualifies a new lead (with its history row and a lead.stage_changed event)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.services.automations.runtime import Outcome
from socialhood.settings import Settings
from tests.integration.test_flow_runs import outbound, ref, send, started, with_flow
from tests.integration.test_outbound_webhooks import add_endpoint, pending
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


def branch_on_stage() -> dict[str, Any]:
    return {
        "start": "check",
        "steps": [
            {
                "type": "branch",
                "id": "check",
                "rules": [
                    {
                        "when": {"kind": "lead_stage", "stages": ["qualified", "follow_up"]},
                        "next": "warm",
                    }
                ],
                "otherwise": "cold",
            },
            send("warm", "Welcome back!"),
            send("cold", "Nice to meet you."),
        ],
    }


async def fire(world: World, author: str, stage: str | None) -> str:
    """A "link" DM from ``author`` runs the flow with the contact in ``stage``."""
    dm = await world.dm(author, "link please")
    assert dm is not None
    if stage is not None:
        async with world.engine.begin() as conn:  # the DM created the contact
            await conn.execute(
                text("UPDATE contacts SET lead_stage = :s WHERE platform_user_id = :r"),
                {"s": stage, "r": author},
            )
    assert await world.run("dm", dm) is Outcome.FIRED
    return str((await outbound(world))[-1]["text"])


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (None, "Nice to meet you."),  # a new lead
        ("qualified", "Welcome back!"),
        ("follow_up", "Welcome back!"),
        ("won", "Nice to meet you."),
        ("lost", "Nice to meet you."),
    ],
)
async def test_a_branch_on_the_lead_stage(world: World, stage: str | None, expected: str) -> None:
    await with_flow(world, branch_on_stage())
    assert await fire(world, ref(), stage) == expected


async def test_a_captured_email_qualifies_a_new_lead(world: World) -> None:
    await add_endpoint(world, ["lead.stage_changed"])
    await with_flow(
        world,
        {
            "start": "q",
            "steps": [{"type": "ask", "id": "q", "text": "Your email?", "expect": "email"}],
        },
    )
    author = ref()
    run = await started(world, author)
    assert run["flow_state"] == "replying"
    answer = await world.dm(author, "priya@example.com")
    assert answer is not None
    assert await world.run("dm", answer) is Outcome.ANSWERED

    [contact] = await world.rows(
        "SELECT id, lead_stage, lead_stage_reason FROM contacts WHERE platform_user_id = :r",
        r=author,
    )
    assert (contact["lead_stage"], contact["lead_stage_reason"]) == (
        "qualified",
        "They gave their email address.",
    )
    [change] = await world.rows("SELECT * FROM lead_stage_changes")
    assert (change["from_stage"], change["to_stage"], change["actor_kind"], change["rule"]) == (
        "new",
        "qualified",
        "rule",
        "email_captured",
    )
    [event] = await pending(world)
    assert event["event_type"] == "lead.stage_changed"
    data = event["payload"]["data"]
    assert (data["from"], data["to"]) == ("new", "qualified")
    assert data["changed_by"] == {"kind": "rule", "user_id": None, "rule": "email_captured"}
    assert data["contact"]["id"] == str(contact["id"])


async def test_a_captured_email_does_not_pull_a_closed_lead_back(world: World) -> None:
    await with_flow(
        world,
        {
            "start": "q",
            "steps": [{"type": "ask", "id": "q", "text": "Your email?", "expect": "email"}],
        },
    )
    author = ref()
    await started(world, author)
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE contacts SET lead_stage = 'won'"))
    answer = await world.dm(author, "priya@example.com")
    assert answer is not None
    assert await world.run("dm", answer) is Outcome.ANSWERED
    [contact] = await world.rows("SELECT lead_stage FROM contacts")
    assert contact["lead_stage"] == "won"
    assert await world.rows("SELECT 1 FROM lead_stage_changes") == []


async def test_a_phone_does_not_qualify(world: World) -> None:
    await with_flow(
        world,
        {
            "start": "q",
            "steps": [{"type": "ask", "id": "q", "text": "Your phone?", "expect": "phone"}],
        },
    )
    author = ref()
    await started(world, author)
    answer = await world.dm(author, "+919876543210")
    assert answer is not None
    assert await world.run("dm", answer) is Outcome.ANSWERED
    [contact] = await world.rows("SELECT lead_stage, phone FROM contacts")
    assert (contact["lead_stage"], contact["phone"]) == ("new", "+919876543210")
