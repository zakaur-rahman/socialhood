"""T4.4 and F-12: comment intake and comment automations (FR-AUT-01, FR-AUT-05, FR-AUT-08,
FR-AUT-10, FR-AUT-14, FR-AUT-18): the comment, its commenter and post are stored once; the public
reply variation goes out at once and the private reply through the account's queue; a failed
private reply never stops the public reply; post scopes, any-comment triggers and cooldowns."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any

import httpx
import pytest
import respx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.media import MediaItem
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.sandbox import outbox
from socialhood.security.crypto import TokenCipher
from socialhood.services.automations import posts
from socialhood.services.automations.runtime import Outcome
from socialhood.services.webhook_processing import process_event
from socialhood.settings import Settings
from tests.support.api import TOKEN_KEY
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_account
from tests.support.ingest import ACCOUNT_REF, deliver, jobs, sessions
from tests.support.instagram import GRAPH, fixture
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

LINK_REPLIES = ["Sent you a DM, {username}!", "Check your inbox!"]


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


async def link_automation(world: World, **values: Any) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "trigger": "comment_keyword",
        "message_text": "Here's the link, {username}!",
        "public_reply_texts": LINK_REPLIES,
        "message_buttons": [{"title": "Shop", "url": "https://maple.example/shop"}],
    }
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        **{**defaults, **values},
    )


def sandbox_comment(account_ref: str, comment_id: str, **value: Any) -> dict[str, Any]:
    change = {
        "id": comment_id,
        "text": "LINK please",
        "from": {"id": "990000000000002", "username": "curious.cat"},
        "media": {"id": f"{account_ref}_post_0", "media_product_type": "FEED"},
        **value,
    }
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_ref,
                "time": int(datetime.now(UTC).timestamp()),
                "changes": [{"field": "comments", "value": change}],
            }
        ],
    }


# ---------------------------------------------------------------- intake (F-12)


async def test_a_comment_is_stored_once_with_its_commenter_and_post(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    linked: list[MediaItem] = []

    async def spy(session: Any, item: MediaItem) -> None:
        linked.append(item)

    monkeypatch.setattr(posts, "on_new_media_item", spy)
    [acct] = await world.rows(
        "SELECT platform_account_id FROM social_accounts WHERE id = :id", id=world.account_id
    )
    ref = acct["platform_account_id"]
    body = sandbox_comment(ref, "18000000000000077")
    maker = sessions(world.engine)

    assert await deliver(maker, world.redis, body) == [WebhookStatus.PROCESSED]
    [comment] = await world.rows("SELECT * FROM comments")
    assert (comment["text"], comment["author_username"], comment["analysis_status"]) == (
        "LINK please",
        "curious.cat",
        "pending",
    )
    [contact] = await world.rows("SELECT * FROM contacts")
    assert (contact["platform_user_id"], contact["username"]) == ("990000000000002", "curious.cat")
    assert comment["contact_id"] == contact["id"]
    [post] = await world.rows("SELECT * FROM media_items")
    assert post["platform_media_id"] == f"{ref}_post_0"
    assert post["caption"] == "New autumn collection is in. Which colour is your favourite?"
    assert comment["media_item_id"] == post["id"]
    assert [item.id for item in linked] == [post["id"]]
    assert await jobs("run_automation") == []  # no comment automation on the account

    # A second delivery of the same comment stores nothing and triggers nothing.
    assert await deliver(maker, world.redis, body, copy="again") == [WebhookStatus.IGNORED]
    assert len(await world.rows("SELECT id FROM comments")) == 1
    assert len(linked) == 1

    # The account's own comments (its public replies come back) are skipped.
    own = sandbox_comment(
        ref,
        "18000000000000078",
        **{"from": {"id": "17841499999999999", "username": "maple.bakery"}},
    )
    assert await deliver(maker, world.redis, own) == [WebhookStatus.IGNORED]
    own_by_id = sandbox_comment(ref, "18000000000000079", **{"from": {"id": ref}})
    assert await deliver(maker, world.redis, own_by_id) == [WebhookStatus.IGNORED]
    assert len(await world.rows("SELECT id FROM comments")) == 1


async def test_a_comment_enqueues_the_account_s_comment_automations(world: World) -> None:
    await link_automation(world)
    comment_id = await world.comment("LINK")
    [job] = await jobs("run_automation")
    assert job["queueing_lock"] == f"automation:comment:{comment_id}"
    assert job["args"]["kind"] == "comment"


async def test_a_post_we_never_synced_is_fetched_from_instagram(
    world: World, engine: AsyncEngine
) -> None:
    account = await make_account(engine, world.wid, platform_account_id=ACCOUNT_REF)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET access_token_enc = :t WHERE id = :id"),
            {"t": TokenCipher([TOKEN_KEY]).encrypt("IGQVJtoken"), "id": account},
        )
    media = fixture("media_list.json")["data"][0] | {"id": "18100000000000001"}
    maker = sessions(engine)
    with respx.mock(assert_all_called=False) as router:
        route = router.get(url__regex=rf"{GRAPH}/v[\d.]+/18100000000000001(\?.*)?$").mock(
            side_effect=[
                httpx.Response(500, json={"error": {"code": 2}}),
                httpx.Response(200, json=media),
            ]
        )
        # Instagram is down: the event fails for now and is retried by the webhook job.
        with pytest.raises(PlatformError):
            await deliver(maker, world.redis, "webhook_comment_changes.json")
        assert await world.rows("SELECT id FROM comments") == []
        [event] = await world.rows("SELECT id FROM webhook_events")
        assert await process_event(maker, event["id"], world.redis) == WebhookStatus.PROCESSED
        assert route.call_count == 2
    [post] = await world.rows("SELECT * FROM media_items WHERE social_account_id = :id", id=account)
    assert post["caption"] == media.get("caption")
    assert post["synced_at"] is not None


async def test_a_post_instagram_refuses_is_stored_from_the_event(
    world: World, engine: AsyncEngine
) -> None:
    await make_account(engine, world.wid, platform_account_id=ACCOUNT_REF)  # no token
    assert await deliver(sessions(engine), world.redis, "webhook_comment_changes.json") == [
        WebhookStatus.PROCESSED
    ]
    [post] = await world.rows("SELECT * FROM media_items")
    assert (post["platform_media_id"], post["synced_at"]) == ("18100000000000001", None)


# ---------------------------------------------------------------- the runtime


async def test_a_keyword_comment_gets_a_public_reply_now_and_a_dm_from_the_queue(
    world: World,
) -> None:
    await link_automation(world)
    comment_id = await world.comment("LINK please 🙏", username="curious.cat")
    assert comment_id is not None

    assert await world.run("comment", comment_id) is Outcome.FIRED
    run = await world.run_row()
    assert (run["result"], run["matched_keyword"], run["trigger_comment_id"]) == (
        "queued",
        "link",
        comment_id,
    )
    [reply] = outbox.COMMENT_REPLIES
    assert reply.text in ("Sent you a DM, curious.cat!", "Check your inbox!")
    assert run["public_reply_variant"] == [
        "Sent you a DM, curious.cat!",
        "Check your inbox!",
    ].index(reply.text)
    assert run["public_reply_platform_id"] == reply.platform_comment_id
    [comment] = await world.rows("SELECT * FROM comments")
    assert (comment["our_reply_platform_id"], comment["our_reply_text"]) == (
        reply.platform_comment_id,
        reply.text,
    )
    assert comment["our_replied_at"] is not None
    assert not outbox.PRIVATE_REPLIES  # waits in the queue
    [drain_job] = await jobs("drain_private_replies")
    assert drain_job["queueing_lock"] == f"prq:{world.account_id}"

    result = await world.drain()
    assert (result.sent, result.failed, result.remaining, result.next_in_s) == (1, 0, 0, None)
    [private] = outbox.PRIVATE_REPLIES
    assert private.recipient_ref == comment["platform_comment_id"]
    assert private.message.text == "Here's the link, curious.cat!"
    assert [b.title for b in private.message.buttons] == ["Shop"]

    run = await world.run_row()
    [dm] = await world.rows("SELECT * FROM messages")
    assert (run["result"], run["private_reply_message_id"]) == ("sent", dm["id"])
    assert (dm["direction"], dm["source"], dm["status"]) == ("outbound", "automation", "sent")
    assert dm["platform_message_id"] == private.platform_message_id
    assert dm["automation_run_id"] == run["id"]
    assert dm["buttons"] == [{"title": "Shop", "url": "https://maple.example/shop"}]
    [conv] = await world.rows("SELECT * FROM conversations")
    assert (conv["contact_id"], conv["id"]) == (comment["contact_id"], dm["conversation_id"])
    assert conv["last_message_source"] == "automation"
    [comment] = await world.rows("SELECT * FROM comments")
    assert comment["private_reply_message_id"] == dm["id"]

    # Re-running the same event sends nothing.
    assert await world.run("comment", comment_id) is Outcome.ALREADY_RAN
    assert (await world.drain()).sent == 0
    assert (len(outbox.COMMENT_REPLIES), len(outbox.PRIVATE_REPLIES)) == (1, 1)


async def test_a_failed_private_reply_still_posts_the_public_reply(world: World) -> None:
    await link_automation(world)
    comment_id = await world.comment("link")
    assert comment_id is not None
    outbox.fail_next("recipient_unavailable", kind="private_reply")

    await world.run("comment", comment_id)
    assert len(outbox.COMMENT_REPLIES) == 1
    assert (await world.drain()).failed == 1

    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("partial", "recipient_unavailable")
    assert run["error_message"] == "DM: This person can't receive messages right now."
    assert run["public_reply_platform_id"] is not None
    [dm] = await world.rows("SELECT status, error_code FROM messages")
    assert dm == {"status": "failed", "error_code": "recipient_unavailable"}


async def test_a_failed_public_reply_still_sends_the_dm(world: World) -> None:
    await link_automation(world)
    comment_id = await world.comment("link")
    assert comment_id is not None
    outbox.fail_next("platform_rejected", kind="comment_reply")

    await world.run("comment", comment_id)
    assert (await world.run_row())["result"] == "queued"
    assert (await world.drain()).sent == 1
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("partial", "platform_rejected")
    assert run["error_message"].startswith("Public reply: Instagram rejected this")


async def test_when_both_fail_the_run_fails(world: World) -> None:
    await link_automation(world)
    comment_id = await world.comment("link")
    assert comment_id is not None
    outbox.fail_next("platform_rejected", kind="comment_reply")
    outbox.fail_next("recipient_unavailable", kind="private_reply")
    await world.run("comment", comment_id)
    await world.drain()
    run = await world.run_row()
    assert run["result"] == "failed"
    assert "Public reply:" in run["error_message"]
    assert "DM:" in run["error_message"]


async def test_public_reply_variations_never_repeat_on_a_post(world: World) -> None:
    await link_automation(world, cooldown_hours=0)
    for _ in range(8):
        comment_id = await world.comment("link")
        assert comment_id is not None
        await world.run("comment", comment_id)
    used = [r.text for r in outbox.COMMENT_REPLIES]
    assert len(used) == 8
    assert all(a != b for a, b in pairwise(used))


async def test_post_scopes(world: World, engine: AsyncEngine) -> None:
    chosen = await make_media_item(
        engine, workspace_id=world.wid, account_id=world.account_id, platform_media_id="chosen"
    )
    await make_media_item(
        engine, workspace_id=world.wid, account_id=world.account_id, platform_media_id="other"
    )
    await link_automation(world, post_scope="selected", media_item_ids=(chosen,), cooldown_hours=0)

    elsewhere = await world.comment("link", media_ref="other")
    assert elsewhere is not None
    assert await world.run("comment", elsewhere) is Outcome.SKIPPED
    on_post = await world.comment("link", media_ref="chosen")
    assert on_post is not None
    assert await world.run("comment", on_post) is Outcome.FIRED

    # "Next post" automations answer only on the post T4.7 linked them to.
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE automations SET post_scope = 'next_post'"))
    later = await world.comment("link", media_ref="chosen")
    assert later is not None
    assert await world.run("comment", later) is Outcome.FIRED
    elsewhere_again = await world.comment("link", media_ref="other")
    assert elsewhere_again is not None
    assert await world.run("comment", elsewhere_again) is Outcome.SKIPPED


async def test_any_comment_answers_top_level_comments_and_keywords_answer_replies(
    world: World,
) -> None:
    await link_automation(world, trigger="comment_any", keywords=(), cooldown_hours=0)
    top = await world.comment("Love this!")
    assert top is not None
    assert await world.run("comment", top) is Outcome.FIRED
    reply = await world.comment("me too", parent="17900000000000001")
    assert reply is not None
    assert await world.run("comment", reply) is Outcome.NO_MATCH

    await link_automation(world, keywords=("link",), cooldown_hours=0)
    keyword_reply = await world.comment("link?", parent="17900000000000001")
    assert keyword_reply is not None
    assert await world.run("comment", keyword_reply) is Outcome.FIRED
    [run] = await world.rows(
        "SELECT matched_keyword FROM automation_runs WHERE trigger_comment_id = :id",
        id=keyword_reply,
    )
    assert run["matched_keyword"] == "link"


async def test_public_reply_only_never_dms(world: World) -> None:
    await link_automation(world, surge_order="public_only")
    comment_id = await world.comment("link")
    assert comment_id is not None
    assert await world.run("comment", comment_id) is Outcome.FIRED
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("sent", None)
    assert len(outbox.COMMENT_REPLIES) == 1
    assert await jobs("drain_private_replies") == []
    assert not outbox.PRIVATE_REPLIES


async def test_one_answer_per_commenter_per_cooldown(world: World) -> None:
    await link_automation(world)
    first = await world.comment("link", author="990000000000042")
    second = await world.comment("link again", author="990000000000042")
    assert first is not None
    assert second is not None
    assert await world.run("comment", first) is Outcome.FIRED
    assert await world.run("comment", second) is Outcome.SKIPPED
    [skipped] = await world.rows(
        "SELECT result FROM automation_runs WHERE trigger_comment_id = :id", id=second
    )
    assert skipped["result"] == "skipped_cooldown"
    assert len(outbox.COMMENT_REPLIES) == 1


async def test_a_comment_past_seven_days_is_skipped(world: World) -> None:
    await link_automation(world)
    old = await world.comment("link", at=datetime.now(UTC) - timedelta(days=8))
    assert old is not None
    assert await world.run("comment", old) is Outcome.SKIPPED
    [run] = await world.rows("SELECT result, error_message FROM automation_runs")
    assert run == {"result": "skipped_expired", "error_message": "Instagram's 7-day limit passed"}
    assert not outbox.COMMENT_REPLIES
