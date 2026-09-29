"""P8 foundation (§5.3, §5.8, §5.9; TR-BIL-02, FR-NOT-02…04, TR-FE-09, SEC-04): the keys,
checks and cascades of payments, push_subscriptions, email_deliveries and weekly_digests, the new
columns on notifications and webhook_events, the Dodo webhook's fail-closed intake, and the push
configuration, through the factories every P8 test uses."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.main import create_app
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in
from tests.support.billing import (
    dodo_event,
    make_payment,
    post_dodo_event,
    set_subscription,
    signed_headers,
)
from tests.support.inbox import make_workspace
from tests.support.notify import (
    VAPID_PUBLIC_KEY,
    make_email_delivery,
    make_notification,
    make_push_subscription,
    make_weekly_digest,
    push_endpoint,
)


@pytest.fixture
async def wid(engine: AsyncEngine, clean_db: None) -> uuid.UUID:
    return await make_workspace(engine)


async def _scalar(engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def _execute(engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def _user(engine: AsyncEngine) -> uuid.UUID:
    suffix = uuid.uuid4().hex[:10]
    async with engine.begin() as conn:
        user: uuid.UUID = (
            await conn.execute(
                text("INSERT INTO users (clerk_user_id, email) VALUES (:c, :e) RETURNING id"),
                {"c": f"user_{suffix}", "e": f"{suffix}@example.com"},
            )
        ).scalar_one()
    return user


# ---------------------------------------------------------------- tables


async def test_payments_are_unique_per_dodo_payment(engine: AsyncEngine, wid: uuid.UUID) -> None:
    await make_payment(engine, workspace_id=wid, dodo_payment_id="pay_1")
    with pytest.raises(IntegrityError, match="uq_payments_dodo_payment_id"):
        await make_payment(engine, workspace_id=wid, dodo_payment_id="pay_1")
    for column, value, check in (
        ("status", "chargeback", "ck_payments_status"),
        ("currency", "inr", "ck_payments_currency"),
        ("amount_minor", -1, "ck_payments_amount_minor"),
    ):
        with pytest.raises(IntegrityError, match=check):
            await make_payment(engine, workspace_id=wid, **{column: value})


async def test_subscriptions_can_hold_a_dodo_subscription(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    await _execute(
        engine,
        "INSERT INTO subscriptions (workspace_id, billing_anchor_day) VALUES (:w, 5)",
        w=wid,
    )
    now = datetime.now(UTC)
    await set_subscription(
        engine,
        workspace_id=wid,
        plan="pro",
        status="trialing",
        dodo_customer_id="cus_1",
        dodo_subscription_id="sub_1",
        dodo_product_id="pdt_pro",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        trial_ends_at=now + timedelta(days=7),
        last_event_at=now,
    )
    assert await _scalar(
        engine, "SELECT plan || ':' || status FROM subscriptions WHERE workspace_id = :w", w=wid
    ) == ("pro:trialing")


async def test_a_push_subscription_is_one_row_per_endpoint_and_goes_with_its_user(
    engine: AsyncEngine, clean_db: None
) -> None:
    user = await _user(engine)
    endpoint = push_endpoint()
    await make_push_subscription(engine, user_id=user, endpoint=endpoint)
    with pytest.raises(IntegrityError, match="uq_push_subscriptions_endpoint"):
        await make_push_subscription(engine, user_id=await _user(engine), endpoint=endpoint)
    with pytest.raises(IntegrityError, match="ck_push_subscriptions_endpoint"):
        await make_push_subscription(engine, user_id=user, endpoint="http://insecure.test/x")
    await _execute(engine, "DELETE FROM users WHERE id = :u", u=user)
    assert await _scalar(engine, "SELECT count(*) FROM push_subscriptions") == 0


async def test_an_email_is_queued_once_per_dedupe_key(engine: AsyncEngine, wid: uuid.UUID) -> None:
    owner = await _scalar(engine, "SELECT owner_user_id FROM workspaces WHERE id = :w", w=wid)
    notification = await make_notification(engine, workspace_id=wid, user_id=owner)
    delivery = await make_email_delivery(
        engine,
        workspace_id=wid,
        user_id=owner,
        notification_id=notification,
        dedupe_key=f"notification:{notification}",
    )
    assert await _scalar(
        engine, "SELECT status FROM email_deliveries WHERE id = :d", d=delivery
    ) == ("queued")
    with pytest.raises(IntegrityError, match="uq_email_deliveries_workspace_id_dedupe_key"):
        await make_email_delivery(
            engine, workspace_id=wid, dedupe_key=f"notification:{notification}"
        )
    with pytest.raises(IntegrityError, match="ck_email_deliveries_sent_at"):
        await make_email_delivery(engine, workspace_id=wid, status="sent")
    with pytest.raises(IntegrityError, match="ck_email_deliveries_status"):
        await make_email_delivery(engine, workspace_id=wid, status="bounced")

    # The outbox outlives the notification (purged after 90 days) and the member.
    await _execute(engine, "DELETE FROM notifications WHERE id = :n", n=notification)
    assert (
        await _scalar(
            engine, "SELECT notification_id FROM email_deliveries WHERE id = :d", d=delivery
        )
        is None
    )
    await _execute(engine, "DELETE FROM workspaces WHERE id = :w", w=wid)
    assert await _scalar(engine, "SELECT count(*) FROM email_deliveries") == 0


async def test_a_weekly_digest_is_one_per_workspace_per_monday(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    monday = date(2026, 9, 28)
    await make_weekly_digest(engine, workspace_id=wid, week_start=monday)
    with pytest.raises(IntegrityError, match="uq_weekly_digests_workspace_id_week_start"):
        await make_weekly_digest(engine, workspace_id=wid, week_start=monday)
    with pytest.raises(IntegrityError, match="ck_weekly_digests_week_start"):
        await make_weekly_digest(engine, workspace_id=wid, week_start=date(2026, 9, 29))
    other = await make_workspace(engine)
    await make_weekly_digest(engine, workspace_id=other, week_start=monday)


async def test_notifications_take_the_three_channels_and_record_pushes(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    owner = await _scalar(engine, "SELECT owner_user_id FROM workspaces WHERE id = :w", w=wid)
    row = await make_notification(
        engine, workspace_id=wid, user_id=owner, channels=["in_app", "email", "push"]
    )
    await _execute(engine, "UPDATE notifications SET pushed_at = now() WHERE id = :n", n=row)
    with pytest.raises(IntegrityError, match="ck_notifications_channels"):
        await make_notification(engine, workspace_id=wid, user_id=owner, channels=["sms"])


# ---------------------------------------------------------------- Dodo webhook intake


async def _stored(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT provider, dedupe_key, event_type, status, occurred_at, payload"
                " FROM webhook_events ORDER BY received_at"
            )
        )
        return [dict(row._mapping) for row in rows]


@pytest.mark.usefixtures("queue")
async def test_a_signed_dodo_event_is_stored_once_and_queued(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    happened = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
    payload = dodo_event(
        "subscription.active",
        {"subscription_id": "sub_1", "product_id": "pdt_test_pro_monthly"},
        timestamp=happened,
    )
    first = await post_dodo_event(client, payload, msg_id="msg_once")
    again = await post_dodo_event(client, payload, msg_id="msg_once")  # Dodo retries
    assert (first.status_code, again.status_code) == (200, 200)

    [row] = await _stored(engine)
    assert (row["provider"], row["dedupe_key"], row["event_type"], row["status"]) == (
        "dodo",
        "dodo:msg_once",
        "subscription.active",
        "received",
    )
    assert row["occurred_at"] == happened
    assert row["payload"]["data"]["subscription_id"] == "sub_1"
    jobs = await _scalar(
        engine,
        "SELECT count(*) FROM procrastinate_jobs WHERE task_name = 'process_webhook_event'",
    )
    assert jobs == 1


@pytest.mark.parametrize(
    "tamper",
    ["unsigned", "wrong_secret", "changed_body", "stale", "not_json"],
)
async def test_an_unverified_dodo_delivery_is_refused_and_stores_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine, tamper: str
) -> None:
    raw = json.dumps(dodo_event("subscription.active", {"subscription_id": "sub_1"})).encode()
    headers = signed_headers(raw)
    body = raw
    expected = 401
    if tamper == "unsigned":
        headers = {"content-type": "application/json"}
    elif tamper == "wrong_secret":
        headers = signed_headers(raw, secret="whsec_" + "QUJD" * 8)
    elif tamper == "changed_body":
        body = raw.replace(b"sub_1", b"sub_2")
    elif tamper == "stale":
        headers = signed_headers(raw, at=datetime.now(UTC) - timedelta(minutes=10))
    elif tamper == "not_json":
        body = b"not json"
        headers = signed_headers(body)
        expected = 400
    response = await client.post("/webhooks/dodo", content=body, headers=headers)
    assert response.status_code == expected, response.text
    assert await _stored(engine) == []


async def test_without_a_secret_the_dodo_webhook_fails_closed(
    api_settings: Settings, clean_db: None, engine: AsyncEngine
) -> None:
    app = create_app(api_settings.model_copy(update={"dodo_webhook_secret": None}))
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            raw = json.dumps(dodo_event("subscription.active", {})).encode()
            response = await client.post("/webhooks/dodo", content=raw, headers=signed_headers(raw))
        assert response.status_code == 503
        assert response.json()["code"] == "service_unavailable"
        assert await _stored(engine) == []
    finally:
        await app.state.http.aclose()
        await app.state.redis.aclose()
        await app.state.engine.dispose()


# ---------------------------------------------------------------- push configuration


async def test_the_push_config_gives_the_vapid_public_key(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, _ = await sign_in(client, clerk)
    response = await client.get("/v1/push/config", headers=clerk.headers(clerk_id))
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "vapid_public_key": VAPID_PUBLIC_KEY}
    assert (await client.get("/v1/push/config")).status_code == 401


async def test_without_vapid_keys_push_is_unavailable(
    api_settings: Settings, clean_db: None, clerk: Clerk
) -> None:
    app = create_app(api_settings.model_copy(update={"vapid_private_key": None}))
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            clerk_id, _ = await sign_in(client, clerk)
            response = await client.get("/v1/push/config", headers=clerk.headers(clerk_id))
        assert response.json() == {"enabled": False, "vapid_public_key": None}
    finally:
        await app.state.http.aclose()
        await app.state.redis.aclose()
        await app.state.engine.dispose()


async def test_a_new_workspace_starts_on_a_free_subscription(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    """Provisioning creates it (F-01); migration 0013 backfilled any workspace without one."""
    _, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    assert await _scalar(
        engine, "SELECT plan || ':' || status FROM subscriptions WHERE workspace_id = :w", w=wid
    ) == ("free:free")
