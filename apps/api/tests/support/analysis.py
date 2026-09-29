"""Helpers for the analysis, summary and follow-up reminder tests (T5.2, T5.7, T5.11): a workspace
with an owner member and an Instagram account, customer DMs through the real ingest, and the jobs'
bodies run in-process."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks.analysis import remind_closing_windows
from socialhood.platforms.events import InboundMessage
from socialhood.repositories import social_accounts as accounts
from socialhood.services import analysis, summaries
from socialhood.services.ingest import ingest
from socialhood.settings import Settings, get_settings
from tests.support.inbox import make_account, make_workspace


@dataclass
class Inbox:
    engine: AsyncEngine
    redis: Redis
    wid: uuid.UUID
    account_id: uuid.UUID
    settings: Settings

    @property
    def maker(self) -> async_sessionmaker[AsyncSession]:
        return make_sessionmaker(self.engine)

    async def dm(
        self, contact_ref: str, text_: str, *, at: datetime | None = None, name: str | None = None
    ) -> uuid.UUID:
        """A customer DM through the real ingest (which queues analyze_conversation)."""
        event = InboundMessage(
            account_ref="sandbox",
            occurred_at=at or datetime.now(UTC),
            contact_ref=contact_ref,
            contact_name=name,
            platform_message_id=f"mid_{uuid.uuid4().hex}",
            kind="text",
            text=text_,
        )
        with workspace_scope(self.wid):
            async with self.maker() as session:
                acct = await accounts.get(session, self.account_id)
                assert acct is not None
                result = await ingest(session, acct, [event])
                await session.commit()
        [message_id] = result.created_message_ids
        return message_id

    async def business(self, conversation_id: uuid.UUID, text_: str, *, at: datetime) -> uuid.UUID:
        """A business message written straight to the tables (as a sent reply would be)."""
        async with self.engine.begin() as conn:
            message_id = (
                await conn.execute(
                    text(
                        "INSERT INTO messages (workspace_id, conversation_id, social_account_id,"
                        " direction, source, kind, text, occurred_at, status)"
                        " VALUES (:w, :c, :a, 'outbound', 'human', 'text', :t, :at, 'sent')"
                        " RETURNING id"
                    ),
                    {
                        "w": self.wid,
                        "c": conversation_id,
                        "a": self.account_id,
                        "t": text_,
                        "at": at,
                    },
                )
            ).scalar_one()
            await conn.execute(
                text(
                    "UPDATE conversations SET last_outbound_at = :at, last_message_at = :at,"
                    " awaiting_reply = false WHERE id = :c"
                ),
                {"at": at, "c": conversation_id},
            )
        return message_id  # type: ignore[no-any-return]

    async def conversation_id(self, contact_ref: str) -> uuid.UUID:
        [row] = await self.rows(
            "SELECT v.id FROM conversations v JOIN contacts c ON c.id = v.contact_id"
            " WHERE c.platform_user_id = :ref",
            ref=contact_ref,
        )
        return row["id"]  # type: ignore[no-any-return]

    async def conversation(self, conversation_id: uuid.UUID) -> dict[str, Any]:
        [row] = await self.rows("SELECT * FROM conversations WHERE id = :id", id=conversation_id)
        return row

    async def analyze(
        self, conversation_id: uuid.UUID, *, now: datetime | None = None
    ) -> analysis.AnalysisRun:
        """analyze_conversation, as the worker runs it."""
        return await analysis.analyze_conversation(
            self.maker,
            self.redis,
            self.settings,
            workspace_id=self.wid,
            conversation_id=conversation_id,
            now=now,
        )

    async def summarize(
        self, conversation_id: uuid.UUID, *, now: datetime | None = None
    ) -> summaries.SummaryRun:
        return await summaries.summarize_conversation(
            self.maker,
            self.redis,
            self.settings,
            workspace_id=self.wid,
            conversation_id=conversation_id,
            now=now,
        )

    async def check_windows(self, now: datetime | None = None) -> list[uuid.UUID]:
        return await remind_closing_windows(self.maker, self.redis, self.settings, now=now)

    async def set(self, table: str, row_id: uuid.UUID, **values: Any) -> None:
        assignments = ", ".join(f"{name} = :{name}" for name in values)
        async with self.engine.begin() as conn:
            await conn.execute(
                text(f"UPDATE {table} SET {assignments} WHERE id = :id"),  # noqa: S608
                {**values, "id": row_id},
            )

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def add_owner_member(engine: AsyncEngine, workspace_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " SELECT id, owner_user_id, 'owner' FROM workspaces WHERE id = :w"
            ),
            {"w": workspace_id},
        )


async def make_inbox(engine: AsyncEngine, redis: Redis) -> Inbox:
    wid = await make_workspace(engine)
    await add_owner_member(engine, wid)
    account_id = await make_account(engine, wid)
    return Inbox(engine, redis, wid, account_id, get_settings())


async def use_credits(engine: AsyncEngine, wid: uuid.UUID, used: int, *, now: datetime) -> None:
    """Set this period's AI credits used (the Free plan has 200)."""
    from socialhood.ai.metering import quota

    maker = make_sessionmaker(engine)
    with workspace_scope(wid):
        async with maker() as session:
            await quota(session, now=now)  # creates the period's counter
            await session.commit()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE usage_counters SET used = :u WHERE workspace_id = :w"),
            {"u": used, "w": wid},
        )
