"""GR-05: the Activity page. Done when a failed run shows its reason and the one action, other
workspaces and agents see nothing, and an automation that keeps failing alerts the owners once.

The list merges automation runs, failed flow steps, failed sends, failed outbound webhook
deliveries and accounts that need attention (services/activity/feed.py)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks.activity import alert_failing_automations
from socialhood.models.inbox import Message
from socialhood.services.activity import alerts
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import Ws, make_run, workspace
from tests.support.automations import make_automation
from tests.support.inbox import make_thread

NOW = datetime.now(UTC).replace(microsecond=0)


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def thread_of(ws: Ws, engine: AsyncEngine) -> Any:
    return await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)


async def failed_run(
    ws: Ws,
    engine: AsyncEngine,
    automation_id: uuid.UUID,
    *,
    at: datetime,
    code: str = "account_needs_reconnect",
    message: str = "stored",
    conversation_id: uuid.UUID | None = None,
    result: str = "failed",
) -> uuid.UUID:
    thread = await thread_of(ws, engine) if conversation_id is None else None
    async with AsyncSession(engine) as session:
        message_id = (
            await session.execute(
                text(
                    "INSERT INTO messages (workspace_id, conversation_id, social_account_id,"
                    " direction, source, kind, occurred_at, status)"
                    " VALUES (:w, :c, :a, 'inbound', 'customer', 'text', :t, 'received')"
                    " RETURNING id"
                ),
                {
                    "w": ws.wid,
                    "c": conversation_id or thread.conversation_id,  # type: ignore[union-attr]
                    "a": ws.account_id,
                    "t": at,
                },
            )
        ).scalar_one()
        await session.commit()
    return await make_run(
        engine,
        workspace_id=ws.wid,
        automation_id=automation_id,
        created_at=at,
        result=result,
        trigger_message_id=message_id,
        conversation_id=conversation_id or thread.conversation_id,  # type: ignore[union-attr]
        error_code=code,
        error_message=message,
    )


async def failed_message(
    ws: Ws,
    engine: AsyncEngine,
    *,
    at: datetime,
    code: str,
    source: str = "human",
    automation_run_id: uuid.UUID | None = None,
) -> uuid.UUID:
    thread = await thread_of(ws, engine)
    with workspace_scope(uuid.UUID(ws.wid)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = Message(
                conversation_id=thread.conversation_id,
                social_account_id=uuid.UUID(ws.account_id),
                direction="outbound",
                source=source,
                kind="text",
                text="private words that never leave the API",
                occurred_at=at,
                client_id=uuid.uuid4(),
                status="failed",
                error_code=code,
                error_message="stored reason",
                automation_run_id=automation_run_id,
            )
            session.add(row)
            await session.commit()
            return row.id


async def failed_delivery(
    ws: Ws, engine: AsyncEngine, *, at: datetime, endpoint_status: str = "active"
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        endpoint = (
            await conn.execute(
                text(
                    "INSERT INTO webhook_endpoints (workspace_id, url, description, events,"
                    " status, secret_enc) VALUES (:w, 'https://hooks.example.com/in?key=zzkey',"
                    " 'Zapier', ARRAY['lead.captured'], :s, 'x'::bytea) RETURNING id"
                ),
                {"w": ws.wid, "s": endpoint_status},
            )
        ).scalar_one()
        delivery = (
            await conn.execute(
                text(
                    "INSERT INTO webhook_deliveries (workspace_id, endpoint_id, event_id,"
                    " event_type, payload, status, attempts, response_code, error, created_at)"
                    " VALUES (:w, :e, gen_random_uuid(), 'lead.captured',"
                    " CAST(:p AS jsonb), 'failed', 7, 500, 'The endpoint answered 500.', :t)"
                    " RETURNING id"
                ),
                {"w": ws.wid, "e": endpoint, "p": json.dumps({"note": "zzpayload"}), "t": at},
            )
        ).scalar_one()
    return endpoint, delivery


async def activity(ws: Ws, **params: Any) -> dict[str, Any]:
    result = await ws.ok("GET", "/activity", params=params)
    assert isinstance(result, dict)
    return result


# ---------------------------------------------------------------- what the list shows


async def test_a_failed_run_shows_its_reason_and_the_reconnect_link(
    ws: Ws, engine: AsyncEngine
) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    run = await failed_run(ws, engine, automation, at=NOW)
    ok = await failed_run(ws, engine, automation, at=NOW - timedelta(minutes=1), result="sent")

    got = await activity(ws)
    [item] = got["items"]  # failures only by default: the run that worked is left out
    assert (item["id"], item["kind"], item["outcome"]) == (str(run), "automation_run", "failed")
    assert item["error_code"] == "account_needs_reconnect"
    assert item["reason"].endswith("needs reconnecting before you can send from it.")
    assert item["action"] == {"label": "Reconnect Instagram", "href": "/settings/connections"}
    assert item["automation_id"] == str(automation)
    assert item["retryable"] is False
    assert got["next_cursor"] is None

    everything = await activity(ws, failures_only="false")
    assert [i["id"] for i in everything["items"]] == [str(run), str(ok)]
    assert everything["items"][1]["outcome"] == "ok"
    assert everything["items"][1]["reason"] is None


async def test_every_kind_is_merged_newest_first_with_its_action(
    ws: Ws, engine: AsyncEngine
) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    expired = await failed_run(
        ws,
        engine,
        automation,
        at=NOW - timedelta(minutes=1),
        code="expired",
        result="skipped_expired",
    )
    message = await failed_message(
        ws, engine, at=NOW - timedelta(minutes=2), code="platform_unavailable"
    )
    _, delivery = await failed_delivery(ws, engine, at=NOW - timedelta(minutes=3))
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE social_accounts SET status = 'needs_reconnect',"
                " last_error = 'The access token expired.', updated_at = :t WHERE id = :a"
            ),
            {"t": NOW - timedelta(minutes=4), "a": ws.account_id},
        )

    got = await activity(ws)
    kinds = [(i["kind"], i["id"]) for i in got["items"]]
    assert kinds == [
        ("automation_run", str(expired)),
        ("message", str(message)),
        ("webhook_delivery", str(delivery)),
        ("account", ws.account_id),
    ]
    run_item, message_item, hook_item, account_item = got["items"]
    assert run_item["outcome"] == "skipped"
    assert "7 days" in run_item["reason"]
    assert run_item["action"] is None  # nothing fixes Instagram's 7-day limit
    assert message_item["error_code"] == "platform_unavailable"
    assert hook_item["error_code"] == "endpoint_error"
    assert hook_item["action"] == {"label": "Check the endpoint", "href": "/settings/integrations"}
    assert "Zapier" in hook_item["title"]
    assert account_item["outcome"] == "attention"
    assert account_item["reason"] == "The access token expired."
    assert account_item["action"]["label"] == "Reconnect Instagram"
    dumped = json.dumps(got)
    for hidden in ("private words", "zzkey", "zzpayload"):
        assert hidden not in dumped  # no message text, URL query or payload


async def test_a_runs_failed_send_is_listed_once_as_the_run(ws: Ws, engine: AsyncEngine) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    run = await failed_run(ws, engine, automation, at=NOW)
    await failed_message(
        ws,
        engine,
        at=NOW,
        code="account_needs_reconnect",
        source="automation",
        automation_run_id=run,
    )
    [item] = (await activity(ws))["items"]
    assert item["kind"] == "automation_run"


async def test_a_failed_flow_step_shows_when_the_run_itself_did_not_fail(
    ws: Ws, engine: AsyncEngine
) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    run = await failed_run(ws, engine, automation, at=NOW, result="sent")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO automation_run_steps (workspace_id, run_id, step_id, kind, status,"
                " detail) VALUES (:w, :r, 'second', 'send', 'failed', CAST(:d AS jsonb))"
            ),
            {
                "w": ws.wid,
                "r": run,
                "d": json.dumps({"error_code": "reply_window_closed", "error": "x"}),
            },
        )
    [item] = (await activity(ws))["items"]
    assert (item["kind"], item["error_code"]) == ("flow_step", "reply_window_closed")
    assert item["action"]["label"] == "Open the chat"


# ---------------------------------------------------------------- retries


async def test_retry_is_offered_only_where_it_is_safe(
    ws: Ws, engine: AsyncEngine, queue: None
) -> None:
    busy = await failed_message(ws, engine, at=NOW, code="platform_rate_limited")
    unsure = await failed_message(
        ws, engine, at=NOW - timedelta(minutes=1), code="delivery_unknown"
    )
    _, on = await failed_delivery(ws, engine, at=NOW - timedelta(minutes=2))
    _, off = await failed_delivery(
        ws, engine, at=NOW - timedelta(minutes=3), endpoint_status="paused"
    )
    items = {i["id"]: i for i in (await activity(ws))["items"]}
    assert items[str(busy)]["retry"] == {"kind": "message", "target_id": str(busy)}
    assert items[str(unsure)]["retryable"] is False  # it may have arrived: check the chat first
    assert items[str(unsure)]["retry"] is None
    assert items[str(on)]["retry"] == {"kind": "webhook_delivery", "target_id": str(on)}
    assert items[str(off)]["retryable"] is False

    # The retry itself is GR-04's replay route.
    replayed = await ws.call("POST", f"/webhook-deliveries/{on}/replay")
    assert replayed.status_code == 202, replayed.text


# ---------------------------------------------------------------- paging and filters


async def test_paging_with_a_cursor_repeats_and_skips_nothing(ws: Ws, engine: AsyncEngine) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    made = [
        await failed_run(ws, engine, automation, at=NOW - timedelta(minutes=n)) for n in range(5)
    ]
    first = await activity(ws, limit=2)
    second = await activity(ws, limit=2, cursor=first["next_cursor"])
    third = await activity(ws, limit=2, cursor=second["next_cursor"])
    seen = [i["id"] for page in (first, second, third) for i in page["items"]]
    assert seen == [str(r) for r in made]
    assert third["next_cursor"] is None
    bad = await ws.call("GET", "/activity", params={"cursor": "nonsense"})
    assert bad.status_code == 400


async def test_filters_by_automation_account_and_kind(ws: Ws, engine: AsyncEngine) -> None:
    one = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    two = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id, name="Two")
    run_one = await failed_run(ws, engine, one, at=NOW)
    run_two = await failed_run(ws, engine, two, at=NOW - timedelta(minutes=1))
    message = await failed_message(
        ws, engine, at=NOW - timedelta(minutes=2), code="platform_unavailable"
    )
    await failed_delivery(ws, engine, at=NOW - timedelta(minutes=3))

    by_automation = await activity(ws, automation_id=str(two))
    assert [i["id"] for i in by_automation["items"]] == [str(run_two)]
    by_kind = await activity(ws, kind="message")
    assert [i["id"] for i in by_kind["items"]] == [str(message)]
    by_account = await activity(ws, account_id=ws.account_id)
    assert {i["kind"] for i in by_account["items"]} == {"automation_run", "message"}
    assert str(run_one) in [i["id"] for i in by_account["items"]]
    other = await activity(ws, account_id=str(uuid.uuid4()))
    assert other["items"] == []
    assert (await ws.call("GET", "/activity", params={"kind": "nonsense"})).status_code == 422


# ---------------------------------------------------------------- who sees it


async def test_other_workspaces_and_agents_see_nothing(
    ws: Ws, engine: AsyncEngine, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    await failed_run(ws, engine, automation, at=NOW)

    other = await workspace(client, clerk, email="other@example.com")
    assert (await activity(other))["items"] == []
    crossed = await client.get(f"/v1/w/{ws.wid}/activity", headers=other.headers)
    assert crossed.status_code == 404

    clerk_id, me = await sign_in(client, clerk, email="agent@example.com")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:w, :u, 'agent')"
            ),
            {"w": ws.wid, "u": me["id"]},
        )
    denied = await client.get(f"/v1/w/{ws.wid}/activity", headers=clerk.headers(clerk_id))
    assert denied.status_code == 403


# ---------------------------------------------------------------- alerts


async def notes(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT type, title, link, channels FROM notifications ORDER BY created_at")
        )
        return [dict(r._mapping) for r in rows]


async def test_an_automation_that_keeps_failing_alerts_the_owners_once(
    ws: Ws, engine: AsyncEngine, queue: None
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    for n in range(alerts.FAILING_RUNS - 1):
        await failed_run(ws, engine, automation, at=NOW - timedelta(minutes=n))
    assert await alert_failing_automations(maker, NOW) == 0  # one short
    await failed_run(ws, engine, automation, at=NOW - timedelta(minutes=10))
    assert await alert_failing_automations(maker, NOW) == 1
    [note] = await notes(engine)
    assert note["type"] == "automation_failing"
    assert note["title"] == "Send the link keeps failing"
    assert note["link"] == f"/settings/activity?automation={automation}"
    assert "in_app" in note["channels"]

    assert await alert_failing_automations(maker, NOW) == 0
    assert len(await notes(engine)) == 1  # the same six hours: no second alert


async def test_failures_older_than_an_hour_do_not_alert(
    ws: Ws, engine: AsyncEngine, queue: None
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    automation = await make_automation(engine, workspace_id=ws.wid, account_id=ws.account_id)
    for n in range(alerts.FAILING_RUNS):
        await failed_run(ws, engine, automation, at=NOW - timedelta(hours=2, minutes=n))
    assert await alert_failing_automations(maker, NOW) == 0
    assert await notes(engine) == []
