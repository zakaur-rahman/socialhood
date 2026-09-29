"""P7 foundation (§5.7; FR-PUB-01, FR-PUB-06, FR-PUB-09, FR-PUB-12, FR-AUT-18): the keys, checks
and cascades of scheduled_posts, scheduled_post_assets, scheduled_post_targets, posting_slots and
hashtag_groups, and the foreign keys that waited for them, through the factories every P7 test
uses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import time
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.automations import AutomationPost
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_account, make_asset, make_workspace
from tests.support.publishing import make_hashtag_group, make_posting_slot, make_scheduled_post


@dataclass(frozen=True)
class Shop:
    workspace_id: uuid.UUID
    account_id: uuid.UUID


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None) -> Shop:
    wid = await make_workspace(engine)
    return Shop(wid, await make_account(engine, wid))


async def _scalar(engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def _execute(engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def test_a_post_keeps_its_assets_in_order_and_one_target_per_account(
    engine: AsyncEngine, shop: Shop
) -> None:
    on = {"workspace_id": shop.workspace_id}
    image = await make_asset(engine, purpose="post", **on)
    video = await make_asset(engine, purpose="post", resource_type="video", fmt="mp4", **on)
    second = await make_account(engine, shop.workspace_id, username="second.shop")
    post = await make_scheduled_post(
        engine,
        account_ids=[shop.account_id, second],
        asset_ids=[video, image],
        caption_overrides={second: "Only here"},
        **on,
    )
    assert await _scalar(
        engine,
        "SELECT array_agg(media_asset_id ORDER BY position) FROM scheduled_post_assets"
        " WHERE scheduled_post_id = :p",
        p=post.id,
    ) == [video, image]
    assert await _scalar(engine, "SELECT format FROM scheduled_posts WHERE id = :p", p=post.id) == (
        "carousel"
    )
    assert set(post.target_ids) == {shop.account_id, second}

    with pytest.raises(IntegrityError, match="uq_scheduled_post_assets_scheduled_post_id_position"):
        await _execute(
            engine,
            "INSERT INTO scheduled_post_assets"
            " (workspace_id, scheduled_post_id, media_asset_id, position)"
            " VALUES (:w, :p, :a, 0)",
            w=shop.workspace_id,
            p=post.id,
            a=image,
        )
    with pytest.raises(IntegrityError, match="ck_scheduled_post_assets_position"):
        await _execute(
            engine,
            "INSERT INTO scheduled_post_assets"
            " (workspace_id, scheduled_post_id, media_asset_id, position)"
            " VALUES (:w, :p, :a, 10)",
            w=shop.workspace_id,
            p=post.id,
            a=image,
        )
    with pytest.raises(
        IntegrityError, match="uq_scheduled_post_targets_scheduled_post_id_social_account_id"
    ):
        await _execute(
            engine,
            "INSERT INTO scheduled_post_targets"
            " (workspace_id, scheduled_post_id, social_account_id) VALUES (:w, :p, :a)",
            w=shop.workspace_id,
            p=post.id,
            a=shop.account_id,
        )
    # An asset used by a post can't be deleted from the library.
    with pytest.raises(IntegrityError, match="fk_scheduled_post_assets_media_asset_id"):
        await _execute(engine, "DELETE FROM media_assets WHERE id = :a", a=image)


@pytest.mark.parametrize(
    ("values", "check"),
    [
        ({"status": "queued"}, "status"),
        ({"format": "story"}, "format"),
        ({"caption": "x" * 2201}, "caption_length"),
        ({"first_comment": ""}, "first_comment_length"),
        ({"status": "scheduled", "format": None}, "schedulable"),
    ],
)
async def test_post_checks(
    engine: AsyncEngine, shop: Shop, values: dict[str, Any], check: str
) -> None:
    with pytest.raises(IntegrityError, match=f"ck_scheduled_posts_{check}"):
        await make_scheduled_post(engine, workspace_id=shop.workspace_id, **values)


async def test_a_draft_needs_no_time_or_media_but_a_scheduled_post_does(
    engine: AsyncEngine, shop: Shop
) -> None:
    await make_scheduled_post(engine, workspace_id=shop.workspace_id, asset_ids=[], caption="")
    await make_scheduled_post(engine, workspace_id=shop.workspace_id, status="scheduled")
    post = await make_scheduled_post(engine, workspace_id=shop.workspace_id)
    with pytest.raises(IntegrityError, match="ck_scheduled_posts_schedulable"):
        await _execute(
            engine, "UPDATE scheduled_posts SET status = 'scheduled' WHERE id = :p", p=post.id
        )


@pytest.mark.parametrize(
    ("status", "values", "check"),
    [
        ("sent", {}, "status"),
        ("published", {"platform_media_id": None}, "published_media"),
        ("pending", {"attempts": -1}, "counters"),
        ("pending", {"child_container_ids": [str(i) for i in range(11)]}, "children"),
        ("pending", {"caption_override": "x" * 2201}, "caption_override_length"),
    ],
)
async def test_target_checks(
    engine: AsyncEngine, shop: Shop, status: str, values: dict[str, Any], check: str
) -> None:
    with pytest.raises(IntegrityError, match=f"ck_scheduled_post_targets_{check}"):
        await make_scheduled_post(
            engine,
            workspace_id=shop.workspace_id,
            account_ids=[shop.account_id],
            status="scheduled",
            target_status=status,
            target_values=values,
        )


async def test_posting_times_are_unique_whole_minutes_on_weekdays(
    engine: AsyncEngine, shop: Shop
) -> None:
    on = {"workspace_id": shop.workspace_id, "account_id": shop.account_id}
    await make_posting_slot(engine, weekday=0, local_time=time(18, 0), **on)
    await make_posting_slot(engine, weekday=2, local_time=time(18, 0), **on)
    with pytest.raises(
        IntegrityError, match="uq_posting_slots_social_account_id_weekday_local_time"
    ):
        await make_posting_slot(engine, weekday=2, local_time=time(18, 0), **on)
    with pytest.raises(IntegrityError, match="ck_posting_slots_weekday"):
        await make_posting_slot(engine, weekday=7, **on)
    with pytest.raises(IntegrityError, match="ck_posting_slots_whole_minute"):
        await make_posting_slot(engine, local_time=time(18, 0, 30), **on)


async def test_hashtag_groups_are_named_once_and_stored_normalised(
    engine: AsyncEngine, shop: Shop
) -> None:
    on = {"workspace_id": shop.workspace_id}
    await make_hashtag_group(engine, name="Summer sale", **on)
    with pytest.raises(IntegrityError, match="uq_hashtag_groups_workspace_id_lower_name"):
        await make_hashtag_group(engine, name="SUMMER SALE", **on)
    for hashtags, check in (
        ([], "hashtags_count"),
        ([f"tag{i}" for i in range(31)], "hashtags_count"),
        (["Summer"], "hashtags_normalized"),
        (["#summer"], "hashtags_normalized"),
    ):
        with pytest.raises(IntegrityError, match=f"ck_hashtag_groups_{check}"):
            await make_hashtag_group(
                engine, name=f"Group {check} {len(hashtags)}", hashtags=hashtags, **on
            )
    with pytest.raises(IntegrityError, match="ck_hashtag_groups_name_length"):
        await make_hashtag_group(engine, name="x" * 41, **on)
    # Another workspace may use the same name.
    other = await make_workspace(engine)
    await make_hashtag_group(engine, workspace_id=other, name="Summer sale")


async def test_deleting_a_post_takes_its_rows_and_links_but_keeps_the_published_post(
    engine: AsyncEngine, shop: Shop
) -> None:
    post = await make_scheduled_post(
        engine,
        workspace_id=shop.workspace_id,
        account_ids=[shop.account_id],
        status="published",
        target_status="published",
    )
    target = post.target_ids[shop.account_id]
    item = await make_media_item(engine, workspace_id=shop.workspace_id, account_id=shop.account_id)
    await _execute(
        engine, "UPDATE media_items SET published_target_id = :t WHERE id = :m", t=target, m=item
    )
    automation = await make_automation(
        engine,
        workspace_id=shop.workspace_id,
        account_id=shop.account_id,
        trigger="comment_keyword",
    )
    with workspace_scope(shop.workspace_id):
        async with AsyncSession(engine) as session:
            session.add(AutomationPost(automation_id=automation, scheduled_post_id=post.id))
            await session.commit()
    # One media item per target.
    other = await make_media_item(
        engine, workspace_id=shop.workspace_id, account_id=shop.account_id
    )
    with pytest.raises(IntegrityError, match="uq_media_items_published_target_id"):
        await _execute(
            engine,
            "UPDATE media_items SET published_target_id = :t WHERE id = :m",
            t=target,
            m=other,
        )

    await _execute(engine, "DELETE FROM scheduled_posts WHERE id = :p", p=post.id)
    for table in ("scheduled_post_assets", "scheduled_post_targets", "automation_posts"):
        count = await _scalar(
            engine,
            f"SELECT count(*) FROM {table} WHERE workspace_id = :w",  # noqa: S608
            w=shop.workspace_id,
        )
        assert count == 0, table
    assert await _scalar(
        engine, "SELECT published_target_id IS NULL FROM media_items WHERE id = :m", m=item
    )


async def test_links_and_posts_must_point_at_real_rows(engine: AsyncEngine, shop: Shop) -> None:
    automation = await make_automation(
        engine,
        workspace_id=shop.workspace_id,
        account_id=shop.account_id,
        trigger="comment_keyword",
    )
    with pytest.raises(IntegrityError, match="fk_automation_posts_scheduled_post_id"):
        await _execute(
            engine,
            "INSERT INTO automation_posts (workspace_id, automation_id, scheduled_post_id)"
            " VALUES (:w, :a, :p)",
            w=shop.workspace_id,
            a=automation,
            p=uuid.uuid4(),
        )
    item = await make_media_item(engine, workspace_id=shop.workspace_id, account_id=shop.account_id)
    with pytest.raises(IntegrityError, match="fk_media_items_published_target_id"):
        await _execute(
            engine,
            "UPDATE media_items SET published_target_id = :t WHERE id = :m",
            t=uuid.uuid4(),
            m=item,
        )
