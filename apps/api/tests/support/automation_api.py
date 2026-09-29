"""Helpers for the automation API tests: a signed-in owner with a sandbox Instagram account, the
plan, run rows and the messages runs point at (written through the ORM in the workspace's scope,
committed, returned as ids)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.automations import AutomationRun
from socialhood.models.inbox import Message
from tests.support.api import Clerk, sign_in

LINK = "https://maple.example/shop"


@dataclass
class Ws:
    client: httpx.AsyncClient
    clerk: Clerk
    clerk_id: str
    wid: str
    user_id: str
    account_id: str

    @property
    def headers(self) -> dict[str, str]:
        """A fresh session token per request, so calls work under time_machine too."""
        return self.clerk.headers(self.clerk_id)

    async def call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return await self.client.request(
            method, f"/v1/w/{self.wid}{path}", headers=self.headers, **kwargs
        )

    async def ok(self, method: str, path: str, status: int = 200, **kwargs: Any) -> Any:
        response = await self.call(method, path, **kwargs)
        assert response.status_code == status, response.text
        return response.json() if response.content else None

    def definition(self, **values: Any) -> dict[str, Any]:
        """A complete DM keyword definition on the sandbox account, with ``values`` changed."""
        body: dict[str, Any] = {
            "name": "Send the link",
            "social_account_id": self.account_id,
            "trigger": "dm_keyword",
            "keywords": ["link"],
            "action": "send_message",
            "message_text": "Hi {first_name}! Here's the link.",
            "message_buttons": [{"title": "Shop", "url": LINK}],
        }
        return {**body, **values}

    async def draft(self, **values: Any) -> dict[str, Any]:
        """A draft with a complete definition (``values`` change it)."""
        created = await self.ok("POST", "/automations", 201, json={"name": "Draft"})
        body = self.definition(**values)
        return await self.ok("PUT", f"/automations/{created['id']}", json=body)

    async def active(self, **values: Any) -> dict[str, Any]:
        draft = await self.draft(**values)
        return await self.ok("POST", f"/automations/{draft['id']}/activate")


async def workspace(
    client: httpx.AsyncClient, clerk: Clerk, *, email: str = "owner@example.com"
) -> Ws:
    clerk_id, me = await sign_in(client, clerk, email=email)
    wid = me["workspaces"][0]["id"]
    account = await client.post(
        f"/v1/w/{wid}/dev/sandbox/accounts", headers=clerk.headers(clerk_id)
    )
    assert account.status_code == 201, account.text
    return Ws(client, clerk, clerk_id, wid, me["id"], account.json()["id"])


async def set_plan(engine: AsyncEngine, wid: str, plan: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE subscriptions SET plan = :p WHERE workspace_id = :w"),
            {"p": plan, "w": wid},
        )


async def make_outbound(
    engine: AsyncEngine,
    *,
    workspace_id: str,
    account_id: str,
    conversation_id: uuid.UUID,
    status: str = "sent",
) -> uuid.UUID:
    """An automation's outbound message (its DM or private reply)."""
    with workspace_scope(uuid.UUID(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = Message(
                conversation_id=conversation_id,
                social_account_id=uuid.UUID(account_id),
                direction="outbound",
                source="automation",
                kind="text",
                text="Hi Priya! Here's the link.",
                occurred_at=datetime.now(UTC),
                client_id=uuid.uuid4(),
                status=status,
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_run(
    engine: AsyncEngine,
    *,
    workspace_id: str,
    automation_id: str | uuid.UUID,
    created_at: datetime,
    result: str = "sent",
    trigger_message_id: uuid.UUID | None = None,
    trigger_comment_id: uuid.UUID | None = None,
    **values: Any,
) -> uuid.UUID:
    with workspace_scope(uuid.UUID(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = AutomationRun(
                automation_id=uuid.UUID(str(automation_id)),
                trigger_message_id=trigger_message_id,
                trigger_comment_id=trigger_comment_id,
                matched_keyword=values.pop("matched_keyword", "link"),
                result=result,
                created_at=created_at,
                **values,
            )
            session.add(row)
            await session.commit()
            return row.id


async def count(engine: AsyncEngine, table: str) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one())  # noqa: S608
