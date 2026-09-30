"""A workspace with an owner, an admin and an agent (each with an email address) for the P8
delivery tests (T8.5-T8.7): notifications made through the real service, their emails sent
through the outbox and their pushes through push delivery, with the tests' FakeEmail and
FakePush."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.notify import outbox, push_delivery
from socialhood.notify.email import EmailError, EmailSender
from socialhood.notify.push import PushError, PushSender
from socialhood.services import notifications
from socialhood.settings import Settings


@dataclass
class Team:
    engine: AsyncEngine
    wid: uuid.UUID
    slug: str
    name: str
    owner: uuid.UUID
    admin: uuid.UUID
    agent: uuid.UUID
    emails: dict[uuid.UUID, str] = field(default_factory=dict)

    @property
    def maker(self) -> async_sessionmaker[AsyncSession]:
        return make_sessionmaker(self.engine)

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)

    async def insert(self, sql: str, **params: Any) -> uuid.UUID:
        """Run ``INSERT … RETURNING id`` and commit; returns the id."""
        async with self.engine.begin() as conn:
            row_id: uuid.UUID = (await conn.execute(text(sql), params)).scalar_one()
        return row_id

    async def notify(self, *, to: str = "admins", commit: bool = True, **values: Any) -> int:
        """notify_admins or notify_members in this workspace, committed like a producer does."""
        defaults: dict[str, Any] = {
            "type": "account_needs_reconnect",
            "severity": "critical",
            "title": "Reconnect @maple.bakery",
            "body": "@maple.bakery needs reconnecting to keep receiving messages.",
            "link": "/settings/connections",
            "dedupe_key": f"reconnect:{uuid.uuid4()}",
        }
        produce = notifications.notify_admins if to == "admins" else notifications.notify_members
        with workspace_scope(self.wid):
            async with self.maker() as session:
                created = await produce(session, **{**defaults, **values})
                if commit:
                    await session.commit()
                else:
                    await session.rollback()
        return created

    async def set_prefs(self, user_id: uuid.UUID, prefs: dict[str, Any]) -> None:
        await self.execute(
            "UPDATE workspace_members SET notification_prefs = CAST(:p AS jsonb)"
            " WHERE workspace_id = :w AND user_id = :u",
            p=json.dumps(prefs),
            w=self.wid,
            u=user_id,
        )

    async def add_member(self, role: str, *, email: str | None = None) -> uuid.UUID:
        user_id = await make_user(self.engine, email=email)
        await self.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (:w, :u, :r)",
            w=self.wid,
            u=user_id,
            r=role,
        )
        [row] = await self.rows("SELECT email FROM users WHERE id = :u", u=user_id)
        self.emails[user_id] = row["email"]
        return user_id

    async def send_email(
        self,
        delivery_id: uuid.UUID,
        sender: EmailSender,
        settings: Settings,
        *,
        will_retry: bool | None = None,
        now: datetime | None = None,
    ) -> str:
        with workspace_scope(self.wid):
            return await outbox.send_queued(
                self.maker,
                delivery_id,
                sender=sender,
                settings=settings,
                will_retry=None if will_retry is None else _always(will_retry),
                now=now,
            )

    async def push(
        self,
        notification_id: uuid.UUID,
        sender: PushSender,
        *,
        will_retry: bool | None = None,
        now: datetime | None = None,
    ) -> int:
        with workspace_scope(self.wid):
            return await push_delivery.deliver(
                self.maker,
                notification_id,
                sender=sender,
                will_retry=None if will_retry is None else _always(will_retry),
                now=now,
            )

    async def deliveries(self) -> list[dict[str, Any]]:
        return await self.rows(
            "SELECT * FROM email_deliveries WHERE workspace_id = :w ORDER BY created_at, to_email",
            w=self.wid,
        )

    async def notes(self, type: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM notifications WHERE workspace_id = :w"
        if type is not None:
            sql += " AND type = :t"
        return await self.rows(sql + " ORDER BY created_at, user_id", w=self.wid, t=type)


def _always(answer: bool) -> Any:
    def decide(error: EmailError | PushError) -> bool:
        return answer

    return decide


async def make_user(engine: AsyncEngine, *, email: str | None = None) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:10]
    async with engine.begin() as conn:
        user_id: uuid.UUID = (
            await conn.execute(
                text("INSERT INTO users (clerk_user_id, email) VALUES (:c, :e) RETURNING id"),
                {"c": f"user_{suffix}", "e": email or f"{suffix}@example.com"},
            )
        ).scalar_one()
    return user_id


async def make_team(engine: AsyncEngine, *, timezone: str = "UTC") -> Team:
    """A workspace (slug ``ws-…``) whose owner, admin and agent all have addresses."""
    owner = await make_user(engine)
    suffix = uuid.uuid4().hex[:10]
    async with engine.begin() as conn:
        wid: uuid.UUID = (
            await conn.execute(
                text(
                    "INSERT INTO workspaces (name, slug, owner_user_id, timezone)"
                    " VALUES (:n, :s, :o, :tz) RETURNING id"
                ),
                {"n": "Maple Bakery", "s": f"ws-{suffix}", "o": owner, "tz": timezone},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'owner')"
            ),
            {"w": wid, "u": owner},
        )
    team = Team(engine, wid, f"ws-{suffix}", "Maple Bakery", owner, owner, owner)
    [row] = await team.rows("SELECT email FROM users WHERE id = :u", u=owner)
    team.emails[owner] = row["email"]
    team.admin = await team.add_member("admin")
    team.agent = await team.add_member("agent")
    return team
