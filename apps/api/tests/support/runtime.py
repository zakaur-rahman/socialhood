"""Helpers for the automation runtime and private-reply queue tests (T4.4, T4.6, T4.8): a
workspace with a sandbox account, comments and customer DMs (taps too) taken in through the real
intake and ingest, and the jobs' bodies run in-process at a chosen time."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.events import InboundComment, InboundMessage
from socialhood.repositories import social_accounts as accounts
from socialhood.services import sending
from socialhood.services.automations import comments, queue, runtime
from socialhood.services.ingest import ingest
from socialhood.services.webhook_handlers import instagram as instagram_handler
from socialhood.settings import Settings
from tests.support.inbox import make_account, make_workspace


@asynccontextmanager
async def platform_deps(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[PlatformDeps]:
    """Platform deps with the sandbox on; webhook comment intake uses them too."""
    async with httpx.AsyncClient() as http:
        platform = deps_from(http, settings)
        monkeypatch.setattr(instagram_handler, "platform_deps", lambda: platform)
        yield platform


@dataclass
class World:
    engine: AsyncEngine
    redis: Redis
    deps: PlatformDeps
    wid: uuid.UUID
    account_id: uuid.UUID

    @property
    def maker(self) -> async_sessionmaker[AsyncSession]:
        return make_sessionmaker(self.engine)

    async def run(
        self, kind: str, trigger_id: uuid.UUID, *, now: datetime | None = None
    ) -> runtime.Outcome:
        """run_automation(kind, id), as the worker runs it."""
        with workspace_scope(self.wid):
            return await runtime.run(
                self.maker,
                self.redis,
                self.deps,
                kind=kind,
                trigger_id=trigger_id,
                workspace_id=self.wid,
                now=now,
            )

    async def drain(
        self, *, now: datetime | None = None, account_id: uuid.UUID | None = None
    ) -> queue.DrainResult:
        with workspace_scope(self.wid):
            return await queue.drain(
                self.maker, self.redis, self.deps, account_id=account_id or self.account_id, now=now
            )

    async def queue_info(self, *, now: datetime | None = None) -> tuple[int, int | None]:
        with workspace_scope(self.wid):
            async with self.maker() as session:
                return await queue.account_queue(session, self.account_id, now=now)

    async def send(self, message_id: uuid.UUID, *, now: datetime | None = None) -> sending.Delivery:
        """The send_message job for one message (no retries left)."""
        [row] = await self.rows(
            "SELECT conversation_id FROM messages WHERE id = :id", id=message_id
        )
        job = sending.SendJob(
            message_id=message_id, conversation_id=row["conversation_id"], workspace_id=self.wid
        )
        with workspace_scope(self.wid):
            return await sending.deliver(
                self.maker, self.redis, self.deps, job, will_retry=lambda error: False, now=now
            )

    async def comment(
        self,
        text_: str,
        *,
        media_ref: str = "sandbox_post_1",
        author: str | None = None,
        username: str = "curious.cat",
        parent: str | None = None,
        at: datetime | None = None,
        account_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        """A comment through the real intake (F-12); its id, or None when nothing was stored."""
        event = InboundComment(
            account_ref="sandbox",
            occurred_at=at or datetime.now(UTC),
            platform_comment_id=f"1790{uuid.uuid4().int % 10**12:012d}",
            media_id=media_ref,
            parent_id=parent,
            author_ref=author or f"99{uuid.uuid4().int % 10**13:013d}",
            author_username=username,
            text=text_,
        )
        with workspace_scope(self.wid):
            async with self.maker() as session:
                acct = await accounts.get(session, account_id or self.account_id)
                assert acct is not None
                taken = await comments.intake(session, acct, event, deps=lambda: self.deps)
                await session.commit()
        return taken.comment.id if taken.comment else None

    async def dm(
        self,
        contact_ref: str,
        text_: str,
        *,
        payload: str | None = None,
        mid: str | None = None,
        at: datetime | None = None,
    ) -> uuid.UUID | None:
        """A customer DM (a tapped quick reply with ``payload``) through the real ingest; its
        id, or None when nothing new was stored (a redelivery)."""
        event = InboundMessage(
            account_ref="sandbox",
            occurred_at=at or datetime.now(UTC),
            contact_ref=contact_ref,
            contact_name=None,
            platform_message_id=mid or f"mid_{uuid.uuid4().hex}",
            kind="text",
            text=text_,
            quick_reply_payload=payload,
        )
        with workspace_scope(self.wid):
            async with self.maker() as session:
                acct = await accounts.get(session, self.account_id)
                assert acct is not None
                result = await ingest(session, acct, [event])
                await session.commit()
        return result.created_message_ids[0] if result.created_message_ids else None

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def plan(self, plan: str) -> None:
        """The workspace's plan (a bare workspace has no subscription row: Free). A second
        account of a platform needs Pro, or it is read-only and sends nothing (FR-BIL-07)."""
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO subscriptions (workspace_id, plan, status, billing_anchor_day)"
                    " VALUES (:w, :p, 'active', 1)"
                    " ON CONFLICT (workspace_id) DO UPDATE SET plan = :p"
                ),
                {"w": self.wid, "p": plan},
            )

    async def run_row(self, run_id: uuid.UUID | None = None) -> dict[str, Any]:
        if run_id is None:
            [row] = await self.rows(
                "SELECT * FROM automation_runs WHERE result <> 'skipped_cooldown'"
            )
            return row
        [row] = await self.rows("SELECT * FROM automation_runs WHERE id = :id", id=run_id)
        return row


async def make_world(engine: AsyncEngine, redis: Redis, deps: PlatformDeps) -> World:
    wid = await make_workspace(engine)
    account_id = await make_account(engine, wid)
    return World(engine, redis, deps, wid, account_id)
