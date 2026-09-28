"""T3.6 read receipts: marking a conversation read queues the platform "seen" call, which is sent
only for accounts with the read_receipts capability; failures are logged, not surfaced."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.runtime import Runtime
from socialhood.jobs.tasks import send as send_tasks
from socialhood.platforms.sandbox import outbox
from socialhood.repositories import inbox
from socialhood.services.read_receipts import after_marked_read
from tests.support.api import Clerk
from tests.support.instagram import GRAPH
from tests.support.sending import (
    IG_TOKEN,
    clean_outbox,
    send_jobs,
    use_app_runtime,
    workspace_with_thread,
)

SEND_URL = rf"{GRAPH}/v[\d.]+/me/messages"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
def worker(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Runtime:
    return use_app_runtime(app, monkeypatch)


async def test_marking_read_queues_one_seen_call(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    setup = await workspace_with_thread(client, clerk, engine)
    with workspace_scope(uuid.UUID(setup.wid)):
        async with worker.sessionmaker() as session:
            conv = await inbox.get_conversation(session, setup.thread.conversation_id)
            assert conv is not None
            await after_marked_read(session, conv)
            await after_marked_read(session, conv)  # opened twice: still one waiting job
    [job] = await send_jobs("mark_read")
    assert job["args"] == {"conversation_id": setup.conversation_id, "workspace_id": setup.wid}

    await send_tasks.mark_read(**job["args"])
    [(account_ref, recipient)] = outbox.SEEN
    assert account_ref.startswith("sandbox_")
    assert recipient.startswith("igsid_")


async def test_an_enqueue_failure_is_not_surfaced(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, worker: Runtime
) -> None:
    setup = await workspace_with_thread(client, clerk, engine)
    with workspace_scope(uuid.UUID(setup.wid)):
        async with worker.sessionmaker() as session:
            conv = await inbox.get_conversation(session, setup.thread.conversation_id)
            assert conv is not None
            await after_marked_read(session, conv)  # the queue is not open: logged only


async def test_instagram_gets_mark_seen_and_errors_are_swallowed(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, worker: Runtime
) -> None:
    setup = await workspace_with_thread(client, clerk, engine, instagram=True)
    route = clerk.router.post(url__regex=SEND_URL).respond(200, json={"recipient_id": "x"})
    await send_tasks.mark_read(conversation_id=setup.conversation_id, workspace_id=setup.wid)
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {IG_TOKEN}"
    body = json.loads(request.content)
    assert body["sender_action"] == "mark_seen"
    assert body["recipient"]["id"].startswith("igsid_")

    route.respond(400, json={"error": {"code": 100, "message": "Invalid parameter"}})
    await send_tasks.mark_read(conversation_id=setup.conversation_id, workspace_id=setup.wid)
    assert route.call_count == 2
