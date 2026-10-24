"""Helpers for the broadcast tests (GR-23): a workspace with a sandbox WhatsApp number on Pro,
customers with and without marketing consent, the dispatch and send jobs run in-process, and the
sandbox webhooks (a message, a status, a quality update) stored and processed like the worker."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.engine import make_sessionmaker
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.services.broadcasts import dispatch
from socialhood.services.webhook_processing import process_event
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import Ws, set_plan
from tests.support.inbox import make_thread
from tests.support.sending import context, use_app_runtime

TEMPLATE = "sale_offer"  # the sandbox number's marketing template: "Hi {{1}}, ... until {{2}}"
VARIABLES = [
    {"source": "field", "field": "first_name", "fallback": "there"},
    {"source": "fixed", "value": "31 October"},
]


@dataclass
class Customer:
    contact_id: uuid.UUID
    conversation_id: uuid.UUID
    wa_id: str
    name: str


@dataclass
class Shop:
    """A signed-in owner on Pro with a sandbox WhatsApp number and a segment of everyone."""

    ws: Ws
    app: FastAPI
    engine: AsyncEngine
    redis: Redis
    segment_id: str
    customers: list[Customer] = field(default_factory=list)

    @property
    def deps(self) -> PlatformDeps:
        return deps_from(self.app.state.http, self.app.state.settings)

    @property
    def maker(self) -> Any:
        return make_sessionmaker(self.engine)

    async def customer(
        self, name: str, *, consent: str | None = "granted", wa_id: str | None = None
    ) -> Customer:
        """A WhatsApp customer who wrote an hour ago; ``consent`` is granted, revoked or None."""
        wa = wa_id or f"9198{uuid.uuid4().int % 10**8:08d}"
        thread = await make_thread(
            self.engine,
            workspace_id=self.ws.wid,
            account_id=self.ws.account_id,
            platform="whatsapp",
            contact_ref=wa,
            username=None,
            display_name=name,
            last_inbound_at=datetime.now(UTC) - timedelta(hours=1),
        )
        if consent is not None:
            await self.ws.ok(
                "POST",
                f"/contacts/{thread.contact_id}/consents",
                json={"channel": "whatsapp", "status": consent, "note": "Asked in the shop"},
            )
        person = Customer(thread.contact_id, thread.conversation_id, wa, name)
        self.customers.append(person)
        return person

    def body(self, name: str = "Diwali sale", **values: Any) -> dict[str, Any]:
        base = {
            "name": name,
            "social_account_id": self.ws.account_id,
            "segment_id": self.segment_id,
            "template_name": TEMPLATE,
            "template_language": "en",
            "variables": VARIABLES,
        }
        return {**base, **values}

    async def broadcast(self, **values: Any) -> dict[str, Any]:
        """A saved draft."""
        return await self.ws.ok("POST", "/broadcasts", 201, json=self.body(**values))

    async def send_now(self, **values: Any) -> dict[str, Any]:
        draft = await self.broadcast(**values)
        return await self.ws.ok("POST", f"/broadcasts/{draft['id']}/start", json={})

    async def batch(self, broadcast_id: str, *, now: datetime | None = None) -> dispatch.Batch:
        """One batch of the dispatch job."""
        return await dispatch.run_batch(
            self.maker,
            self.redis,
            self.deps,
            workspace_id=uuid.UUID(self.ws.wid),
            broadcast_id=uuid.UUID(broadcast_id),
            now=now,
        )

    async def deliver_queued(self, send_tasks: Any) -> int:
        """Run send_message for every queued broadcast message, as the worker would."""
        async with self.engine.connect() as conn:
            queued = (
                await conn.execute(
                    text(
                        "SELECT id, conversation_id FROM messages"
                        " WHERE source = 'broadcast' AND status = 'queued' ORDER BY created_at"
                    )
                )
            ).all()
        for message_id, conversation_id in queued:
            await send_tasks.send_message(
                context(),
                message_id=str(message_id),
                conversation_id=str(conversation_id),
                workspace_id=self.ws.wid,
            )
        return len(queued)

    async def inject(self, **body: Any) -> httpx.Response:
        """A sandbox webhook for the number (dm, status or quality), stored; process it next."""
        return await self.ws.call(
            "POST",
            "/dev/sandbox/inbound",
            json={"account_id": self.ws.account_id, **body},
        )

    async def process_webhooks(self) -> list[WebhookStatus | None]:
        """Process every stored webhook event that is still ``received``."""
        async with self.engine.connect() as conn:
            ids = [
                row[0]
                for row in (
                    await conn.execute(
                        text(
                            "SELECT id FROM webhook_events WHERE status = 'received'"
                            " ORDER BY received_at"
                        )
                    )
                ).all()
            ]
        return [await process_event(self.maker, event_id, self.redis) for event_id in ids]

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def shop(
    client: httpx.AsyncClient,
    clerk: Clerk,
    app: FastAPI,
    engine: AsyncEngine,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
    *,
    plan: str = "pro",
    email: str = "owner@example.com",
    enabled: bool = True,
) -> Shop:
    """The setting on (it is off by default), the send job using the test app's runtime, and a
    workspace on ``plan`` with a sandbox WhatsApp number and a segment of everyone."""
    monkeypatch.setattr(app.state.settings, "broadcasts_enabled", enabled)
    use_app_runtime(app, monkeypatch)
    clerk_id, me = await sign_in(client, clerk, email=email, first_name="Asha")
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)
    created = await client.post(
        f"/v1/w/{wid}/dev/sandbox/accounts", params={"platform": "whatsapp"}, headers=headers
    )
    assert created.status_code == 201, created.text
    ws = Ws(client, clerk, clerk_id, wid, me["id"], created.json()["id"])
    await set_plan(engine, wid, plan)
    segment = await ws.ok("POST", "/contact-segments", 201, json={"name": "Everyone", "filter": {}})
    return Shop(ws, app, engine, redis, segment["id"])


async def make_broadcast_row(
    engine: AsyncEngine,
    *,
    workspace_id: str,
    account_id: str,
    segment_id: str | None = None,
    contact_id: uuid.UUID | str | None = None,
    message_id: uuid.UUID | str | None = None,
) -> str:
    """A broadcast with one recipient (when ``contact_id`` is given) and the number's health, for
    the isolation and deletion tests."""
    async with engine.begin() as conn:
        broadcast = (
            await conn.execute(
                text(
                    "INSERT INTO broadcasts (workspace_id, social_account_id, segment_id, name,"
                    " segment_name, template_name, template_language, template_category,"
                    " template_body, status) VALUES (:w, :a, :s, 'Diwali', 'Everyone',"
                    " 'sale_offer', 'en', 'marketing', 'Hi {{1}}', 'completed') RETURNING id"
                ),
                {"w": workspace_id, "a": account_id, "s": segment_id},
            )
        ).scalar_one()
        if contact_id is not None:
            await conn.execute(
                text(
                    "INSERT INTO broadcast_recipients (workspace_id, broadcast_id, contact_id,"
                    " position, state, message_id, dispatched_at) VALUES (:w, :b, :c, 0,"
                    " 'dispatched', :m, now())"
                ),
                {"w": workspace_id, "b": broadcast, "c": contact_id, "m": message_id},
            )
        await conn.execute(
            text(
                "INSERT INTO whatsapp_number_health (workspace_id, social_account_id,"
                " quality_rating, checked_at) VALUES (:w, :a, 'green', now())"
            ),
            {"w": workspace_id, "a": account_id},
        )
    return str(broadcast)
