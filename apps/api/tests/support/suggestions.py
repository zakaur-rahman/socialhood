"""Suggestion and auto-reply test support (T5.4, T5.6): fake "suggest" answers, and a context
that runs suggest_reply and decide_auto_reply in-process with the test app's database, Valkey
and sandbox platform, like a worker would."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.ai.fake import FakeProvider
from socialhood.ai.metering import quota
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.models.ai import AiDecision
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.events import InboundMessage
from socialhood.realtime import events
from socialhood.repositories import social_accounts
from socialhood.services.ingest import ingest
from socialhood.services.suggestions import auto, service
from tests.support.ai import make_analysis, make_source
from tests.support.api import Clerk
from tests.support.ingest import stream
from tests.support.sending import Setup, workspace_with_thread

SHIPPING_Q = "How much is shipping?"
SHIPPING_A = "Shipping is free on orders over ₹999. Track orders at https://maple.example/track"
SHIPPING_REPLY = "Shipping is free on orders over ₹999."


def answer(
    reply: str = SHIPPING_REPLY, *, used: tuple[str, ...] = ("k1",), confidence: float = 0.9
) -> dict[str, Any]:
    """What the model returns when knowledge answers the question (TR-AI-06)."""
    return {
        "can_answer": True,
        "reply": reply,
        "missing_info": None,
        "missing_topic": None,
        "confidence": confidence,
        "used_source_ids": list(used),
    }


def cannot(
    missing_info: str = "whether you ship to Dubai", topic: str = "shipping to uae"
) -> dict[str, Any]:
    return {
        "can_answer": False,
        "reply": None,
        "missing_info": missing_info,
        "missing_topic": topic,
        "confidence": 0.2,
        "used_source_ids": [],
    }


@dataclass
class Ai:
    """A signed-in owner's workspace with a sandbox account and one customer question."""

    app: FastAPI
    client: httpx.AsyncClient
    engine: AsyncEngine
    redis: Redis
    fake: FakeProvider
    setup: Setup

    @property
    def wid(self) -> uuid.UUID:
        return uuid.UUID(self.setup.wid)

    @property
    def conversation_id(self) -> uuid.UUID:
        return self.setup.thread.conversation_id

    @property
    def message_id(self) -> uuid.UUID:
        return self.setup.thread.message_ids[-1]

    @property
    def maker(self) -> async_sessionmaker[AsyncSession]:
        return make_sessionmaker(self.engine)

    @property
    def deps(self) -> PlatformDeps:
        return deps_from(self.app.state.http, self.app.state.settings)

    async def call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return await self.client.request(
            method, f"/v1/w/{self.setup.wid}{path}", headers=self.setup.headers, **kwargs
        )

    async def suggest(
        self, message_id: uuid.UUID | None = None, *, regeneration: int = 0
    ) -> service.Outcome:
        """suggest_reply, as the worker runs it (no retry left)."""
        with workspace_scope(self.wid):
            return await service.generate(
                self.maker,
                self.redis,
                workspace_id=self.wid,
                conversation_id=self.conversation_id,
                message_id=message_id or self.message_id,
                regeneration=regeneration,
            )

    async def decide(self, suggestion_id: uuid.UUID) -> AiDecision | None:
        with workspace_scope(self.wid):
            return await auto.decide(self.maker, self.redis, self.deps, suggestion_id=suggestion_id)

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)

    async def suggestions(self) -> list[dict[str, Any]]:
        return await self.rows(
            "SELECT * FROM reply_suggestions WHERE conversation_id = :c ORDER BY created_at, id",
            c=self.conversation_id,
        )

    async def pending(self) -> dict[str, Any]:
        [row] = await self.rows(
            "SELECT * FROM reply_suggestions WHERE conversation_id = :c AND status = 'pending'",
            c=self.conversation_id,
        )
        return row

    async def events(self, *types: str) -> list[tuple[str, dict[str, Any]]]:
        published = await stream(self.redis, self.wid)
        return [(kind, p) for kind, p in published if not types or kind in types]

    async def plan(self, plan: str) -> None:
        await self.execute(
            "UPDATE subscriptions SET plan = :p WHERE workspace_id = :w", p=plan, w=self.wid
        )

    async def mode(self, mode: str) -> None:
        await self.execute(
            "UPDATE social_accounts SET ai_mode = :m WHERE id = :a",
            m=mode,
            a=self.setup.account_id,
        )

    async def set_used(self, used: int) -> None:
        """This period's AI credits used (the counter is created first)."""
        with workspace_scope(self.wid):
            async with self.maker() as session:
                await quota(session)
                await session.commit()
        await self.execute(
            "UPDATE usage_counters SET used = :u WHERE workspace_id = :w", u=used, w=self.wid
        )

    async def used(self) -> int:
        found = await self.rows(
            "SELECT used FROM usage_counters WHERE workspace_id = :w", w=self.wid
        )
        return int(found[0]["used"]) if found else 0

    async def receive(
        self, body: str, *, echo: bool = False, at: datetime | None = None
    ) -> uuid.UUID | None:
        """A customer message (or, with ``echo``, a reply from the Instagram app) through the
        real ingest; the new message's id."""
        [contact] = await self.rows(
            "SELECT platform_user_id FROM contacts WHERE id = :c", c=self.setup.thread.contact_id
        )
        event = InboundMessage(
            account_ref="sandbox",
            occurred_at=at or datetime.now(UTC),
            contact_ref=contact["platform_user_id"],
            contact_name=None,
            platform_message_id=f"mid_{uuid.uuid4().hex}",
            kind="text",
            text=body,
            is_echo=echo,
        )
        with workspace_scope(self.wid):
            async with self.maker() as session:
                acct = await social_accounts.get(session, uuid.UUID(self.setup.account_id))
                assert acct is not None
                result = await ingest(session, acct, [event])
                await events.commit_and_publish(session, self.redis)
        return result.created_message_ids[0] if result.created_message_ids else None

    async def shipping_faq(self) -> uuid.UUID:
        return await make_source(
            self.engine, workspace_id=self.wid, question=SHIPPING_Q, body=SHIPPING_A
        )

    async def analysis(self, message_id: uuid.UUID | None = None, **values: Any) -> uuid.UUID:
        return await make_analysis(
            self.engine,
            workspace_id=self.wid,
            conversation_id=self.conversation_id,
            message_id=message_id or self.message_id,
            **{"intent": "shipping", **values},
        )


async def make_ai(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    fake: FakeProvider,
    *,
    question: str = SHIPPING_Q,
) -> Ai:
    setup = await workspace_with_thread(client, clerk, engine)
    ai = Ai(app, client, engine, redis, fake, setup)
    await ai.execute("UPDATE messages SET text = :t WHERE id = :id", t=question, id=ai.message_id)
    return ai
