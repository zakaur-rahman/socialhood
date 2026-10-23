"""GR-08 and GR-09 at runtime: a referral with a known ref (then the first DM) starts the entry
link's automation, an ad referral starts the ad click automation, and neither starts twice."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.events import ReferralInfo
from socialhood.services.automations.runtime import Outcome
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

CUSTOMER = "igsid_link_fan"


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


async def link(world: World, code: str, automation_id: uuid.UUID | None) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO entry_links (workspace_id, social_account_id, automation_id, code,"
                " name) VALUES (:w, :a, :auto, :code, :code)"
            ),
            {"w": world.wid, "a": world.account_id, "auto": automation_id, "code": code},
        )


async def entry_automation(world: World, **values: Any) -> uuid.UUID:
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=(),
        trigger=values.pop("trigger", "entry_link"),
        name=values.pop("name", "Welcome"),
        message_text="Welcome, {first_name}!",
        **values,
    )


async def test_opening_a_link_then_a_dm_starts_the_links_automation(world: World) -> None:
    automation_id = await entry_automation(world)
    await link(world, "spring", automation_id)
    await world.referral(CUSTOMER, ref="spring")
    first = await world.dm(CUSTOMER, "hi!")
    assert first is not None

    assert await world.run("dm", first) is Outcome.FIRED
    run = await world.run_row()
    assert (run["automation_id"], run["result"], run["matched_keyword"]) == (
        automation_id,
        "sent",
        "",
    )
    conversation = (await world.rows("SELECT * FROM conversations"))[0]
    assert (conversation["entry_source"], conversation["entry_ref"]) == ("link", "spring")


async def test_a_later_message_does_not_start_it_again(world: World) -> None:
    automation_id = await entry_automation(world, cooldown_hours=0)
    await link(world, "spring", automation_id)
    await world.referral(CUSTOMER, ref="spring")
    first = await world.dm(CUSTOMER, "hi!")
    second = await world.dm(CUSTOMER, "and another thing")
    assert first is not None
    assert second is not None
    assert await world.run("dm", first) is Outcome.FIRED
    assert await world.run("dm", second) is Outcome.NO_MATCH


async def test_a_ref_that_is_not_one_of_our_links_starts_nothing(world: World) -> None:
    await entry_automation(world)
    await world.referral(CUSTOMER, ref="unknown")
    first = await world.dm(CUSTOMER, "hi!")
    assert first is not None
    assert await world.run("dm", first) is Outcome.NO_MATCH


async def test_a_link_starts_only_its_own_automation(world: World) -> None:
    mine = await entry_automation(world, name="Spring")
    await entry_automation(world, name="Autumn")
    await link(world, "spring", mine)
    await world.referral(CUSTOMER, ref="spring")
    first = await world.dm(CUSTOMER, "hi!")
    assert first is not None
    assert await world.run("dm", first) is Outcome.FIRED
    assert (await world.run_row())["automation_id"] == mine


async def test_a_referral_older_than_an_hour_is_not_an_entry(world: World) -> None:
    automation_id = await entry_automation(world)
    await link(world, "spring", automation_id)
    then = datetime.now(UTC) - timedelta(hours=3)
    await world.referral(CUSTOMER, ref="spring", at=then)
    first = await world.dm(CUSTOMER, "hi!")
    assert first is not None
    assert await world.run("dm", first) is Outcome.NO_MATCH


async def test_an_ad_referral_starts_the_ad_click_automation(world: World) -> None:
    automation_id = await entry_automation(world, trigger="ad_click", name="From ads")
    ad = ReferralInfo(source="ad", ad_id="ad_77", ad_title="Spring sale", ctwa_clid="clid_1")
    first = await world.dm(CUSTOMER, "Is this still on?", referral=ad)
    assert first is not None

    assert await world.run("dm", first) is Outcome.FIRED
    assert (await world.run_row())["automation_id"] == automation_id
    conversation = (await world.rows("SELECT * FROM conversations"))[0]
    assert (conversation["entry_source"], conversation["entry_ad_id"]) == ("ad", "ad_77")
    assert conversation["last_referral"]["ctwa_clid"] == "clid_1"


async def test_an_ad_click_on_chosen_ads_passes_over_other_ads(world: World) -> None:
    await entry_automation(
        world, trigger="ad_click", post_scope="selected", ad_ids=["ad_1"], name="One ad"
    )
    other = ReferralInfo(source="ad", ad_id="ad_2")
    first = await world.dm(CUSTOMER, "hello", referral=other)
    assert first is not None
    assert await world.run("dm", first) is Outcome.SKIPPED
