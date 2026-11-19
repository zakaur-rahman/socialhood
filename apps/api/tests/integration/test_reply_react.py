"""GR-42: a reply quotes a message (stored, sent with the first part, shown in the thread and in
events) and a member reacts to a message (sent at once, stored as the business's, audited)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.runtime import Runtime
from socialhood.platforms.sandbox import outbox
from socialhood.realtime.events import stream_key
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import set_plan
from tests.support.inbox import make_thread
from tests.support.sending import (
    Setup,
    clean_outbox,
    message_row,
    post_message,
    run_send,
    use_app_runtime,
    workspace_with_thread,
)

HEART = "❤️"
THUMBS_UP = "\U0001f44d"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
def worker(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Runtime:
    return use_app_runtime(app, monkeypatch)


@pytest.fixture
async def setup(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    return await workspace_with_thread(client, clerk, engine)


async def whatsapp_setup(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    """A sandbox WhatsApp number and a customer who wrote five minutes ago."""
    clerk_id, me = await sign_in(client, clerk, email="wa@example.com", first_name="Asha")
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)
    await set_plan(engine, wid, "pro")  # WhatsApp is on Creator and up (C-172)
    created = await client.post(
        f"/v1/w/{wid}/dev/sandbox/accounts", json={"platform": "whatsapp"}, headers=headers
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]
    thread = await make_thread(
        engine,
        workspace_id=wid,
        account_id=account_id,
        platform="whatsapp",
        contact_ref="919800000042",
        last_inbound_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    return Setup(clerk_id, wid, account_id, thread, headers)


def react_url(setup: Setup, message_id: uuid.UUID | str) -> str:
    return f"{setup.messages_url}/{message_id}/reaction"


async def react(
    client: httpx.AsyncClient, setup: Setup, emoji: str | None, message_id: uuid.UUID | None = None
) -> httpx.Response:
    target = message_id or setup.thread.message_ids[0]
    return await client.put(react_url(setup, target), json={"emoji": emoji}, headers=setup.headers)


def problem(response: httpx.Response, status: int, code: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body: dict[str, object] = response.json()
    assert body["code"] == code
    return body


# ---------------------------------------------------------------- replies


async def test_a_reply_quotes_the_customers_message_everywhere(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    queue: None,
    worker: Runtime,
    redis: Redis,
) -> None:
    quoted_id = setup.thread.message_ids[0]
    quoted = await message_row(engine, str(quoted_id))
    response = await post_message(
        client, setup, text="Yes, we do", reply_to_message_id=str(quoted_id)
    )
    assert response.status_code == 202, response.text
    expected = {
        "id": str(quoted_id),
        "kind": "text",
        "direction": "inbound",
        "text_preview": "Do you ship to Pune?",
    }
    message = response.json()
    assert message["reply_to"] == expected
    assert (await message_row(engine, message["id"]))["reply_to_platform_message_id"] == (
        quoted["platform_message_id"]
    )

    await run_send(setup, message)
    [sent] = outbox.SENT
    assert sent.message.reply_to == quoted["platform_message_id"]

    listed = (await client.get(setup.messages_url, headers=setup.headers)).json()["items"]
    assert next(m for m in listed if m["id"] == message["id"])["reply_to"] == expected
    for entry in await redis.xrange(stream_key(uuid.UUID(setup.wid))):
        data = json.loads(entry[1]["data"])
        if entry[1]["type"] in ("message.created", "message.updated"):
            assert data["message"]["reply_to"] == expected
            assert "_reply_to" not in data


async def test_only_a_message_of_this_conversation_can_be_quoted(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    other = await make_thread(engine, workspace_id=setup.wid, account_id=setup.account_id)
    body = problem(
        await post_message(client, setup, reply_to_message_id=str(other.message_ids[0])),
        422,
        "validation_error",
    )
    assert body["errors"] == [
        {"field": "reply_to_message_id", "message": "That message isn't in this conversation."}
    ]


async def test_a_message_without_a_platform_id_cant_be_quoted(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    queued = (await post_message(client, setup, text="Not sent yet")).json()
    problem(
        await post_message(client, setup, reply_to_message_id=queued["id"]),
        422,
        "validation_error",
    )


# ---------------------------------------------------------------- reactions


async def test_a_heart_on_instagram_is_sent_stored_audited_and_removed(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, redis: Redis
) -> None:
    quoted = await message_row(engine, str(setup.thread.message_ids[0]))
    response = await react(client, setup, HEART)
    assert response.status_code == 200, response.text
    [reaction] = response.json()["reactions"]
    assert (reaction["emoji"], reaction["by"]) == (HEART, "business")
    [sent] = outbox.REACTIONS
    assert (sent.platform_message_id, sent.emoji) == (quoted["platform_message_id"], HEART)

    types = [e[1]["type"] for e in await redis.xrange(stream_key(uuid.UUID(setup.wid)))]
    assert types == ["message.updated"]
    audit = await client.get(
        f"/v1/w/{setup.wid}/audit-events?action=message.reacted", headers=setup.headers
    )
    assert audit.json()["items"][0]["target_id"] == str(setup.thread.message_ids[0])

    # The same reaction again changes nothing and sends nothing.
    assert (await react(client, setup, HEART)).status_code == 200
    assert len(outbox.REACTIONS) == 1

    removed = await react(client, setup, None)
    assert removed.status_code == 200
    assert removed.json()["reactions"] == []
    assert outbox.REACTIONS[-1].emoji is None


async def test_instagram_takes_only_a_heart(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    problem(await react(client, setup, THUMBS_UP), 409, "reaction_not_supported")
    assert not outbox.REACTIONS
    assert (await message_row(engine, str(setup.thread.message_ids[0])))["reactions"] == []


async def test_whatsapp_takes_the_six_and_one_replaces_the_other(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    setup = await whatsapp_setup(client, clerk, engine)
    assert (await react(client, setup, THUMBS_UP)).status_code == 200
    response = await react(client, setup, HEART)
    assert response.status_code == 200, response.text
    assert [r["emoji"] for r in response.json()["reactions"]] == [HEART]
    assert [r.emoji for r in outbox.REACTIONS] == [THUMBS_UP, HEART]


async def test_whatsapp_refuses_a_message_older_than_30_days(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    setup = await whatsapp_setup(client, clerk, engine)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE messages SET occurred_at = now() - interval '31 days' WHERE id = :id"),
            {"id": setup.thread.message_ids[0]},
        )
    problem(await react(client, setup, THUMBS_UP), 422, "validation_error")
    assert not outbox.REACTIONS


async def test_an_emoji_outside_the_six_is_invalid(client: httpx.AsyncClient, setup: Setup) -> None:
    problem(await react(client, setup, "\U0001f525"), 422, "validation_error")


async def test_a_closed_window_refuses_reactions(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    setup = await workspace_with_thread(client, clerk, engine, last_inbound_ago=timedelta(days=8))
    problem(await react(client, setup, HEART), 409, "reply_window_closed")


async def test_a_platform_failure_is_reported_and_nothing_is_stored(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    outbox.fail_next("platform_rejected", kind="react")
    problem(await react(client, setup, HEART), 502, "platform_error")
    assert (await message_row(engine, str(setup.thread.message_ids[0])))["reactions"] == []


async def test_a_message_of_another_conversation_is_not_found(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine
) -> None:
    other = await make_thread(engine, workspace_id=setup.wid, account_id=setup.account_id)
    problem(await react(client, setup, HEART, other.message_ids[0]), 404, "not_found")
