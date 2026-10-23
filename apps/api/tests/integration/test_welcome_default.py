"""GR-12 at runtime: the welcome (first_message) answers a contact's first DM to the account, once;
the default reply answers a DM nothing else matched, only while AI is off for the conversation.
Both go through the DM runtime (cooldowns, run records), and neither answers a keyword match, a
story or a tap."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.services.automations.runtime import Outcome
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

FAN = "igsid_welcome_fan"
REPLY = "A person will reply soon."


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


async def ai_mode(world: World, mode: str) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET ai_mode = :m WHERE id = :a"),
            {"m": mode, "a": world.account_id},
        )


async def override(world: World, mode: str) -> None:
    """The conversation's own AI mode (every conversation of the test)."""
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE conversations SET ai_mode_override = :m"), {"m": mode})


async def fallback(world: World, trigger: str, text_: str) -> uuid.UUID:
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=(),
        trigger=trigger,
        name=trigger,
        message_text=text_,
    )


async def price_keyword(world: World) -> uuid.UUID:
    return await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, keywords=("price",)
    )


async def runs_of(world: World, automation_id: uuid.UUID) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM automation_runs WHERE automation_id = :a ORDER BY created_at",
        a=automation_id,
    )


# ---------------------------------------------------------------- the welcome


async def test_a_new_contact_gets_the_welcome_once(world: World) -> None:
    welcome = await fallback(world, "first_message", "Welcome, {first_name|friend}!")
    first = await world.dm(FAN, "hello")
    second = await world.dm(FAN, "anyone there?")
    assert first is not None
    assert second is not None

    assert await world.run("dm", first) is Outcome.FIRED
    assert await world.run("dm", second) is Outcome.NO_MATCH

    [run] = await runs_of(world, welcome)
    assert (run["result"], run["matched_keyword"], run["trigger_message_id"]) == ("sent", "", first)
    [dm] = await world.rows("SELECT * FROM messages WHERE direction = 'outbound'")
    assert dm["source"] == "automation"


async def test_a_contact_who_wrote_before_the_automation_existed_is_not_welcomed(
    world: World,
) -> None:
    """The check reads history, not the feature's launch: an earlier DM is enough."""
    old = await world.dm(FAN, "an old message", at=datetime.now(UTC) - timedelta(days=30))
    assert old is not None
    welcome = await fallback(world, "first_message", "Welcome!")
    new = await world.dm(FAN, "back again")
    assert new is not None

    assert await world.run("dm", new) is Outcome.NO_MATCH
    assert await runs_of(world, welcome) == []


async def test_a_contact_who_only_commented_gets_the_welcome_on_their_first_dm(
    world: World,
) -> None:
    welcome = await fallback(world, "first_message", "Welcome!")
    assert await world.comment("love this", author=FAN) is not None
    dm = await world.dm(FAN, "hi")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.FIRED
    assert len(await runs_of(world, welcome)) == 1


async def test_another_contact_is_welcomed_too(world: World) -> None:
    welcome = await fallback(world, "first_message", "Welcome!")
    one = await world.dm("igsid_one", "hi")
    two = await world.dm("igsid_two", "hello")
    assert one is not None
    assert two is not None

    assert await world.run("dm", one) is Outcome.FIRED
    assert await world.run("dm", two) is Outcome.FIRED
    assert len(await runs_of(world, welcome)) == 2


async def test_a_keyword_automation_beats_the_welcome_on_the_first_dm(world: World) -> None:
    welcome = await fallback(world, "first_message", "Welcome!")
    keyword = await price_keyword(world)
    dm = await world.dm(FAN, "What is the price?")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.FIRED
    assert len(await runs_of(world, keyword)) == 1
    assert await runs_of(world, welcome) == []


async def test_the_welcome_answers_when_the_keyword_did_not_match(world: World) -> None:
    welcome = await fallback(world, "first_message", "Welcome!")
    await price_keyword(world)
    dm = await world.dm(FAN, "hello")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.FIRED
    assert len(await runs_of(world, welcome)) == 1


async def test_a_story_reply_or_mention_is_not_a_welcome(world: World) -> None:
    welcome = await fallback(world, "first_message", "Welcome!")
    reply = await world.story(FAN, text_="Where is this from?")
    mention = await world.story("igsid_mentioner", kind="story_mention", text_=None)
    assert reply is not None
    assert mention is not None

    assert await world.run("dm", reply) is Outcome.NO_MATCH
    assert await world.run("dm", mention) is Outcome.NO_MATCH
    assert await runs_of(world, welcome) == []


