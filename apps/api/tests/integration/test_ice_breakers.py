"""GR-11 at runtime: conversation starters are saved and pushed to the platform (the sandbox keeps
what was set), a failed push keeps the list and says why, and a tap (a postback carrying the
starter's payload) starts the mapped automation, or leaves the message to the inbox AI."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.platforms.base import IceBreaker
from socialhood.platforms.events import InboundMessage
from socialhood.platforms.sandbox import outbox
from socialhood.repositories import social_accounts as accounts
from socialhood.services import ice_breakers
from socialhood.services.automations.runtime import Outcome
from socialhood.services.ingest import ingest
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

CUSTOMER = "igsid_starter_fan"


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


async def starter_automation(world: World, **values: Any) -> uuid.UUID:
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=(),
        trigger="ice_breaker",
        name=values.pop("name", "Opening hours"),
        message_text="We are open 9 to 6.",
        **values,
    )


async def save(world: World, items: list[ice_breakers.StarterIn]) -> tuple[list[Any], str | None]:
    with workspace_scope(world.wid):
        async with world.maker() as session:
            acct = await accounts.get(session, world.account_id)
            assert acct is not None
            rows, error = await ice_breakers.save(session, acct, items, deps=world.deps)
            await session.commit()
            return list(rows), error


async def tap(world: World, payload: str, text_: str = "Opening hours?") -> uuid.UUID | None:
    event = InboundMessage(
        account_ref="sandbox",
        occurred_at=datetime.now(UTC),
        contact_ref=CUSTOMER,
        contact_name=None,
        platform_message_id=f"mid_{uuid.uuid4().hex}",
        kind="text",
        text=text_,
        postback_payload=payload,
    )
    with workspace_scope(world.wid):
        async with world.maker() as session:
            acct = await accounts.get(session, world.account_id)
            assert acct is not None
            result = await ingest(session, acct, [event])
            await session.commit()
    return result.created_message_ids[0] if result.created_message_ids else None


async def test_saved_starters_are_pushed_and_a_tap_starts_the_mapped_automation(
    world: World,
) -> None:
    automation_id = await starter_automation(world)

    rows, error = await save(
        world,
        [
            ice_breakers.StarterIn("Opening hours?", automation_id=automation_id),
            ice_breakers.StarterIn("Can I talk to someone?", answer_with_ai=True),
        ],
    )

    assert error is None
    assert all(r.synced_at is not None and r.sync_error is None for r in rows)
    [ref] = await world.rows("SELECT platform_account_id FROM social_accounts")
    assert outbox.ICE_BREAKERS[ref["platform_account_id"]] == [
        IceBreaker("Opening hours?", f"ib:{rows[0].id}"),
        IceBreaker("Can I talk to someone?", f"ib:{rows[1].id}"),
    ]

    message_id = await tap(world, f"ib:{rows[0].id}")
    assert message_id is not None
    assert await world.run("dm", message_id) is Outcome.FIRED
    run = await world.run_row()
    assert (run["automation_id"], run["result"]) == (automation_id, "sent")
    [conv] = await world.rows("SELECT entry_source, entry_ref FROM conversations")
    assert (conv["entry_source"], conv["entry_ref"]) == ("ice_breaker", "Opening hours?")


async def test_a_starter_answered_by_ai_starts_no_automation(world: World) -> None:
    await starter_automation(world)
    rows, _ = await save(
        world, [ice_breakers.StarterIn("Can I talk to someone?", answer_with_ai=True)]
    )

    message_id = await tap(world, f"ib:{rows[0].id}")
    assert message_id is not None

    assert await world.run("dm", message_id) is Outcome.NO_MATCH
    assert await world.rows("SELECT id FROM automation_runs") == []
    [stored] = await world.rows(
        "SELECT automation_handled FROM messages WHERE id = :id", id=message_id
    )
    assert stored["automation_handled"] is False  # the inbox AI answers it


async def test_a_payload_that_is_not_ours_does_not_start_an_ice_breaker(world: World) -> None:
    await starter_automation(world)
    message_id = await tap(world, "HOURS")
    assert message_id is not None
    # Not a starter: DM keyword automations are looked at (there are none), the ice breaker is not.
    assert await world.run("dm", message_id) is Outcome.NO_MATCH


async def test_a_failed_push_keeps_the_list_and_says_why(world: World) -> None:
    rows, error = await save(
        world,
        [ice_breakers.StarterIn("Where? [sandbox:fail=platform_rejected]", answer_with_ai=True)],
    )

    assert error
    assert len(rows) == 1
    assert rows[0].sync_error == error
    assert rows[0].synced_at is None


async def test_saving_replaces_the_list_and_keeps_a_position_id(world: World) -> None:
    first, _ = await save(world, [ice_breakers.StarterIn("One?", answer_with_ai=True)] * 1)
    again, _ = await save(
        world,
        [
            ice_breakers.StarterIn("One, reworded?", answer_with_ai=True),
            ice_breakers.StarterIn("Two?", answer_with_ai=True),
        ],
    )
    assert again[0].id == first[0].id
    kept, _ = await save(world, [ice_breakers.StarterIn("One, reworded?", answer_with_ai=True)])
    assert [r.question for r in kept] == ["One, reworded?"]
    assert len(await world.rows("SELECT id FROM ice_breakers")) == 1


async def test_a_starter_needs_one_target_and_a_matching_automation(world: World) -> None:
    other_trigger = await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id
    )
    bad: list[list[ice_breakers.StarterIn]] = [
        [ice_breakers.StarterIn("No target?")],
        [ice_breakers.StarterIn("Both?", automation_id=uuid.uuid4(), answer_with_ai=True)],
        [ice_breakers.StarterIn("Wrong trigger?", automation_id=other_trigger)],
        [ice_breakers.StarterIn("")],
        [ice_breakers.StarterIn("x" * 81, answer_with_ai=True)],
        [ice_breakers.StarterIn(f"Q{i}?", answer_with_ai=True) for i in range(5)],
    ]
    for items in bad:
        with pytest.raises(ApiError) as caught:
            await save(world, items)
        assert caught.value.code == "validation_error"
