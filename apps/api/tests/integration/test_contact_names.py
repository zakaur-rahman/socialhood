"""C-135: team-saved contact names survive platform profile names, on every path."""

from __future__ import annotations

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.analysis import Inbox, make_inbox
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.inbox import make_thread


@pytest.fixture
async def inbox(engine: AsyncEngine, redis: Redis, clean_db: None, queue: None) -> Inbox:
    return await make_inbox(engine, redis)


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def contact_row(inbox: Inbox, ref: str) -> dict[str, object]:
    [row] = await inbox.rows(
        "SELECT display_name, name_source, platform_name FROM contacts WHERE platform_user_id = :r",
        r=ref,
    )
    return row


async def test_an_inbound_name_fills_a_platform_named_contact_and_updates_it(
    inbox: Inbox,
) -> None:
    await inbox.dm("c1", "Hi", name="Asha R.")
    assert await contact_row(inbox, "c1") == {
        "display_name": "Asha R.",
        "name_source": "platform",
        "platform_name": "Asha R.",
    }
    await inbox.dm("c1", "Hello again", name="Asha Rao")
    row = await contact_row(inbox, "c1")
    assert (row["display_name"], row["platform_name"]) == ("Asha Rao", "Asha Rao")


async def test_an_inbound_message_keeps_a_team_name(inbox: Inbox) -> None:
    await inbox.dm("c2", "Hi", name="Asha R.")
    async with inbox.engine.begin() as conn:
        await conn.execute(
            text("UPDATE contacts SET display_name = 'Asha (wholesale)', name_source = 'team'")
        )
    await inbox.dm("c2", "Hello again", name="Asha Rao")
    assert await contact_row(inbox, "c2") == {
        "display_name": "Asha (wholesale)",
        "name_source": "team",
        "platform_name": "Asha Rao",
    }


async def test_a_missing_inbound_name_never_clears_a_name(inbox: Inbox) -> None:
    await inbox.dm("c3", "Hi", name="Asha R.")
    await inbox.dm("c3", "Again", name=None)
    assert (await contact_row(inbox, "c3"))["display_name"] == "Asha R."


async def test_renaming_sets_team_and_reverting_restores_the_platform_name(
    engine: AsyncEngine, ws: Ws
) -> None:
    thread = await make_thread(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        contact_ref="asha",
        username="asha",
        display_name="Asha R.",
        texts=("Hi",),
    )
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE contacts SET platform_name = 'Asha R.'"))
    renamed = await ws.ok(
        "PATCH", f"/contacts/{thread.contact_id}", json={"name": "Asha (wholesale)"}
    )
    assert (renamed["name"], renamed["name_source"], renamed["platform_name"]) == (
        "Asha (wholesale)",
        "team",
        "Asha R.",
    )
    detail = await ws.ok("GET", f"/conversations/{thread.conversation_id}")
    assert detail["contact"]["name_source"] == "team"
    assert detail["contact"]["platform_name"] == "Asha R."
    back = await ws.ok("PATCH", f"/contacts/{thread.contact_id}", json={"use_platform_name": True})
    assert (back["name"], back["name_source"]) == ("Asha R.", "platform")