async def test_a_tapped_button_is_not_a_welcome(world: World) -> None:
    welcome = await fallback(world, "first_message", "Welcome!")
    tap = await world.dm(FAN, "Tell me more", payload="SOME_PAYLOAD")
    assert tap is not None

    assert await world.run("dm", tap) is Outcome.NO_MATCH
    assert await runs_of(world, welcome) == []


# ---------------------------------------------------------------- the default reply


async def test_an_unmatched_dm_gets_the_default_reply_while_ai_is_off(world: World) -> None:
    await ai_mode(world, "off")
    default = await fallback(world, "default_reply", REPLY)
    dm = await world.dm(FAN, "random question")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.FIRED
    [run] = await runs_of(world, default)
    assert (run["result"], run["matched_keyword"]) == ("sent", "")


@pytest.mark.parametrize("mode", ["suggest", "auto"])
async def test_no_default_reply_while_the_ai_is_on(world: World, mode: str) -> None:
    await ai_mode(world, mode)
    default = await fallback(world, "default_reply", REPLY)
    dm = await world.dm(FAN, "random question")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.NO_MATCH
    assert await runs_of(world, default) == []


async def test_the_conversations_ai_mode_overrides_the_accounts(world: World) -> None:
    await ai_mode(world, "suggest")
    default = await fallback(world, "default_reply", REPLY)
    dm = await world.dm(FAN, "random question")
    assert dm is not None
    await override(world, "off")

    assert await world.run("dm", dm) is Outcome.FIRED
    assert len(await runs_of(world, default)) == 1


async def test_an_override_that_turns_ai_on_blocks_the_default_reply(world: World) -> None:
    await ai_mode(world, "off")
    default = await fallback(world, "default_reply", REPLY)
    dm = await world.dm(FAN, "random question")
    assert dm is not None
    await override(world, "suggest")

    assert await world.run("dm", dm) is Outcome.NO_MATCH
    assert await runs_of(world, default) == []


async def test_no_default_reply_when_a_keyword_matched(world: World) -> None:
    await ai_mode(world, "off")
    default = await fallback(world, "default_reply", REPLY)
    keyword = await price_keyword(world)
    dm = await world.dm(FAN, "price?")
    assert dm is not None

    assert await world.run("dm", dm) is Outcome.FIRED
    assert len(await runs_of(world, keyword)) == 1
    assert await runs_of(world, default) == []


async def test_a_keyword_match_on_cooldown_gets_no_default_reply(world: World) -> None:
    await ai_mode(world, "off")
    default = await fallback(world, "default_reply", REPLY)
    await price_keyword(world)
    first = await world.dm(FAN, "price?")
    again = await world.dm(FAN, "price again?")
    assert first is not None
    assert again is not None

    assert await world.run("dm", first) is Outcome.FIRED
    assert await world.run("dm", again) is Outcome.SKIPPED
    assert await runs_of(world, default) == []


async def test_a_story_reply_and_a_tap_get_no_default_reply(world: World) -> None:
    await ai_mode(world, "off")
    default = await fallback(world, "default_reply", REPLY)
    reply = await world.story(FAN, text_="Where is this from?")
    tap = await world.dm("igsid_tapper", "Tell me more", payload="SOME_PAYLOAD")
    assert reply is not None
    assert tap is not None

    assert await world.run("dm", reply) is Outcome.NO_MATCH
    assert await world.run("dm", tap) is Outcome.NO_MATCH
    assert await runs_of(world, default) == []


async def test_the_default_reply_obeys_its_cooldown(world: World) -> None:
    await ai_mode(world, "off")
    default = await fallback(world, "default_reply", REPLY)
    first = await world.dm(FAN, "one")
    second = await world.dm(FAN, "two")
    assert first is not None
    assert second is not None

    assert await world.run("dm", first) is Outcome.FIRED
    assert await world.run("dm", second) is Outcome.SKIPPED
    results = [r["result"] for r in await runs_of(world, default)]
    assert sorted(results) == ["sent", "skipped_cooldown"]


async def test_the_welcome_answers_and_the_default_reply_stays_quiet(world: World) -> None:
    await ai_mode(world, "off")
    welcome = await fallback(world, "first_message", "Welcome!")
    default = await fallback(world, "default_reply", REPLY)
    first = await world.dm(FAN, "hello")
    later = await world.dm(FAN, "another question", at=datetime.now(UTC) + timedelta(minutes=1))
    assert first is not None
    assert later is not None

    assert await world.run("dm", first) is Outcome.FIRED
    assert len(await runs_of(world, welcome)) == 1
    assert await runs_of(world, default) == []

    # The next DM is not a first message, so the default reply answers it.
    assert await world.run("dm", later) is Outcome.FIRED
    assert len(await runs_of(world, default)) == 1
