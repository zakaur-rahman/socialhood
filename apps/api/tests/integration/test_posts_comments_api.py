"""T6.3: the posts and comments API (FR-CMT-03, FR-CMT-04, UX-SCR-05, TR-API-05). Done when: a
second private reply to the same comment is refused. Plus: post detail, the comment list and its
filter chips, the summary refresh, public replies with Idempotency-Key, private replies through the
private-reply bucket, hide, unhide and delete, and platform refusals. Other workspaces' posts and
comments are covered by the tenancy suite (tests/tenancy)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.platforms.deps import deps_from
from socialhood.platforms.sandbox import outbox
from socialhood.services.comments import private_replies
from socialhood.services.comments.actions import DELETED, ONE_PER_COMMENT, TOO_OLD
from tests.support.analysis import use_credits
from tests.support.analytics import make_comment_analysis
from tests.support.api import Clerk, sign_in
from tests.support.automations import make_automation, make_comment, make_media_item
from tests.support.ingest import jobs, stream
from tests.support.sending import clean_outbox

CHIPS = ("all", "positive", "neutral", "negative", "questions", "buying", "spam", "hidden")


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@dataclass
class Shop:
    app: FastAPI
    client: httpx.AsyncClient
    engine: AsyncEngine
    redis: Redis
    clerk_id: str
    wid: str
    account_id: str
    headers: dict[str, str]

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def one(self, sql: str, **params: Any) -> dict[str, Any]:
        [row] = await self.rows(sql, **params)
        return row

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)

    async def post(self, **values: Any) -> uuid.UUID:
        return await make_media_item(
            self.engine, workspace_id=self.wid, account_id=self.account_id, **values
        )

    async def comment(self, post: uuid.UUID, text_: str = "Nice!", **values: Any) -> uuid.UUID:
        return await make_comment(
            self.engine,
            workspace_id=self.wid,
            account_id=self.account_id,
            media_item_id=post,
            text=text_,
            **values,
        )

    async def analyse(self, comment_id: uuid.UUID, **values: Any) -> None:
        await make_comment_analysis(
            self.engine, workspace_id=self.wid, comment_id=comment_id, **values
        )

    def url(self, path: str) -> str:
        return f"/v1/w/{self.wid}{path}"

    async def get(self, path: str, **params: Any) -> httpx.Response:
        return await self.client.get(self.url(path), params=params, headers=self.headers)

    async def post_json(
        self, path: str, body: dict[str, Any] | None = None, *, key: str | None = None
    ) -> httpx.Response:
        headers = dict(self.headers)
        if key is not None:
            headers["Idempotency-Key"] = key
        return await self.client.post(self.url(path), json=body, headers=headers)

    async def send_private_reply(
        self, comment_id: uuid.UUID, *, now: datetime | None = None
    ) -> private_replies.Outcome:
        """send_private_reply as the worker runs it (no retries left)."""
        row = await self.one(
            "SELECT private_reply_message_id FROM comments WHERE id = :id", id=comment_id
        )
        wid = uuid.UUID(self.wid)
        with workspace_scope(wid):
            return await private_replies.send(
                self.app.state.sessionmaker,
                self.redis,
                deps_from(self.app.state.http, self.app.state.settings),
                workspace_id=wid,
                comment_id=comment_id,
                message_id=row["private_reply_message_id"],
                will_retry=lambda error: False,
                now=now,
            )


@pytest.fixture
async def shop(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> Shop:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com", first_name="Asha")
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)
    created = await client.post(f"/v1/w/{wid}/dev/sandbox/accounts", headers=headers)
    assert created.status_code == 201, created.text
    return Shop(
        app,
        client,
        engine,
        app.state.redis,
        clerk_id,
        wid,
        created.json()["id"],
        headers,
    )


# ---------------------------------------------------------------- post detail and comments


async def test_post_detail_has_its_counts_summary_and_largest_topics_first(shop: Shop) -> None:
    post = await shop.post(caption="Linen shirts")
    stats = {"total": 12, "analysed": 10, "positive": 5, "neutral": 2, "negative": 1, "spam": 2}
    topics = [
        {"label": "sizes", "count": 2, "positive": 1, "neutral": 1, "negative": 0},
        {"label": "price", "count": 5, "positive": 3, "neutral": 1, "negative": 1},
    ]
    await shop.execute(
        "UPDATE media_items SET comment_stats = CAST(:s AS jsonb), topics = CAST(:t AS jsonb),"
        " summary = 'People love the fit.', summary_updated_at = now() WHERE id = :id",
        s=json.dumps(stats),
        t=json.dumps(topics),
        id=post,
    )

    response = await shop.get(f"/posts/{post}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["caption"], body["summary"]) == (
        str(post),
        "Linen shirts",
        "People love the fit.",
    )
    assert body["stats"] == stats
    assert [t["label"] for t in body["topics"]] == ["price", "sizes"]
    assert body["summary_updated_at"] is not None
    assert (await shop.get(f"/posts/{uuid.uuid4()}")).status_code == 404


async def test_the_comment_list_is_newest_first_and_narrowed_by_each_chip(shop: Shop) -> None:
    post = await shop.post()
    t0 = datetime.now(UTC) - timedelta(hours=1)
    contact_id = uuid.uuid4()
    await shop.execute(
        "INSERT INTO contacts (id, workspace_id, social_account_id, platform_user_id, username,"
        " profile_picture_url) VALUES (:id, :w, :a, '990000000000077', 'fan', 'https://pic/1.jpg')",
        id=contact_id,
        w=shop.wid,
        a=shop.account_id,
    )
    made: dict[str, uuid.UUID] = {}
    specs: list[tuple[str, dict[str, Any] | None]] = [
        ("love", {"sentiment": "positive", "intent": "feedback"}),
        ("angry", {"sentiment": "negative", "intent": "complaint"}),
        ("price", {"sentiment": "neutral", "intent": "pricing"}),
        ("spam", {"sentiment": "neutral", "intent": "spam", "is_spam": True}),
        ("buy", {"sentiment": "positive", "intent": "purchase"}),
        ("pending", None),
        ("hidden", None),
        ("deleted", None),
    ]
    for i, (name, analysis) in enumerate(specs):
        made[name] = await shop.comment(
            post,
            name,
            commented_at=t0 + timedelta(minutes=i),
            contact_id=contact_id if name == "love" else None,
        )
        if analysis is not None:
            await shop.analyse(made[name], **analysis)
    await shop.execute("UPDATE comments SET hidden = true WHERE id = :id", id=made["hidden"])
    await shop.execute("UPDATE comments SET deleted_at = now() WHERE id = :id", id=made["deleted"])

    async def listed(chip: str) -> list[str]:
        response = await shop.get(f"/posts/{post}/comments", filter=chip)
        assert response.status_code == 200, response.text
        return [c["text"] for c in response.json()["items"]]

    assert await listed("all") == ["hidden", "pending", "buy", "spam", "price", "angry", "love"]
    assert await listed("positive") == ["buy", "love"]
    assert await listed("neutral") == ["price"]  # spam is its own chip
    assert await listed("negative") == ["angry"]
    assert await listed("questions") == ["price"]
    assert await listed("buying") == ["buy", "price"]
    assert await listed("spam") == ["spam"]
    assert await listed("hidden") == ["hidden"]

    items = (await shop.get(f"/posts/{post}/comments")).json()["items"]
    love = next(c for c in items if c["text"] == "love")
    assert love["analysis"]["sentiment"] == "positive"
    assert love["analysis_status"] == "done"
    assert love["author_profile_picture_url"] == "https://pic/1.jpg"
    assert love["post_id"] == str(post)
    pending = next(c for c in items if c["text"] == "pending")
    assert (pending["analysis"], pending["analysis_status"]) == (None, "pending")
    assert next(c for c in items if c["text"] == "hidden")["hidden"] is True

    first = (await shop.get(f"/posts/{post}/comments", limit=3)).json()
    assert [c["text"] for c in first["items"]] == ["hidden", "pending", "buy"]
    rest = (await shop.get(f"/posts/{post}/comments", limit=3, cursor=first["next_cursor"])).json()
    assert [c["text"] for c in rest["items"]] == ["spam", "price", "angry"]
    bad = await shop.get(f"/posts/{post}/comments", cursor="not-a-cursor")
    assert bad.status_code == 422
    assert (await shop.get(f"/posts/{post}/comments", filter="loud")).status_code == 422
    assert (await shop.get(f"/posts/{uuid.uuid4()}/comments")).status_code == 404


async def test_the_summary_refresh_queues_the_job_or_says_why_not(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post)

    refused = await shop.post_json(f"/posts/{post}/summary")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "No comments on this post have been analysed yet."

    await shop.analyse(comment_id)
    accepted = await shop.post_json(f"/posts/{post}/summary")
    assert accepted.status_code == 202, accepted.text
    [job] = await jobs("summarize_post")
    assert job["queueing_lock"] == f"postsum:{post}"
    assert not job["deferred"]  # a member's refresh runs at once

    await use_credits(shop.engine, uuid.UUID(shop.wid), 199, now=datetime.now(UTC))
    assert (await shop.post_json(f"/posts/{post}/summary")).status_code == 402

    await shop.execute(
        "UPDATE social_accounts SET ai_analysis_enabled = false WHERE id = :id", id=shop.account_id
    )
    assert (await shop.post_json(f"/posts/{post}/summary")).status_code == 409
    assert (await shop.post_json(f"/posts/{uuid.uuid4()}/summary")).status_code == 404


# ---------------------------------------------------------------- public reply


async def test_a_public_reply_is_posted_once_per_idempotency_key(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post, "How much?")
    ref = (await shop.one("SELECT * FROM comments WHERE id = :id", id=comment_id))[
        "platform_comment_id"
    ]
    path = f"/comments/{comment_id}/reply"

    first = await shop.post_json(path, {"text": "₹499, DM us!"}, key="reply-key-1")

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["public_reply"]["text"] == "₹499, DM us!"
    assert body["public_reply"]["platform_id"].startswith("sandbox_reply_")
    assert [(r.comment_ref, r.text) for r in outbox.COMMENT_REPLIES] == [(ref, "₹499, DM us!")]
    row = await shop.one("SELECT our_reply_text FROM comments WHERE id = :id", id=comment_id)
    assert row["our_reply_text"] == "₹499, DM us!"
    events = await stream(shop.redis, shop.wid)
    assert [kind for kind, _ in events] == ["comment.updated"]
    assert events[0][1]["comment"]["public_reply"]["text"] == "₹499, DM us!"

    again = await shop.post_json(path, {"text": "₹499, DM us!"}, key="reply-key-1")
    assert again.status_code == 200
    assert again.json() == body
    other_body = await shop.post_json(path, {"text": "Something else"}, key="reply-key-1")
    assert other_body.status_code == 409
    assert other_body.json()["code"] == "idempotency_conflict"
    double_click = await shop.post_json(path, {"text": "₹499, DM us!"}, key="reply-key-2")
    assert double_click.status_code == 200
    assert len(outbox.COMMENT_REPLIES) == 1  # nothing more was posted

    assert (
        await shop.post_json(path, {"text": "Also in blue"}, key="reply-key-3")
    ).status_code == 200
    assert len(outbox.COMMENT_REPLIES) == 2


async def test_platform_refusals_of_a_reply(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post)
    path = f"/comments/{comment_id}/reply"

    outbox.fail_next("platform_rejected", kind="comment_reply")
    rejected = await shop.post_json(path, {"text": "Hi"}, key="refused-1")
    assert rejected.status_code == 502
    assert rejected.json()["code"] == "platform_error"

    outbox.fail_next("platform_rate_limited", retry_after_s=30, kind="comment_reply")
    limited = await shop.post_json(path, {"text": "Hi"}, key="refused-2")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "30"

    outbox.fail_next("account_needs_reconnect", kind="comment_reply")
    broken = await shop.post_json(path, {"text": "Hi"}, key="refused-3")
    assert (broken.status_code, broken.json()["code"]) == (409, "account_needs_reconnect")
    account = await shop.one(
        "SELECT status FROM social_accounts WHERE id = :id", id=shop.account_id
    )
    assert account["status"] == "needs_reconnect"
    still = await shop.post_json(path, {"text": "Hi"}, key="refused-4")
    assert (still.status_code, still.json()["code"]) == (409, "account_needs_reconnect")
    assert list(outbox.COMMENT_REPLIES) == []

    missing = await shop.post_json(
        f"/comments/{uuid.uuid4()}/reply", {"text": "Hi"}, key="missing-key-1"
    )
    assert missing.status_code == 404
    no_key = await shop.client.post(shop.url(path), json={"text": "Hi"}, headers=shop.headers)
    assert no_key.status_code == 422


# ---------------------------------------------------------------- private reply


async def test_a_second_private_reply_to_the_same_comment_is_refused(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post, "Link please", author_ref="990000000000055")
    comment = await shop.one("SELECT * FROM comments WHERE id = :id", id=comment_id)
    path = f"/comments/{comment_id}/private-reply"

    queued = await shop.post_json(path, {"text": "Here's the link: maple.example"}, key="dm-key-1")

    assert queued.status_code == 202, queued.text
    reply = queued.json()["private_reply"]
    message = await shop.one("SELECT * FROM messages WHERE id = :id", id=reply["message_id"])
    assert (message["status"], message["source"], message["direction"]) == (
        "queued",
        "human",
        "outbound",
    )
    assert message["text"] == "Here's the link: maple.example"
    assert str(message["conversation_id"]) == reply["conversation_id"]
    contact = await shop.one(
        "SELECT c.platform_user_id FROM conversations v JOIN contacts c ON c.id = v.contact_id"
        " WHERE v.id = :id",
        id=message["conversation_id"],
    )
    assert contact["platform_user_id"] == "990000000000055"  # the commenter's conversation
    [job] = await jobs("send_private_reply")
    assert job["queueing_lock"] == f"send:{message['id']}"
    assert job["args"]["comment_id"] == str(comment_id)
    kinds = [kind for kind, _ in await stream(shop.redis, shop.wid)]
    assert kinds == ["message.created", "conversation.updated", "comment.updated"]

    # The same request again: the first answer, nothing new queued.
    again = await shop.post_json(path, {"text": "Here's the link: maple.example"}, key="dm-key-1")
    assert again.status_code == 202
    assert again.json() == queued.json()
    # Another private reply to the same comment: refused (Instagram allows one).
    second = await shop.post_json(path, {"text": "One more thing"}, key="dm-key-2")
    assert second.status_code == 409
    assert (second.json()["code"], second.json()["detail"]) == ("conflict", ONE_PER_COMMENT)
    assert len(await shop.rows("SELECT id FROM messages")) == 1

    # The job sends it through the adapter's private reply, addressed by the comment.
    assert await shop.send_private_reply(comment_id) == "sent"
    [sent] = outbox.PRIVATE_REPLIES
    assert (sent.recipient_ref, sent.message.text) == (
        comment["platform_comment_id"],
        "Here's the link: maple.example",
    )
    row = await shop.one("SELECT status, platform_message_id FROM messages")
    assert row["status"] == "sent"
    assert row["platform_message_id"] == sent.platform_message_id
    assert await shop.send_private_reply(comment_id) == "skipped"  # already sent
    third = await shop.post_json(path, {"text": "And again"}, key="dm-key-3")
    assert (third.status_code, third.json()["detail"]) == (409, ONE_PER_COMMENT)


async def test_private_replies_follow_instagram_s_limits(shop: Shop) -> None:
    post = await shop.post()
    old = await shop.comment(post, commented_at=datetime.now(UTC) - timedelta(days=8))
    too_old = await shop.post_json(
        f"/comments/{old}/private-reply", {"text": "Hi"}, key="old-key-1"
    )
    assert (too_old.status_code, too_old.json()["detail"]) == (409, TOO_OLD)

    fresh = await shop.comment(post)
    long_text = "₹" * 400  # 1,200 bytes: over Instagram's 1,000
    too_long = await shop.post_json(
        f"/comments/{fresh}/private-reply", {"text": long_text}, key="long-key-1"
    )
    assert too_long.status_code == 422
    assert too_long.json()["errors"][0]["field"] == "text"

    automation = await make_automation(
        shop.engine, workspace_id=shop.wid, account_id=shop.account_id, trigger="comment_any"
    )
    await shop.execute(
        "INSERT INTO automation_runs (workspace_id, automation_id, trigger_comment_id,"
        " matched_keyword, result) VALUES (:w, :a, :c, '', 'queued')",
        w=shop.wid,
        a=automation,
        c=fresh,
    )
    queued_run = await shop.post_json(
        f"/comments/{fresh}/private-reply", {"text": "Hi"}, key="auto-key-1"
    )
    assert queued_run.status_code == 409
    assert "automation" in queued_run.json()["detail"]
    assert await shop.rows("SELECT id FROM messages") == []


async def test_a_refused_private_reply_frees_the_comment_for_another(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post)
    path = f"/comments/{comment_id}/private-reply"
    assert (await shop.post_json(path, {"text": "Hi!"}, key="free-key-1")).status_code == 202

    outbox.fail_next("platform_rejected", kind="private_reply")
    assert await shop.send_private_reply(comment_id) == "failed"
    failed = await shop.one("SELECT status, error_code, error_message FROM messages")
    assert (failed["status"], failed["error_code"]) == ("failed", "platform_rejected")
    assert failed["error_message"].startswith("Instagram rejected this")
    row = await shop.one(
        "SELECT private_reply_message_id FROM comments WHERE id = :id", id=comment_id
    )
    assert row["private_reply_message_id"] is None
    retried = await shop.post_json(path, {"text": "Hi again!"}, key="free-key-2")
    assert retried.status_code == 202, retried.text

    # Past Instagram's 7 days when the job runs: failed with the reason, freed again.
    later = datetime.now(UTC) + timedelta(days=8)
    assert await shop.send_private_reply(comment_id, now=later) == "failed"
    expired = await shop.one("SELECT error_message FROM messages WHERE text = 'Hi again!'")
    assert expired["error_message"] == TOO_OLD
    assert list(outbox.PRIVATE_REPLIES) == []


async def test_an_unconfirmed_private_reply_keeps_the_comment_s_one_chance(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post)
    path = f"/comments/{comment_id}/private-reply"
    assert (await shop.post_json(path, {"text": "Hi!"}, key="unknown-key-1")).status_code == 202
    outbox.fail_next("delivery_unknown", kind="private_reply")
    assert await shop.send_private_reply(comment_id) == "failed"
    row = await shop.one("SELECT status, error_code FROM messages")
    assert (row["status"], row["error_code"]) == ("failed", "delivery_unknown")
    second = await shop.post_json(path, {"text": "Hi?"}, key="unknown-key-2")
    assert second.status_code == 409  # Instagram may have it: no second one


# ---------------------------------------------------------------- hide, unhide, delete


async def test_hide_unhide_and_delete_change_instagram_first(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post, "Rude words")
    kept = await shop.comment(post, "Kind words")
    ref = (await shop.one("SELECT * FROM comments WHERE id = :id", id=comment_id))[
        "platform_comment_id"
    ]

    hidden = await shop.post_json(f"/comments/{comment_id}/hide")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["hidden"] is True
    assert (await shop.post_json(f"/comments/{comment_id}/hide")).json()["hidden"] is True
    shown = await shop.post_json(f"/comments/{comment_id}/unhide")
    assert shown.json()["hidden"] is False
    assert [(m.comment_ref, m.action) for m in outbox.MODERATION] == [
        (ref, "hide"),
        (ref, "unhide"),
    ]  # hiding a hidden comment called nothing

    outbox.fail_next("platform_rejected", kind="moderation")
    assert (await shop.post_json(f"/comments/{comment_id}/hide")).status_code == 502

    await shop.redis.delete(f"events:{shop.wid}")
    deleted = await shop.client.delete(shop.url(f"/comments/{comment_id}"), headers=shop.headers)
    assert deleted.status_code == 204, deleted.text
    assert outbox.MODERATION[-1].action == "delete"
    row = await shop.one("SELECT deleted_at FROM comments WHERE id = :id", id=comment_id)
    assert row["deleted_at"] is not None
    events = await stream(shop.redis, shop.wid)
    assert [kind for kind, _ in events] == ["comment.updated", "post.updated"]
    assert events[0][1]["comment"]["deleted_at"] is not None
    assert events[1][1]["post"]["stats"]["total"] == 1  # the deleted one leaves the count
    listed = (await shop.get(f"/posts/{post}/comments")).json()["items"]
    assert [c["id"] for c in listed] == [str(kept)]

    again = await shop.client.delete(shop.url(f"/comments/{comment_id}"), headers=shop.headers)
    assert again.status_code == 204
    assert len(outbox.MODERATION) == 3  # nothing more was called
    gone = await shop.post_json(f"/comments/{comment_id}/hide")
    assert (gone.status_code, gone.json()["detail"]) == (409, DELETED)


async def test_only_admins_delete_comments(shop: Shop) -> None:
    post = await shop.post()
    comment_id = await shop.comment(post)
    await shop.execute(
        "UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w", w=shop.wid
    )
    refused = await shop.client.delete(shop.url(f"/comments/{comment_id}"), headers=shop.headers)
    assert refused.status_code == 403
    assert (await shop.post_json(f"/comments/{comment_id}/hide")).status_code == 200
    assert [m.action for m in outbox.MODERATION] == ["hide"]


@pytest.mark.parametrize("chip", CHIPS)
async def test_every_chip_is_accepted(shop: Shop, chip: str) -> None:
    post = await shop.post()
    response = await shop.get(f"/posts/{post}/comments", filter=chip)
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}
