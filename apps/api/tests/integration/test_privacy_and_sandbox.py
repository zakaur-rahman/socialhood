"""T2.8: Meta deauthorize and data deletion (FR-PRV-01, F-16); the sandbox platform (TR-PL-07)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.tasks.privacy import delete_user_data
from socialhood.models.platform import WebhookStatus
from socialhood.security.signatures import sign_request
from socialhood.services.webhook_processing import process_event
from tests.support.api import IG_APP_SECRET, META_APP_SECRET, WEB, Clerk, sign_in
from tests.support.instagram import FakeInstagram, connect, fixture, signed_delivery

APP_SCOPED_ID = "26000000000000001"  # me_business.json "id"


def signed_form(user_id: str, secret: str = IG_APP_SECRET) -> dict[str, str]:
    payload = {"algorithm": "HMAC-SHA256", "user_id": user_id, "issued_at": 1790000000}
    return {"signed_request": sign_request(payload, secret)}


async def one(engine: AsyncEngine, sql: str) -> dict[str, Any]:
    async with engine.connect() as conn:
        return dict((await conn.execute(text(sql))).one()._mapping)


async def test_deauthorize_disconnects_and_tells_the_owner(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    await connect(client, clerk, clerk_id, wid)

    response = await client.post("/webhooks/meta/deauthorize", data=signed_form(APP_SCOPED_ID))
    assert response.status_code == 200

    row = await one(engine, "SELECT * FROM social_accounts")
    assert (row["status"], row["access_token_enc"]) == ("disconnected", None)
    [note] = (
        await client.get(f"/v1/w/{wid}/notifications", headers=clerk.headers(clerk_id))
    ).json()["items"]
    assert note["type"] == "account_disconnected"


async def test_privacy_callbacks_accept_either_app_secret(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    await connect(client, clerk, clerk_id, me["workspaces"][0]["id"])
    form = signed_form(APP_SCOPED_ID, META_APP_SECRET)
    assert (await client.post("/webhooks/meta/deauthorize", data=form)).status_code == 200
    assert (await one(engine, "SELECT status FROM social_accounts"))["status"] == "disconnected"


async def test_a_forged_signed_request_is_refused(client: httpx.AsyncClient) -> None:
    for form in (signed_form("1", "wrong-secret"), {"signed_request": "garbage"}):
        response = await client.post("/webhooks/meta/deauthorize", data=form)
        assert response.status_code == 401
        response = await client.post("/webhooks/meta/data-deletion", data=form)
        assert response.status_code == 401


async def test_data_deletion_returns_a_status_url_and_deletes(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    await connect(client, clerk, clerk_id, me["workspaces"][0]["id"])
    raw, headers = signed_delivery(fixture("webhook_messaging_batch.json"))
    await client.post("/webhooks/instagram", content=raw, headers=headers)

    response = await client.post("/webhooks/meta/data-deletion", data=signed_form(APP_SCOPED_ID))
    assert response.status_code == 200
    body = response.json()
    code = body["confirmation_code"]
    assert body["url"] == f"{WEB}/data-deletion?code={code}"
    jobs = await jobs_app.connector.execute_query_all_async(
        "SELECT args FROM procrastinate_jobs WHERE task_name = 'delete_platform_user_data'"
    )
    assert jobs == [{"args": {"confirmation_code": code}}]

    status = (await client.get(f"/v1/data-deletion/{code}")).json()
    assert status["status"] == "received"

    assert await delete_user_data(app.state.sessionmaker, code) is True
    assert await delete_user_data(app.state.sessionmaker, code) is False  # already done

    status = (await client.get(f"/v1/data-deletion/{code}")).json()
    assert status["status"] == "completed"
    assert status["completed_at"] is not None
    row = await one(engine, "SELECT status, access_token_enc FROM social_accounts")
    assert (row["status"], row["access_token_enc"]) == ("disconnected", None)
    assert (await one(engine, "SELECT count(*) AS n FROM webhook_events"))["n"] == 0


async def test_an_unknown_deletion_code(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/data-deletion/doesnotexist")
    assert response.status_code == 404


async def test_sandbox_account_and_inbound_events(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)

    created = await client.post(f"/v1/w/{wid}/dev/sandbox/accounts", headers=headers)
    assert created.status_code == 201
    acct = created.json()
    assert acct["sandbox"] is True
    assert "post_insights" in acct["capabilities"]

    for kind in ("dm", "comment"):
        injected = await client.post(
            f"/v1/w/{wid}/dev/sandbox/inbound",
            json={"account_id": acct["id"], "kind": kind, "text": "Hi, is this in stock?"},
            headers=headers,
        )
        assert injected.json() == {"stored": 1}

    async with engine.connect() as conn:
        stored = (await conn.execute(text("SELECT id, event_type FROM webhook_events"))).all()
    expected = {"message": WebhookStatus.PROCESSED, "comment": WebhookStatus.IGNORED}  # P6
    for event_id, event_type in stored:
        assert await process_event(app.state.sessionmaker, event_id) is expected[event_type]
    dm = await one(engine, "SELECT direction, text FROM messages")
    assert dm == {"direction": "inbound", "text": "Hi, is this in stock?"}
    async with engine.connect() as conn:
        routed = (
            (await conn.execute(text("SELECT DISTINCT workspace_id FROM webhook_events")))
            .scalars()
            .all()
        )
    assert [str(w) for w in routed] == [wid]


async def test_sandbox_is_hidden_when_disabled(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"sandbox_platform_enabled": False})
    clerk_id, me = await sign_in(client, clerk)
    response = await client.post(
        f"/v1/w/{me['workspaces'][0]['id']}/dev/sandbox/accounts", headers=clerk.headers(clerk_id)
    )
    assert response.status_code == 404


async def test_only_sandbox_accounts_take_injected_events(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    await connect(client, clerk, clerk_id, wid)
    real = (await one(engine, "SELECT id FROM social_accounts"))["id"]
    response = await client.post(
        f"/v1/w/{wid}/dev/sandbox/inbound",
        json={"account_id": str(real), "kind": "dm", "text": "x"},
        headers=clerk.headers(clerk_id),
    )
    assert response.status_code == 409
