"""T3.6: the send pipeline. POST a reply (TR-API-05 idempotency, TR-PL-10 limits, FR-INB-10
window, account and attachment checks, FR-SUG-05 takeover), the send_message job (TR-JOB-04
retries, TR-JOB-05 unknown outcomes, F-07 attachments), retry, and the in-flight sweeper."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.runtime import Runtime
from socialhood.jobs.tasks.send import sweep_in_flight
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.sandbox import outbox
from socialhood.realtime.events import stream_key
from tests.support.api import Clerk
from tests.support.inbox import make_asset, make_workspace
from tests.support.instagram import GRAPH
from tests.support.sending import (
    IG_TOKEN,
    Setup,
    clean_outbox,
    conversation_row,
    message_row,
    outbound_rows,
    post_message,
    run_send,
    send_jobs,
    use_app_runtime,
    workspace_with_thread,
)

SEND_URL = rf"{GRAPH}/v[\d.]+/me/messages"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
def worker(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Runtime:
    return use_app_runtime(app, monkeypatch)


@pytest.fixture
async def setup(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    return await workspace_with_thread(client, clerk, engine)


def problem(response: httpx.Response, status: int, code: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body: dict[str, object] = response.json()
    assert body["code"] == code
    return body


# ---------------------------------------------------------------- POST …/messages


async def test_a_reply_is_queued_and_returned_with_202(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, redis: Redis
) -> None:
    client_id = str(uuid.uuid4())
    response = await post_message(client, setup, client_id=client_id, text="Yes, we ship to Pune")

    assert response.status_code == 202, response.text
    message = response.json()
    assert message["status"] == "queued"
    assert message["client_id"] == client_id
    assert message["direction"] == "outbound"
    assert message["source"] == "human"
    assert message["kind"] == "text"
    assert message["sent_by"]["name"]
    assert message["human_agent_tag"] is False

    [row] = await outbound_rows(engine, setup)
    assert row["sent_by_user_id"] is not None
    [job] = await send_jobs()
    assert job["queueing_lock"] == f"send:{message['id']}"
    assert job["lock"] == f"conv:{setup.conversation_id}"

    conv = await conversation_row(engine, setup)
    assert conv["awaiting_reply"] is False
    assert conv["last_outbound_at"] is not None
    assert conv["last_message_direction"] == "outbound"
    assert conv["last_message_preview"] == "Yes, we ship to Pune"

    entries = await redis.xrange(stream_key(uuid.UUID(setup.wid)))
    types = [e[1]["type"] for e in entries]
    assert types == ["message.created", "conversation.updated"]
    assert json.loads(entries[0][1]["data"])["message"]["id"] == message["id"]


async def test_the_same_key_twice_sends_once(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    client_id = str(uuid.uuid4())
    first = await post_message(client, setup, key="key-0001-abcd", client_id=client_id)
    second = await post_message(client, setup, key="key-0001-abcd", client_id=client_id)

    assert first.status_code == second.status_code == 202
    assert second.json() == first.json()
    assert len(await outbound_rows(engine, setup)) == 1
    assert len(await send_jobs()) == 1

    await run_send(setup, first.json())
    await run_send(setup, first.json())  # a stray second run finds it sent and does nothing
    assert len(outbox.SENT) == 1
    assert (await message_row(engine, first.json()["id"]))["status"] == "sent"


async def test_a_lost_key_still_cannot_send_a_client_id_twice(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    client_id = str(uuid.uuid4())
    first = await post_message(client, setup, key="key-aaaa-0001", client_id=client_id)
    again = await post_message(client, setup, key="key-bbbb-0002", client_id=client_id)
    assert again.status_code == 202
    assert again.json()["id"] == first.json()["id"]
    assert len(await outbound_rows(engine, setup)) == 1
    assert len(await send_jobs()) == 1

    changed = await post_message(client, setup, key="key-cccc-0003", client_id=client_id, text="x")
    problem(changed, 409, "idempotency_conflict")


async def test_the_same_key_with_a_different_body_is_a_conflict(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    client_id = str(uuid.uuid4())
    await post_message(client, setup, key="key-0002-abcd", client_id=client_id, text="One")
    response = await post_message(client, setup, key="key-0002-abcd", client_id=client_id, text="2")
    problem(response, 409, "idempotency_conflict")
    assert len(await outbound_rows(engine, setup)) == 1


async def test_a_refused_request_can_be_sent_again_with_its_key(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'needs_reconnect' WHERE id = :id"),
            {"id": setup.account_id},
        )
    body = {"client_id": str(uuid.uuid4()), "text": "Hello"}
    refused = await post_message(client, setup, key="key-0003-abcd", **body)
    problem(refused, 409, "account_needs_reconnect")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'active' WHERE id = :id"),
            {"id": setup.account_id},
        )
    accepted = await post_message(client, setup, key="key-0003-abcd", **body)
    assert accepted.status_code == 202, accepted.text


async def test_a_1001_byte_instagram_message_is_rejected(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    body = problem(await post_message(client, setup, text="a" * 1001), 422, "validation_error")
    assert body["errors"] == [
        {
            "field": "text",
            "message": "Instagram messages can be up to 1,000 bytes; this one is 1,001.",
        }
    ]
    # Bytes, not characters: 501 two-byte characters are over the limit too.
    problem(await post_message(client, setup, text="é" * 501), 422, "validation_error")
    assert (await post_message(client, setup, text="a" * 1000)).status_code == 202
    assert (await post_message(client, setup, text="é" * 500)).status_code == 202


async def test_an_empty_message_is_rejected(
    client: httpx.AsyncClient, setup: Setup, queue: None
) -> None:
    body = problem(await post_message(client, setup, text="   "), 422, "validation_error")
    assert body["errors"] == [{"field": "text", "message": "Write a message or add an attachment."}]


async def test_a_closed_window_is_409(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    setup = await workspace_with_thread(client, clerk, engine, last_inbound_ago=timedelta(days=8))
    body = problem(await post_message(client, setup), 409, "reply_window_closed")
    assert body["detail"] == (
        "Instagram allows replies for 24 hours after the customer's last message."
    )
    assert await outbound_rows(engine, setup) == []


async def test_without_human_agent_the_window_closes_after_24_hours(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    setup = await workspace_with_thread(
        client, clerk, engine, last_inbound_ago=timedelta(hours=25), instagram=True
    )
    problem(await post_message(client, setup), 409, "reply_window_closed")


async def test_a_human_agent_reply_carries_the_tag(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    # The sandbox account has the human_agent capability.
    setup = await workspace_with_thread(client, clerk, engine, last_inbound_ago=timedelta(days=3))
    response = await post_message(client, setup)
    assert response.status_code == 202, response.text
    assert response.json()["human_agent_tag"] is True


async def test_an_account_that_needs_reconnecting_cannot_send(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'disconnected' WHERE id = :id"),
            {"id": setup.account_id},
        )
    problem(await post_message(client, setup), 409, "account_needs_reconnect")


async def test_attachments_must_be_this_workspaces_images(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    other = await make_workspace(engine)
    foreign = await make_asset(engine, workspace_id=other)
    body = problem(
        await post_message(client, setup, attachment_asset_ids=[str(foreign)]),
        422,
        "validation_error",
    )
    assert body["errors"] == [
        {"field": "attachment_asset_ids", "message": "Attachment not found. Upload it again."}
    ]

    video = await make_asset(engine, workspace_id=setup.wid, resource_type="video")
    problem(
        await post_message(client, setup, attachment_asset_ids=[str(video)]),
        415,
        "unsupported_media",
    )

    image = await make_asset(engine, workspace_id=setup.wid)
    response = await post_message(client, setup, text=None, attachment_asset_ids=[str(image)])
    assert response.status_code == 202, response.text
    message = response.json()
    assert message["kind"] == "image"
    [attachment] = message["attachments"]
    assert attachment["id"] == str(image)
    assert attachment["type"] == "image"
    assert "send_url" not in attachment  # internal fields stay out of the API


async def test_a_reply_pauses_auto_for_the_takeover_period(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET needs_human = true, needs_human_reason = 'refund'")
        )
    before = datetime.now(UTC)
    assert (await post_message(client, setup)).status_code == 202
    conv = await conversation_row(engine, setup)
    assert conv["needs_human"] is False
    assert conv["needs_human_reason"] is None
    paused = conv["ai_paused_until"] - before
    assert timedelta(minutes=119) < paused < timedelta(minutes=121)


async def test_takeover_zero_pauses_until_resumed(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None
) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE ai_settings SET takeover_minutes = 0"))
    assert (await post_message(client, setup)).status_code == 202
    async with engine.connect() as conn:
        infinite = await conn.scalar(
            text("SELECT ai_paused_until = 'infinity' FROM conversations WHERE id = :id"),
            {"id": setup.conversation_id},
        )
    assert infinite is True

    # A later reply with a shorter takeover period never shortens "until resumed".
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE ai_settings SET takeover_minutes = 30"))
    assert (await post_message(client, setup)).status_code == 202
    async with engine.connect() as conn:
        still = await conn.scalar(
            text("SELECT ai_paused_until = 'infinity' FROM conversations WHERE id = :id"),
            {"id": setup.conversation_id},
        )
    assert still is True


# ---------------------------------------------------------------- the send_message job


async def test_the_job_sends_and_marks_the_message_sent(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    queue: None,
    worker: Runtime,
    redis: Redis,
) -> None:
    message = (await post_message(client, setup, text="On its way")).json()
    await run_send(setup, message)

    [sent] = outbox.SENT
    assert sent.message.text == "On its way"
    assert sent.message.human_agent is False
    row = await message_row(engine, message["id"])
    assert row["status"] == "sent"
    assert row["platform_message_id"] == sent.platform_message_id
    assert row["sent_at"] is not None
    assert row["attempts"] == 1

    updates = [
        json.loads(e[1]["data"])["message"]
        for e in await redis.xrange(stream_key(uuid.UUID(setup.wid)))
        if e[1]["type"] == "message.updated"
    ]
    assert [u["status"] for u in updates] == ["sending", "sent"]


async def test_a_retryable_error_retries_then_fails_with_its_code(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    message = (await post_message(client, setup)).json()
    outbox.fail_next("platform_unavailable", times=5)

    for attempt in range(4):  # the queue retries; the row stays in progress
        with pytest.raises(PlatformError) as raised:
            await run_send(setup, message, attempts=attempt)
        assert raised.value.code == "platform_unavailable"
        row = await message_row(engine, message["id"])
        assert row["status"] == "sending"
        assert row["error_code"] is None

    await run_send(setup, message, attempts=4)  # the last attempt: failed, not re-raised
    row = await message_row(engine, message["id"])
    assert row["status"] == "failed"
    assert row["error_code"] == "platform_unavailable"
    assert row["error_message"] == "Instagram didn't respond."
    assert row["attempts"] == 5
    assert not outbox.SENT


async def test_a_retry_that_succeeds_sends_once(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    message = (await post_message(client, setup)).json()
    outbox.fail_next("platform_rate_limited", retry_after_s=30)
    with pytest.raises(PlatformError):
        await run_send(setup, message)
    await run_send(setup, message, attempts=1)
    assert len(outbox.SENT) == 1
    assert (await message_row(engine, message["id"]))["status"] == "sent"


async def test_a_permanent_error_fails_at_once_with_a_readable_reason(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    message = (await post_message(client, setup)).json()
    outbox.fail_next("recipient_unavailable")
    await run_send(setup, message)
    row = await message_row(engine, message["id"])
    assert row["status"] == "failed"
    assert row["error_code"] == "recipient_unavailable"
    assert row["error_message"] == "This person can't receive messages right now."


async def test_a_timeout_after_sending_is_delivery_unknown_and_not_retried(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    queue: None,
    worker: Runtime,
) -> None:
    setup = await workspace_with_thread(client, clerk, engine, instagram=True)
    route = clerk.router.post(url__regex=SEND_URL).mock(
        side_effect=httpx.ReadTimeout("no response")
    )
    message = (await post_message(client, setup)).json()

    await run_send(setup, message)  # returns: nothing for the queue to retry

    assert route.call_count == 1
    row = await message_row(engine, message["id"])
    assert row["status"] == "failed"
    assert row["error_code"] == "delivery_unknown"
    assert row["error_message"] == (
        "We couldn't confirm this was delivered. Check the chat in Instagram before retrying."
    )
    await run_send(setup, message, attempts=1)  # even a stray retry sends nothing
    assert route.call_count == 1


async def test_a_timeout_before_sending_is_retried(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    setup = await workspace_with_thread(client, clerk, engine, instagram=True)
    clerk.router.post(url__regex=SEND_URL).mock(side_effect=httpx.ConnectTimeout("no connection"))
    message = (await post_message(client, setup)).json()
    with pytest.raises(PlatformError) as raised:
        await run_send(setup, message)
    assert raised.value.code == "platform_unavailable"
    assert (await message_row(engine, message["id"]))["status"] == "sending"


async def test_instagram_send_uses_the_token_and_stores_the_mid(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    setup = await workspace_with_thread(client, clerk, engine, instagram=True)
    route = clerk.router.post(url__regex=SEND_URL).respond(
        200, json={"recipient_id": "igsid", "message_id": "aWdfZAG1faXRlbToxOklH"}
    )
    message = (await post_message(client, setup, text="Hi")).json()
    await run_send(setup, message)

    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {IG_TOKEN}"
    body = json.loads(request.content)
    assert body["message"] == {"text": "Hi"}
    assert "tag" not in body
    row = await message_row(engine, message["id"])
    assert row["platform_message_id"] == "aWdfZAG1faXRlbToxOklH"


async def test_an_expired_token_fails_the_send_and_flags_the_account(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    setup = await workspace_with_thread(client, clerk, engine, instagram=True)
    clerk.router.post(url__regex=SEND_URL).respond(
        400, json={"error": {"code": 190, "message": "Error validating access token"}}
    )
    message = (await post_message(client, setup)).json()
    await run_send(setup, message)

    assert (await message_row(engine, message["id"]))["error_code"] == "account_needs_reconnect"
    async with engine.connect() as conn:
        status = await conn.scalar(
            text("SELECT status FROM social_accounts WHERE id = :id"), {"id": setup.account_id}
        )
    assert status == "needs_reconnect"


async def test_the_window_is_checked_again_when_sending(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    message = (await post_message(client, setup)).json()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET last_inbound_at = now() - interval '8 days'")
        )
    await run_send(setup, message)
    assert not outbox.SENT
    assert (await message_row(engine, message["id"]))["error_code"] == "reply_window_closed"


async def test_attachments_go_one_per_message_with_the_text_last(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    first = await make_asset(engine, workspace_id=setup.wid)
    second = await make_asset(engine, workspace_id=setup.wid)
    message = (
        await post_message(
            client, setup, text="Both colours", attachment_asset_ids=[str(first), str(second)]
        )
    ).json()
    await run_send(setup, message)

    kinds = [s.message.attachment.type if s.message.attachment else "text" for s in outbox.SENT]
    assert kinds == ["image", "image", "text"]
    image = outbox.SENT[0].message.attachment
    assert image is not None
    assert "/upload/f_jpg,q_auto,w_1440,c_limit/" in image.url
    row = await message_row(engine, message["id"])
    assert row["status"] == "sent"
    assert row["platform_message_id"] == outbox.SENT[2].platform_message_id
    assert [a["platform_message_id"] for a in row["attachments"]] == [
        outbox.SENT[0].platform_message_id,
        outbox.SENT[1].platform_message_id,
    ]


async def test_a_retry_after_a_partial_send_skips_the_parts_already_sent(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    image = await make_asset(engine, workspace_id=setup.wid)
    message = (
        await post_message(
            client,
            setup,
            text="Price list [sandbox:fail=platform_rejected]",
            attachment_asset_ids=[str(image)],
        )
    ).json()
    await run_send(setup, message)
    assert len(outbox.SENT) == 1  # the image went; the text was rejected
    assert (await message_row(engine, message["id"]))["error_code"] == "platform_rejected"

    retried = await client.post(
        f"/v1/w/{setup.wid}/messages/{message['id']}/retry", headers=setup.headers
    )
    assert retried.status_code == 202, retried.text
    await run_send(setup, message)
    assert len(outbox.SENT) == 1  # the image is not sent again


async def test_a_busy_rate_bucket_reschedules_without_using_a_try(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    queue: None,
    worker: Runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from socialhood.platforms.buckets import TokenBuckets
    from socialhood.services import sending

    async def busy(self: TokenBuckets, bucket: object, account_id: str) -> float:
        return 5.0

    message = (await post_message(client, setup)).json()
    await queue_jobs_done()  # the running job no longer blocks its own key
    monkeypatch.setattr(TokenBuckets, "take", busy)
    monkeypatch.setattr(sending, "MAX_INLINE_WAIT_S", 1.0)

    await run_send(setup, message)

    assert not outbox.SENT
    row = await message_row(engine, message["id"])
    assert row["status"] == "queued"
    assert row["attempts"] == 0
    [job] = [j for j in await send_jobs() if j["status"] == "todo"]
    assert job["scheduled_at"] > datetime.now(UTC) + timedelta(seconds=3)
    assert job["args"]["message_id"] == message["id"]


async def test_a_job_that_starts_before_the_commit_looks_again(
    setup: Setup, queue: None, worker: Runtime
) -> None:
    ghost = {"id": str(uuid.uuid4()), "conversation_id": setup.conversation_id}
    await run_send(setup, ghost)
    [job] = await send_jobs()
    assert job["args"]["not_found"] == 1
    assert job["args"]["message_id"] == ghost["id"]


# ---------------------------------------------------------------- retry


async def test_retry_requeues_a_failed_message_once(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    message = (await post_message(client, setup)).json()
    outbox.fail_next("platform_rejected")
    await run_send(setup, message)
    assert (await message_row(engine, message["id"]))["status"] == "failed"
    await queue_jobs_done()

    url = f"/v1/w/{setup.wid}/messages/{message['id']}/retry"
    first = await client.post(url, headers=setup.headers)
    second = await client.post(url, headers=setup.headers)  # a double click
    assert first.status_code == second.status_code == 202
    assert first.json()["status"] == second.json()["status"] == "queued"
    assert first.json()["error"] is None
    waiting = [j for j in await send_jobs() if j["status"] == "todo"]
    assert len(waiting) == 1

    await run_send(setup, message)
    await run_send(setup, message)
    assert len(outbox.SENT) == 1
    assert (await message_row(engine, message["id"]))["status"] == "sent"

    problem(await client.post(url, headers=setup.headers), 409, "conflict")


async def test_retry_rechecks_the_window(
    client: httpx.AsyncClient, setup: Setup, engine: AsyncEngine, queue: None, worker: Runtime
) -> None:
    message = (await post_message(client, setup)).json()
    outbox.fail_next("platform_rejected")
    await run_send(setup, message)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET last_inbound_at = now() - interval '8 days'")
        )
    response = await client.post(
        f"/v1/w/{setup.wid}/messages/{message['id']}/retry", headers=setup.headers
    )
    problem(response, 409, "reply_window_closed")
    assert (await message_row(engine, message["id"]))["status"] == "failed"


async def test_only_outbound_messages_can_be_retried(
    client: httpx.AsyncClient, setup: Setup, queue: None
) -> None:
    inbound = setup.thread.message_ids[0]
    response = await client.post(
        f"/v1/w/{setup.wid}/messages/{inbound}/retry", headers=setup.headers
    )
    problem(response, 409, "conflict")


async def queue_jobs_done() -> None:
    """Mark every job finished, as the worker would have after running them."""
    from socialhood.jobs.app import app as jobs_app

    await jobs_app.connector.execute_query_async(
        "UPDATE procrastinate_jobs SET status = 'succeeded' WHERE status = 'todo'"
    )


# ---------------------------------------------------------------- sweeper


async def age(engine: AsyncEngine, message_id: str, status: str, minutes: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE messages SET status = :s,"
                " updated_at = now() - make_interval(mins => :m) WHERE id = :id"
            ),
            {"s": status, "m": minutes, "id": message_id},
        )


async def test_the_sweeper_requeues_a_queued_message_that_lost_its_job(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    queue: None,
    worker: Runtime,
    redis: Redis,
) -> None:
    message = (await post_message(client, setup)).json()
    await age(engine, message["id"], "queued", 2)
    counts = await sweep_in_flight(worker.sessionmaker, redis)
    assert counts == {"requeued": 0, "abandoned": 0}  # its job is still waiting

    await queue_jobs_done()
    counts = await sweep_in_flight(worker.sessionmaker, redis)
    assert counts == {"requeued": 1, "abandoned": 0}
    assert len([j for j in await send_jobs() if j["status"] == "todo"]) == 1


async def test_the_sweeper_fails_a_stuck_send_as_delivery_unknown(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    queue: None,
    worker: Runtime,
    redis: Redis,
) -> None:
    message = (await post_message(client, setup)).json()
    await age(engine, message["id"], "sending", 11)
    # A retry is still waiting: leave it alone.
    assert await sweep_in_flight(worker.sessionmaker, redis) == {"requeued": 0, "abandoned": 0}

    await queue_jobs_done()  # the worker died mid-send; nothing will finish it
    assert await sweep_in_flight(worker.sessionmaker, redis) == {"requeued": 0, "abandoned": 1}
    row = await message_row(engine, message["id"])
    assert row["status"] == "failed"
    assert row["error_code"] == "delivery_unknown"
    assert [j for j in await send_jobs() if j["status"] == "todo"] == []


async def test_the_sweeper_leaves_recent_messages_alone(
    client: httpx.AsyncClient,
    setup: Setup,
    engine: AsyncEngine,
    queue: None,
    worker: Runtime,
    redis: Redis,
) -> None:
    message = (await post_message(client, setup)).json()
    await queue_jobs_done()
    await age(engine, message["id"], "sending", 5)
    assert await sweep_in_flight(worker.sessionmaker, redis) == {"requeued": 0, "abandoned": 0}
