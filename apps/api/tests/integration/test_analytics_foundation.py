"""P6 foundation (§5.6; TR-AI-11, FR-ANL-01): the comment_analyses, post_metric_snapshots and
account_daily_metrics keys and checks, through the factories every P6 test uses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.analytics import make_account_day, make_comment_analysis, make_snapshot
from tests.support.automations import make_comment, make_media_item
from tests.support.inbox import make_account, make_workspace


@dataclass(frozen=True)
class Post:
    workspace_id: uuid.UUID
    account_id: uuid.UUID
    post_id: uuid.UUID


@pytest.fixture
async def post(engine: AsyncEngine, clean_db: None) -> Post:
    wid = await make_workspace(engine)
    account = await make_account(engine, wid)
    item = await make_media_item(engine, workspace_id=wid, account_id=account)
    return Post(wid, account, item)


async def _scalar(engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def test_each_window_is_stored_once_per_post(engine: AsyncEngine, post: Post) -> None:
    on = {"workspace_id": post.workspace_id, "media_item_id": post.post_id}
    await make_snapshot(engine, window="1h", metrics={"likes": 3, "comments": 1}, **on)
    await make_snapshot(engine, window="24h", **on)
    with pytest.raises(IntegrityError, match="uq_post_metric_snapshots_media_item_id_window"):
        await make_snapshot(engine, window="24h", **on)
    with pytest.raises(IntegrityError, match="ck_post_metric_snapshots_window"):
        await make_snapshot(engine, window="2h", **on)
    windows = await _scalar(
        engine,
        'SELECT array_agg("window" ORDER BY captured_at) FROM post_metric_snapshots'
        " WHERE media_item_id = :p",
        p=post.post_id,
    )
    assert windows == ["1h", "24h"]


async def test_one_account_row_per_day(engine: AsyncEngine, post: Post) -> None:
    on = {"workspace_id": post.workspace_id, "account_id": post.account_id}
    day = date(2026, 9, 28)
    await make_account_day(engine, day=day, **on)
    with pytest.raises(IntegrityError, match="uq_account_daily_metrics_social_account_id_date"):
        await make_account_day(engine, day=day, **on)
    # Without the insights scope: followers only, empty metrics.
    await make_account_day(engine, day=day + timedelta(days=1), metrics={}, **on)


async def test_one_analysis_per_comment_with_known_values(engine: AsyncEngine, post: Post) -> None:
    on = {"workspace_id": post.workspace_id, "account_id": post.account_id}
    comment = await make_comment(engine, media_item_id=post.post_id, **on)
    await make_comment_analysis(engine, workspace_id=post.workspace_id, comment_id=comment)
    assert await _scalar(
        engine,
        "SELECT a.media_item_id = c.media_item_id AND c.analysis_status = 'done'"
        " FROM comment_analyses a JOIN comments c ON c.id = a.comment_id WHERE c.id = :c",
        c=comment,
    )
    with pytest.raises(IntegrityError, match="uq_comment_analyses_comment_id"):
        await make_comment_analysis(engine, workspace_id=post.workspace_id, comment_id=comment)

    other = await make_comment(engine, media_item_id=post.post_id, **on)
    for bad, check in (
        ({"sentiment": "angry"}, "sentiment"),
        ({"intent": "question"}, "intent"),
        ({"sentiment_score": 1.5}, "sentiment_score"),
        ({"topic": ""}, "topic_length"),
    ):
        with pytest.raises(IntegrityError, match=f"ck_comment_analyses_{check}"):
            await make_comment_analysis(
                engine, workspace_id=post.workspace_id, comment_id=other, **bad
            )
    await make_comment_analysis(
        engine, workspace_id=post.workspace_id, comment_id=other, topic=None, is_spam=True
    )


async def test_a_deleted_post_takes_its_analyses_and_snapshots(
    engine: AsyncEngine, post: Post
) -> None:
    on = {"workspace_id": post.workspace_id, "account_id": post.account_id}
    comment = await make_comment(engine, media_item_id=post.post_id, **on)
    await make_comment_analysis(engine, workspace_id=post.workspace_id, comment_id=comment)
    await make_snapshot(engine, workspace_id=post.workspace_id, media_item_id=post.post_id)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM media_items WHERE id = :p"), {"p": post.post_id})
    for table in ("comment_analyses", "post_metric_snapshots"):
        count = await _scalar(
            engine,
            f"SELECT count(*) FROM {table} WHERE workspace_id = :w",  # noqa: S608
            w=post.workspace_id,
        )
        assert count == 0, table
