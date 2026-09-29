"""Helpers for the comment intelligence tests (T6.1, T6.2, T6.3): a workspace with a sandbox
account (tests/support/runtime.World), its posts and comments, and the P6 jobs' bodies run
in-process like a worker would."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks import comments as comment_tasks
from socialhood.services.comments import analysis, backfill, private_replies, summaries
from socialhood.services.sync import sync_account_media
from socialhood.settings import Settings
from tests.support.automations import make_media_item
from tests.support.runtime import World


@dataclass
class Comments:
    world: World

    @property
    def wid(self) -> uuid.UUID:
        return self.world.wid

    @property
    def account_id(self) -> uuid.UUID:
        return self.world.account_id

    @property
    def settings(self) -> Settings:
        return self.world.deps.settings

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        return await self.world.rows(sql, **params)

    async def one(self, sql: str, **params: Any) -> dict[str, Any]:
        [row] = await self.rows(sql, **params)
        return row

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.world.engine.begin() as conn:
            await conn.execute(text(sql), params)

    async def account_ref(self) -> str:
        row = await self.one(
            "SELECT platform_account_id FROM social_accounts WHERE id = :id", id=self.account_id
        )
        return str(row["platform_account_id"])

    async def plan(self, plan: str) -> None:
        await self.execute(
            "INSERT INTO subscriptions (workspace_id, plan, status, billing_anchor_day)"
            " VALUES (:w, :p, 'active', 1)"
            " ON CONFLICT (workspace_id) DO UPDATE SET plan = :p",
            w=self.wid,
            p=plan,
        )

    async def post(self, **values: Any) -> uuid.UUID:
        return await make_media_item(
            self.world.engine, workspace_id=self.wid, account_id=self.account_id, **values
        )

    async def comment(self, text_: str, *, post: uuid.UUID, **values: Any) -> uuid.UUID:
        """A comment through the real webhook intake, on a stored post."""
        row = await self.one("SELECT platform_media_id FROM media_items WHERE id = :id", id=post)
        comment_id = await self.world.comment(text_, media_ref=row["platform_media_id"], **values)
        assert comment_id is not None
        return comment_id

    async def bulk_comments(self, post: uuid.UUID, count: int, *, prefix: str = "bulk") -> None:
        """``count`` pending comments written straight to the table, in arrival order."""
        await self.execute(
            "INSERT INTO comments (workspace_id, social_account_id, media_item_id,"
            " platform_comment_id, author_platform_user_id, author_username, text, commented_at,"
            " created_at)"
            " SELECT :w, :a, :m, :p || '_' || g, 'fan_' || (g % 997), 'fan' || (g % 997),"
            " 'comment number ' || g, now() - make_interval(secs => :n - g),"
            " now() + make_interval(secs => g / 1000.0)"
            " FROM generate_series(1, :n) g",
            w=self.wid,
            a=self.account_id,
            m=post,
            p=f"{prefix}_{post.hex[:8]}",
            n=count,
        )

    # ---- the jobs, as the worker runs them

    async def sync(self, *, now: datetime | None = None) -> int | None:
        return await sync_account_media(
            self.world.maker,
            self.world.deps,
            workspace_id=self.wid,
            account_id=self.account_id,
            now=now,
        )

    async def backfill(self, *, now: datetime | None = None) -> backfill.BackfillResult | None:
        return await backfill.backfill_comments(
            self.world.maker,
            self.world.redis,
            self.world.deps,
            workspace_id=self.wid,
            account_id=self.account_id,
            now=now,
        )

    async def analyze(
        self, *, now: datetime | None = None, max_batches: int = analysis.MAX_BATCHES_PER_RUN
    ) -> analysis.AccountRun:
        return await analysis.analyze_comments(
            self.world.maker,
            self.world.redis,
            self.settings,
            self.world.deps,
            workspace_id=self.wid,
            account_id=self.account_id,
            now=now,
            max_batches=max_batches,
        )

    async def summarize(
        self, post: uuid.UUID, *, now: datetime | None = None
    ) -> summaries.SummaryRun:
        return await summaries.summarize_post(
            self.world.maker,
            self.world.redis,
            self.settings,
            workspace_id=self.wid,
            media_item_id=post,
            now=now,
        )

    async def send_private_reply(
        self, comment_id: uuid.UUID, *, attempt: int = 0, now: datetime | None = None
    ) -> private_replies.Outcome:
        row = await self.one(
            "SELECT private_reply_message_id FROM comments WHERE id = :id", id=comment_id
        )
        with workspace_scope(self.wid):
            return await private_replies.send(
                self.world.maker,
                self.world.redis,
                self.world.deps,
                workspace_id=self.wid,
                comment_id=comment_id,
                message_id=row["private_reply_message_id"],
                attempt=attempt,
                will_retry=lambda error: False,
                now=now or datetime.now(UTC),
            )

    async def dispatch(self) -> int:
        return await comment_tasks.dispatch_analysis(self.world.maker)

    # ---- reading back

    async def stats(self, post: uuid.UUID) -> dict[str, int]:
        row = await self.one("SELECT comment_stats FROM media_items WHERE id = :id", id=post)
        return dict(row["comment_stats"])

    async def statuses(self) -> dict[str, int]:
        rows = await self.rows(
            "SELECT analysis_status, count(*) AS n FROM comments WHERE workspace_id = :w"
            " GROUP BY analysis_status",
            w=self.wid,
        )
        return {row["analysis_status"]: int(row["n"]) for row in rows}


def reading(
    number: str,
    *,
    sentiment: str = "neutral",
    score: float = 0.0,
    intent: str = "other",
    spam: bool = False,
    topic: str | None = None,
) -> dict[str, Any]:
    """One item of a comment_analysis answer."""
    return {
        "id": number,
        "sentiment": sentiment,
        "sentiment_score": score,
        "intent": intent,
        "is_spam": spam,
        "topic": topic,
    }
