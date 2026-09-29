"""P5 inbox routes: the latest analysis on the conversation detail (FR-AI-02), correcting an
analysis (FR-AI-04, T5.2), asking for a summary (FR-AI-03, T5.7), the Closing soon view
(FR-INB-14, T5.11) and GET …/billing (TR-BIL-04, TR-BIL-05, T5.1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.realtime.events import stream_key
from tests.support.ai import make_analysis, make_source
from tests.support.analysis import use_credits
from tests.support.api import Clerk, sign_in
from tests.support.inbox import make_account, make_thread
from tests.support.ingest import stream


@dataclass
class Member:
    client: httpx.AsyncClient
    clerk: Clerk
    clerk_id: str
    wid: str
    account_id: uuid.UUID

    async def call(
        self, method: str, path: str, *, json: Any = None, **params: Any
    ) -> httpx.Response:
        return await self.client.request(
            method,
            f"/v1/w/{self.wid}{path}",
            json=json,
            params=params,
            headers=self.clerk.headers(self.clerk_id),
        )


@pytest.fixture
async def member(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> Member:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    return Member(client, clerk, clerk_id, wid, await make_account(engine, wid))


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def execute(engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


# ---------------------------------------------------------------- analyses (FR-AI-02, FR-AI-04)


async def test_the_detail_shows_the_latest_analysis(member: Member, engine: AsyncEngine) -> None:
    thread = await make_thread(
        engine,
        workspace_id=member.wid,
        account_id=member.account_id,
        texts=("hi", "how much is the gold ring?"),
    )
    conv = thread.conversation_id
    detail = (await member.call("GET", f"/conversations/{conv}")).json()
    assert detail["latest_analysis"] is None

    await make_analysis(
        engine,
        workspace_id=member.wid,
        conversation_id=conv,
        message_id=thread.message_ids[0],
        intent="greeting",
    )
    newest = await make_analysis(
        engine,
        workspace_id=member.wid,
        conversation_id=conv,
        message_id=thread.message_ids[1],
        intent="pricing",
        topics=["gold ring"],
    )

    latest = (await member.call("GET", f"/conversations/{conv}")).json()["latest_analysis"]
    assert latest["id"] == str(newest)
    assert latest["message_id"] == str(thread.message_ids[1])
    assert (latest["intent"], latest["topics"], latest["corrected"]) == (
        "pricing",
        ["gold ring"],
        False,
    )


async def test_correcting_the_latest_analysis(
    member: Member, engine: AsyncEngine, redis: Redis
) -> None:
    thread = await make_thread(engine, workspace_id=member.wid, account_id=member.account_id)
    conv = thread.conversation_id
    analysis_id = await make_analysis(
        engine,
        workspace_id=member.wid,
        conversation_id=conv,
        message_id=thread.message_ids[0],
        intent="pricing",
        sentiment="neutral",
    )
    await execute(
        engine,
        "UPDATE conversations SET last_intent = 'pricing', last_sentiment = 'neutral'"
        " WHERE id = :id",
        id=conv,
    )
    await redis.delete(stream_key(uuid.UUID(member.wid)))

    response = await member.call(
        "PATCH", f"/message-analyses/{analysis_id}", json={"intent": "complaint"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["intent"], body["sentiment"], body["corrected"]) == ("complaint", "neutral", True)
    [row] = await rows(engine, "SELECT * FROM message_analyses WHERE id = :id", id=analysis_id)
    assert (row["intent"], row["corrected_intent"], row["corrected_sentiment"]) == (
        "pricing",  # the model's answer is kept for the evaluation set
        "complaint",
        None,
    )
    assert row["corrected_by_user_id"] is not None
    assert row["corrected_at"] is not None
    [conv_row] = await rows(engine, "SELECT last_intent FROM conversations WHERE id = :id", id=conv)
    assert conv_row["last_intent"] == "complaint"
    [(kind, payload)] = await stream(redis, member.wid)
    assert kind == "conversation.updated"
    assert payload["conversation"]["signal"] == "complaint"

    again = await member.call(
        "PATCH", f"/message-analyses/{analysis_id}", json={"sentiment": "negative"}
    )
    assert (again.json()["intent"], again.json()["sentiment"]) == ("complaint", "negative")


async def test_correcting_an_older_analysis_leaves_the_conversation(
    member: Member, engine: AsyncEngine
) -> None:
    thread = await make_thread(
        engine, workspace_id=member.wid, account_id=member.account_id, texts=("a", "b")
    )
    conv = thread.conversation_id
    older = await make_analysis(
        engine, workspace_id=member.wid, conversation_id=conv, message_id=thread.message_ids[0]
    )
    await make_analysis(
        engine, workspace_id=member.wid, conversation_id=conv, message_id=thread.message_ids[1]
    )

    response = await member.call("PATCH", f"/message-analyses/{older}", json={"intent": "spam"})

    assert response.json()["intent"] == "spam"
    [conv_row] = await rows(engine, "SELECT last_intent FROM conversations WHERE id = :id", id=conv)
    assert conv_row["last_intent"] is None


async def test_a_correction_needs_a_value(member: Member, engine: AsyncEngine) -> None:
    thread = await make_thread(engine, workspace_id=member.wid, account_id=member.account_id)
    analysis_id = await make_analysis(
        engine,
        workspace_id=member.wid,
        conversation_id=thread.conversation_id,
        message_id=thread.message_ids[0],
    )

    empty = await member.call("PATCH", f"/message-analyses/{analysis_id}", json={})
    assert empty.status_code == 422
    assert empty.json()["code"] == "validation_error"
    wrong = await member.call("PATCH", f"/message-analyses/{analysis_id}", json={"intent": "x"})
    assert wrong.status_code == 422
    missing = await member.call(
        "PATCH", f"/message-analyses/{uuid.uuid4()}", json={"intent": "spam"}
    )
    assert missing.status_code == 404


# ---------------------------------------------------------------- summaries (FR-AI-03)


async def summary_jobs() -> list[dict[str, Any]]:
    return list(
        await jobs_app.connector.execute_query_all_async(
            "SELECT queue_name, queueing_lock, args FROM procrastinate_jobs"
            " WHERE task_name = 'summarize_conversation'"
        )
    )


async def test_asking_for_a_summary(member: Member, engine: AsyncEngine) -> None:
    thread = await make_thread(engine, workspace_id=member.wid, account_id=member.account_id)
    conv = thread.conversation_id

    response = await member.call("POST", f"/conversations/{conv}/summary")

    assert response.status_code == 202
    [job] = await summary_jobs()
    assert (job["queue_name"], job["queueing_lock"]) == ("bulk", f"convsum:{conv}")
    assert job["args"] == {"workspace_id": member.wid, "conversation_id": str(conv)}
    # A second request while one waits is the same job.
    assert (await member.call("POST", f"/conversations/{conv}/summary")).status_code == 202
    assert len(await summary_jobs()) == 1


async def test_no_summary_without_credits_or_with_analysis_off(
    member: Member, engine: AsyncEngine
) -> None:
    thread = await make_thread(engine, workspace_id=member.wid, account_id=member.account_id)
    path = f"/conversations/{thread.conversation_id}/summary"
    await execute(
        engine,
        "UPDATE social_accounts SET ai_analysis_enabled = false WHERE id = :id",
        id=member.account_id,
    )
    off = await member.call("POST", path)
    assert (off.status_code, off.json()["code"]) == (409, "conflict")

    await execute(
        engine,
        "UPDATE social_accounts SET ai_analysis_enabled = true WHERE id = :id",
        id=member.account_id,
    )
    await use_credits(engine, uuid.UUID(member.wid), 200, now=datetime.now(UTC))
    spent = await member.call("POST", path)
    assert (spent.status_code, spent.json()["code"]) == (402, "quota_exceeded")
    assert await summary_jobs() == []


# ---------------------------------------------------------------- Closing soon (FR-INB-14)


async def test_the_closing_soon_view(member: Member, engine: AsyncEngine) -> None:
    wrote = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=19)
    reminded = await make_thread(
        engine,
        workspace_id=member.wid,
        account_id=member.account_id,
        last_inbound_at=wrote,
    )
    not_reminded = await make_thread(
        engine,
        workspace_id=member.wid,
        account_id=member.account_id,
        last_inbound_at=wrote,
    )
    for thread in (reminded, not_reminded):
        await execute(
            engine,
            "UPDATE conversations SET lead_score = 80 WHERE id = :id",
            id=thread.conversation_id,
        )
    await execute(
        engine,
        "UPDATE conversations SET window_reminder_for = last_inbound_at WHERE id = :id",
        id=reminded.conversation_id,
    )

    listed = (await member.call("GET", "/conversations", view="closing_soon")).json()["items"]

    assert [item["id"] for item in listed] == [str(reminded.conversation_id)]
    assert listed[0]["signal"] == "closing_soon"


# ---------------------------------------------------------------- billing (TR-BIL-04, FR-AI-05)


async def test_billing_state_on_the_free_plan(member: Member, engine: AsyncEngine) -> None:
    await make_source(engine, workspace_id=member.wid, question="Hours?", body="9 to 6.")
    await make_source(engine, workspace_id=member.wid, question="Returns?", body="Within 7 days.")
    today = datetime.now(UTC)
    await use_credits(engine, uuid.UUID(member.wid), 37, now=today)

    response = await member.call("GET", "/billing")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["plan"], body["status"], body["cancel_at_period_end"]) == ("free", "free", False)
    assert body["trial_eligible"] is True
    assert body["prices"] == []
    entitlements = {e["key"]: e["value"] for e in body["entitlements"]}
    assert entitlements["ai_modes"] == ["off", "suggest"]
    assert entitlements["ai_credits_monthly"] == 200
    assert entitlements["active_automations"] == 3
    assert entitlements["ai_reply_automations"] is False
    usage = {u["metric"]: u for u in body["usage"]}
    [anchor] = await rows(
        engine, "SELECT billing_anchor_day FROM subscriptions WHERE workspace_id = :w", w=member.wid
    )
    credits = usage["ai_credits"]
    assert (credits["used"], credits["limit"]) == (37, 200)
    period_end = date.fromisoformat(credits["period_end"])
    assert period_end.day == anchor["billing_anchor_day"]
    assert period_end > today.date()
    assert usage["knowledge_characters"] == {
        "metric": "knowledge_characters",
        "used": len("Hours?9 to 6.") + len("Returns?Within 7 days."),
        "limit": 200_000,
        "period_end": None,
    }


async def test_a_trial_used_by_the_same_owner_email_ends_eligibility(
    member: Member, engine: AsyncEngine
) -> None:
    [me] = await rows(
        engine,
        "SELECT u.email FROM users u JOIN workspaces w ON w.owner_user_id = u.id WHERE w.id = :w",
        w=member.wid,
    )
    # Another account with the same email (another sign-in method) owns a workspace that trialled.
    async with engine.begin() as conn:
        other_user = (
            await conn.execute(
                text("INSERT INTO users (clerk_user_id, email) VALUES (:c, :e) RETURNING id"),
                {"c": f"user_{uuid.uuid4().hex[:8]}", "e": me["email"].upper()},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO workspaces (name, slug, owner_user_id, trial_used_at)"
                " VALUES ('Old shop', :s, :o, now())"
            ),
            {"s": f"old-{uuid.uuid4().hex[:8]}", "o": other_user},
        )

    body = (await member.call("GET", "/billing")).json()

    assert body["trial_eligible"] is False
