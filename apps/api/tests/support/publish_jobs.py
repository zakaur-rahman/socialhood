"""The publish jobs' bodies run in-process against sandbox accounts (T7.3): a workspace with an
owner and two sandbox accounts, due posts, and each job as the worker runs it."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks import publishing as publish_jobs
from socialhood.models.connections import SocialAccount
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.services.post_publishing import publish
from tests.support.analysis import add_owner_member
from tests.support.inbox import make_account, make_asset, make_workspace
from tests.support.publishing import MadePost, make_scheduled_post

FILE_FORMATS = {"image": "jpg", "video": "mp4"}


def never(error: PlatformError) -> bool:
    return False


def always(error: PlatformError) -> bool:
    return True


@dataclass
class Desk:
    engine: AsyncEngine
    redis: Redis
    deps: PlatformDeps
    wid: uuid.UUID
    account_ids: list[uuid.UUID]

    @property
    def maker(self) -> async_sessionmaker[AsyncSession]:
        return make_sessionmaker(self.engine)

    async def post(
        self,
        kinds: Sequence[str] = ("image",),
        *,
        accounts: Sequence[uuid.UUID] | None = None,
        status: str = "scheduled",
        publish_at: datetime | None = None,
        workspace_id: uuid.UUID | None = None,
        **values: Any,
    ) -> MadePost:
        """A post due a minute ago (unless ``publish_at`` says otherwise) with one asset per
        kind, in order, on the first account unless ``accounts`` are given."""
        wid = workspace_id or self.wid
        assets = [
            await make_asset(
                self.engine,
                workspace_id=wid,
                purpose="post",
                resource_type=kind,
                fmt=FILE_FORMATS[kind],
            )
            for kind in kinds
        ]
        return await make_scheduled_post(
            self.engine,
            workspace_id=wid,
            account_ids=list(accounts or self.account_ids[:1]),
            asset_ids=assets,
            status=status,
            publish_at=publish_at or datetime.now(UTC) - timedelta(minutes=1),
            **values,
        )

    # ---- the jobs

    async def dispatch(self, now: datetime | None = None) -> list[uuid.UUID]:
        return await publish_jobs.dispatch_due(self.maker, self.redis, now)

    async def publish(
        self,
        target_id: uuid.UUID,
        *,
        will_retry: Callable[[PlatformError], bool] = never,
        now: datetime | None = None,
    ) -> publish.Outcome:
        with workspace_scope(self.wid):
            return await publish.publish_target(
                self.maker,
                self.redis,
                self.deps,
                target_id=target_id,
                will_retry=will_retry,
                now=now,
            )

    async def poll(
        self, target_id: uuid.UUID, n: int, *, now: datetime | None = None
    ) -> publish.Outcome:
        with workspace_scope(self.wid):
            return await publish.poll_container(
                self.maker, self.redis, self.deps, target_id=target_id, n=n, now=now
            )

    async def poll_until_done(self, target_id: uuid.UUID, *, first: int = 1) -> list[str]:
        """Polls from ``first`` while they say "waiting"; their outcomes."""
        outcomes: list[str] = []
        n = first
        while True:
            outcome = await self.poll(target_id, n)
            outcomes.append(outcome)
            if outcome != "waiting" or n > 20:
                return outcomes
            n += 1

    async def first_comment(
        self, target_id: uuid.UUID, *, will_retry: Callable[[PlatformError], bool] = never
    ) -> str:
        with workspace_scope(self.wid):
            return await publish.post_first_comment(
                self.maker, self.redis, self.deps, target_id=target_id, will_retry=will_retry
            )

    async def sweep(self, now: datetime | None = None) -> dict[str, int]:
        return await publish_jobs.sweep_stuck(self.maker, self.redis, now)

    # ---- reading rows

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def target(self, target_id: uuid.UUID) -> dict[str, Any]:
        [row] = await self.rows("SELECT * FROM scheduled_post_targets WHERE id = :id", id=target_id)
        return row

    async def post_row(self, post_id: uuid.UUID) -> dict[str, Any]:
        [row] = await self.rows("SELECT * FROM scheduled_posts WHERE id = :id", id=post_id)
        return row

    async def set(self, table: str, row_id: uuid.UUID, **values: Any) -> None:
        assignments = ", ".join(f"{name} = :{name}" for name in values)
        async with self.engine.begin() as conn:
            await conn.execute(
                text(f"UPDATE {table} SET {assignments} WHERE id = :id"),  # noqa: S608
                {**values, "id": row_id},
            )

    async def account(self, account_id: uuid.UUID) -> SocialAccount:
        [row] = await self.rows(
            "SELECT platform_account_id, username FROM social_accounts WHERE id = :id",
            id=account_id,
        )
        return SocialAccount(
            platform="instagram",
            platform_account_id=row["platform_account_id"],
            username=row["username"],
        )

    async def notifications(self) -> list[dict[str, Any]]:
        return await self.rows(
            "SELECT type, severity, title, body, link, dedupe_key FROM notifications"
            " WHERE workspace_id = :w ORDER BY created_at",
            w=self.wid,
        )


async def make_desk(engine: AsyncEngine, redis: Redis, deps: PlatformDeps) -> Desk:
    wid = await make_workspace(engine)
    await add_owner_member(engine, wid)
    first = await make_account(engine, wid, username="maple.bakery")
    second = await make_account(engine, wid, username="maple.cafe")
    return Desk(engine, redis, deps, wid, [first, second])
