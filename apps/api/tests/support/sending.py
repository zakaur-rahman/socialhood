"""Helpers for the send pipeline tests: a workspace with a sandbox (or Instagram) account and a
thread, the send endpoint, and the send_message task run in-process like a worker would."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from procrastinate.jobs import Job
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.runtime import Runtime
from socialhood.jobs.tasks import send as send_tasks
from socialhood.platforms.sandbox import outbox
from socialhood.security.crypto import TokenCipher
from tests.support.api import TOKEN_KEY, Clerk, sign_in
from tests.support.inbox import Thread, make_account, make_thread

IG_ACCOUNT = "17841400000000001"
IG_TOKEN = "IGQVJsend-token"


def clean_outbox() -> Iterator[None]:
    """For an autouse fixture: the sandbox's sends and injected failures start empty."""
    outbox.reset()
    yield
    outbox.reset()


def use_app_runtime(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Runtime:
    """Make the send tasks use the test app's settings, database, Valkey and HTTP client."""
    rt = Runtime(
        settings=app.state.settings,
        sessionmaker=app.state.sessionmaker,
        redis=app.state.redis,
        http=app.state.http,
    )
    monkeypatch.setattr(send_tasks, "runtime", lambda: rt)
    return rt


@dataclass
class Setup:
    clerk_id: str
    wid: str
    account_id: str
    thread: Thread
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def conversation_id(self) -> str:
        return str(self.thread.conversation_id)

    @property
    def messages_url(self) -> str:
        return f"/v1/w/{self.wid}/conversations/{self.conversation_id}/messages"


async def workspace_with_thread(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    *,
    last_inbound_ago: timedelta = timedelta(minutes=5),
    instagram: bool = False,
    email: str = "owner@example.com",
) -> Setup:
    """A signed-in owner, one account (sandbox, or a real-looking Instagram one with a token)
    and a conversation whose customer last wrote ``last_inbound_ago``."""
    clerk_id, me = await sign_in(client, clerk, email=email, first_name="Asha")
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)
    if instagram:
        account_id = str(await make_account(engine, wid, platform_account_id=IG_ACCOUNT))
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE social_accounts SET access_token_enc = :t WHERE id = :id"),
                {"t": TokenCipher([TOKEN_KEY]).encrypt(IG_TOKEN), "id": account_id},
            )
    else:
        created = await client.post(f"/v1/w/{wid}/dev/sandbox/accounts", headers=headers)
        assert created.status_code == 201, created.text
        account_id = created.json()["id"]
    thread = await make_thread(
        engine,
        workspace_id=wid,
        account_id=account_id,
        last_inbound_at=datetime.now(UTC) - last_inbound_ago,
    )
    return Setup(clerk_id, wid, account_id, thread, headers)


async def post_message(
    client: httpx.AsyncClient, setup: Setup, *, key: str | None = None, **body: Any
) -> httpx.Response:
    payload: dict[str, Any] = {"client_id": str(uuid.uuid4()), "text": "Yes, we ship to Pune"}
    payload.update(body)
    return await client.post(
        setup.messages_url,
        json=payload,
        headers={**setup.headers, "Idempotency-Key": key or str(payload["client_id"])},
    )


@dataclass
class FakeContext:
    job: Job


def context(attempts: int = 0) -> FakeContext:
    return FakeContext(
        Job(
            id=1,
            queue="interactive",
            lock=None,
            queueing_lock=None,
            task_name="send_message",
            attempts=attempts,
        )
    )


async def run_send(setup: Setup, message: dict[str, Any], *, attempts: int = 0) -> None:
    """Run send_message as the worker would on its attempt number ``attempts`` (0 first)."""
    await send_tasks.send_message(
        context(attempts),
        message_id=str(message["id"]),
        conversation_id=str(message["conversation_id"]),
        workspace_id=setup.wid,
    )


async def outbound_rows(engine: AsyncEngine, setup: Setup) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT * FROM messages WHERE conversation_id = :c AND direction = 'outbound'"
                " ORDER BY occurred_at"
            ),
            {"c": setup.conversation_id},
        )
        return [dict(r._mapping) for r in result]


async def message_row(engine: AsyncEngine, message_id: str) -> dict[str, Any]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM messages WHERE id = :id"), {"id": message_id}
        )
        return dict(result.one()._mapping)


async def conversation_row(engine: AsyncEngine, setup: Setup) -> dict[str, Any]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM conversations WHERE id = :id"), {"id": setup.conversation_id}
        )
        return dict(result.one()._mapping)


async def send_jobs(task: str = "send_message") -> list[dict[str, Any]]:
    return list(
        await jobs_app.connector.execute_query_all_async(
            "SELECT id, status, args, lock, queueing_lock, scheduled_at"
            " FROM procrastinate_jobs WHERE task_name = %(t)s ORDER BY id",
            t=task,
        )
    )
