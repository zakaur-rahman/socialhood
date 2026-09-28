"""T2.5-T2.6: Instagram webhook intake (TR-WH-01...05), routing and the stuck-row sweep."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.tasks.maintenance import sweep_webhook_events
from socialhood.models.platform import WebhookStatus
from socialhood.repositories.webhook_events import MAX_ATTEMPTS
from socialhood.services import webhook_processing
from socialhood.services.webhook_processing import process_event
from tests.support.api import IG_VERIFY_TOKEN, Clerk, sign_in
from tests.support.instagram import FakeInstagram, connect, fixture, hub_signature, signed_delivery

URL = "/webhooks/instagram"


async def events(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, dedupe_key, event_type, status, attempts, last_error, workspace_id,"
                " platform_account_id FROM webhook_events ORDER BY received_at, dedupe_key"
            )
        )
        return [dict(r._mapping) for r in result]


async def job_count() -> int:
    row = await jobs_app.connector.execute_query_one_async(
        "SELECT count(*) AS n FROM procrastinate_jobs WHERE task_name = 'process_webhook_event'"
    )
    return int(row["n"])


async def test_verification_echoes_the_challenge(client: httpx.AsyncClient) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": IG_VERIFY_TOKEN, "hub.challenge": "42"}
    response = await client.get(URL, params=params)
    assert (response.status_code, response.text) == (200, "42")
    wrong = await client.get(URL, params={**params, "hub.verify_token": "nope"})
    assert wrong.status_code == 403


async def test_a_batch_is_stored_once_per_event_and_queued(
    client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    raw, headers = signed_delivery(fixture("webhook_messaging_batch.json"))
    first = await client.post(URL, content=raw, headers=headers)
    again = await client.post(URL, content=raw, headers=headers)  # Meta re-delivers
    assert (first.status_code, again.status_code) == (200, 200)

    stored = await events(engine)
    assert sorted(e["event_type"] for e in stored) == ["message", "reaction", "seen"]
    assert {e["platform_account_id"] for e in stored} == {"17841400000000001"}
    assert await job_count() == 3


@pytest.mark.parametrize(
    "signature",
    [None, "sha256=" + "0" * 64, hub_signature(b"something else")],
    ids=["missing", "wrong", "other-body"],
)
async def test_an_unsigned_delivery_is_refused_and_not_stored(
    client: httpx.AsyncClient, engine: AsyncEngine, signature: str | None
) -> None:
    raw = json.dumps(fixture("webhook_messaging_batch.json")).encode()
    headers = {"content-type": "application/json"}
    if signature:
        headers["x-hub-signature-256"] = signature
    response = await client.post(URL, content=raw, headers=headers)
    assert response.status_code == 401
    assert await events(engine) == []


async def test_a_signed_but_unreadable_body_is_kept_and_acknowledged(
    client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    raw = b"{not json"
    response = await client.post(
        URL, content=raw, headers={"x-hub-signature-256": hub_signature(raw)}
    )
    assert response.status_code == 200
    [stored] = await events(engine)
    assert stored["event_type"] == "invalid"
    assert stored["dedupe_key"].startswith("ig:invalid:")


async def test_an_oversized_delivery_is_refused(client: httpx.AsyncClient) -> None:
    raw = b"x" * (5 * 1024 * 1024 + 1)
    response = await client.post(
        URL, content=raw, headers={"x-hub-signature-256": hub_signature(raw)}
    )
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


async def test_api_bodies_are_limited_to_one_megabyte(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    response = await client.patch(
        f"/v1/w/{me['workspaces'][0]['id']}",
        content=b'{"name": "' + b"x" * (1024 * 1024) + b'"}',
        headers={**clerk.headers(clerk_id), "content-type": "application/json"},
    )
    assert response.status_code == 413


async def test_events_route_to_the_connected_workspace(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    await connect(client, clerk, clerk_id, wid)

    raw, headers = signed_delivery(fixture("webhook_comment_changes.json"))
    await client.post(URL, content=raw, headers=headers)
    [event] = await events(engine)
    assert await process_event(app.state.sessionmaker, event["id"]) is WebhookStatus.IGNORED

    [event] = await events(engine)
    assert str(event["workspace_id"]) == wid
    assert event["last_error"] == "comment handling arrives with the inbox"
    assert event["attempts"] == 1


async def test_events_for_unknown_or_disconnected_accounts_are_ignored(
    app: FastAPI, client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    raw, headers = signed_delivery(fixture("webhook_comment_field_value.json"))
    await client.post(URL, content=raw, headers=headers)
    [event] = await events(engine)
    await process_event(app.state.sessionmaker, event["id"])
    [event] = await events(engine)
    assert (event["status"], event["last_error"]) == (
        "ignored",
        "unknown or disconnected account",
    )
    assert event["workspace_id"] is None


async def test_a_failing_handler_retries_then_fails_on_the_last_attempt(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TR-JOB-04: the row stays ``received`` while retries remain, ``failed`` only at the end."""

    async def broken(session: Any, event: Any) -> Any:
        raise RuntimeError("parser bug")

    monkeypatch.setitem(webhook_processing.HANDLERS, "instagram", broken)
    raw, headers = signed_delivery(fixture("webhook_comment_changes.json"))
    await client.post(URL, content=raw, headers=headers)
    [event] = await events(engine)

    for attempt in range(1, MAX_ATTEMPTS):
        with pytest.raises(RuntimeError):
            await process_event(app.state.sessionmaker, event["id"])
        [row] = await events(engine)
        assert (row["status"], row["attempts"]) == ("received", attempt)
        assert row["last_error"] == "RuntimeError: parser bug"

    assert await process_event(app.state.sessionmaker, event["id"]) is WebhookStatus.FAILED
    [row] = await events(engine)
    assert (row["status"], row["attempts"]) == ("failed", MAX_ATTEMPTS)
    assert await process_event(app.state.sessionmaker, event["id"]) is None


async def test_the_sweep_requeues_events_whose_enqueue_was_lost(
    app: FastAPI, engine: AsyncEngine, queue: None
) -> None:
    old = datetime.now(UTC) - timedelta(minutes=5)
    async with engine.begin() as conn:
        for key, received_at in (("ig:msg:lost", old), ("ig:msg:fresh", datetime.now(UTC))):
            await conn.execute(
                text(
                    "INSERT INTO webhook_events (id, provider, dedupe_key, event_type, payload,"
                    " received_at) VALUES (:id, 'instagram', :key, 'message', '{}', :at)"
                ),
                {"id": uuid.uuid4(), "key": key, "at": received_at},
            )

    assert await sweep_webhook_events(app.state.sessionmaker) == {"requeued": 1}
    assert await job_count() == 1
    # A second sweep finds the job already waiting (queueing lock) and adds nothing.
    assert await sweep_webhook_events(app.state.sessionmaker) == {"requeued": 0}
    assert await job_count() == 1
