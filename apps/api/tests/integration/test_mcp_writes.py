"""C-165 phase B: draft_reply (never sends), add_knowledge, pause/resume_automation, ask_amplychat
and get_ask_answer, and the two prompts, through the SDK client against the mounted app."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.agent import orchestrator
from socialhood.billing.plans import ENTITLEMENTS
from socialhood.mcp.tools import ask
from socialhood.services.knowledge import sources
from tests.support.automation_api import set_plan
from tests.support.automations import make_automation
from tests.support.mcp import connect, error_of, make_key, structured
from tests.support.sending import Setup, clean_outbox

SCOPES = ("replies:draft", "knowledge:write", "knowledge:read", "automations:write", "ask")


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


@pytest.fixture
async def key(client: httpx.AsyncClient, setup: Setup) -> str:
    made, _ = await make_key(client, setup, *SCOPES, "conversations:read", "automations:read")
    return made


async def call(app: FastAPI, key: str, name: str, args: dict[str, Any]) -> Any:
    async with connect(app, key) as mcp:
        return await mcp.call_tool(name, args)


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


# ---------------------------------------------------------------- draft_reply


async def test_draft_reply_saves_a_suggestion_and_never_sends(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    before = await rows(engine, "SELECT 1 FROM messages WHERE direction = 'outbound'")
    first = structured(
        await call(
            mcp_app,
            key,
            "draft_reply",
            {"conversation_id": setup.conversation_id, "text": "Yes, we ship to Pune!"},
        )
    )
    assert (first["saved"], first["sent"]) == (True, False)
    assert first["reply"] == "Yes, we ship to Pune!"
    assert first["dashboard_url"].endswith(f"/inbox/{setup.conversation_id}")
    [pending] = await rows(engine, "SELECT * FROM reply_suggestions WHERE status = 'pending'")
    assert pending["reply_text"] == "Yes, we ship to Pune!"
    assert pending["can_answer"] is True
    assert await rows(engine, "SELECT 1 FROM messages WHERE direction = 'outbound'") == before

    second = structured(
        await call(
            mcp_app,
            key,
            "draft_reply",
            {"conversation_id": setup.conversation_id, "text": "Shipping takes 3 days."},
        )
    )
    assert second["draft_id"] != first["draft_id"]
    statuses = {r["status"] for r in await rows(engine, "SELECT status FROM reply_suggestions")}
    assert statuses == {"pending", "superseded"}  # one pending suggestion per conversation
    audit = await rows(engine, "SELECT 1 FROM audit_events WHERE action = 'reply.drafted'")
    assert len(audit) == 2


async def test_draft_reply_errors(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    both = error_of(
        await call(
            mcp_app,
            key,
            "draft_reply",
            {"conversation_id": setup.conversation_id, "text": "x", "use_knowledge": True},
        )
    )
    assert both["code"] == "validation_error"
    neither = error_of(
        await call(mcp_app, key, "draft_reply", {"conversation_id": setup.conversation_id})
    )
    assert neither["code"] == "validation_error"
    unknown = error_of(
        await call(
            mcp_app,
            key,
            "draft_reply",
            {"conversation_id": str(uuid.uuid4()), "text": "hello"},
        )
    )
    assert unknown["code"] == "not_found"
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET last_inbound_at = :at"),
            {"at": datetime.now(UTC) - timedelta(days=10)},
        )
    closed = error_of(
        await call(
            mcp_app, key, "draft_reply", {"conversation_id": setup.conversation_id, "text": "hi"}
        )
    )
    assert closed["code"] == "reply_window_closed"
    assert await rows(engine, "SELECT 1 FROM reply_suggestions") == []


async def test_draft_reply_works_on_free(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    await set_plan(engine, setup.wid, "free")
    saved = structured(
        await call(
            mcp_app,
            key,
            "draft_reply",
            {"conversation_id": setup.conversation_id, "text": "Thanks for writing!"},
        )
    )
    assert saved["saved"] is True


# ---------------------------------------------------------------- add_knowledge


@pytest.fixture
def ingested(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    seen: list[uuid.UUID] = []

    async def enqueue(source: Any) -> bool:
        seen.append(source.id)
        return True

    monkeypatch.setattr(sources, "enqueue_ingest", enqueue)
    return seen


async def test_add_knowledge_text_and_faq(
    mcp_app: FastAPI, key: str, engine: AsyncEngine, ingested: list[uuid.UUID]
) -> None:
    note = structured(
        await call(
            mcp_app,
            key,
            "add_knowledge",
            {
                "type": "text",
                "title": "Opening hours",
                "body": "We open 9 to 6, Monday to Saturday.",
            },
        )
    )
    assert (note["type"], note["status"], note["title"]) == ("text", "pending", "Opening hours")
    assert note["characters"] == 35
    assert note["characters_used"] == 35
    faq = structured(
        await call(
            mcp_app,
            key,
            "add_knowledge",
            {"type": "faq", "question": "Do you deliver?", "body": "Yes, across Pune."},
        )
    )
    assert faq["type"] == "faq"
    assert faq["title"] == "Do you deliver?"
    assert ingested == [uuid.UUID(note["source_id"]), uuid.UUID(faq["source_id"])]  # after commit
    assert len(await rows(engine, "SELECT 1 FROM knowledge_sources")) == 2
    audit = await rows(engine, "SELECT 1 FROM audit_events WHERE action = 'knowledge.created'")
    assert len(audit) == 2
    # An identical resend inside the window is the first result, not a second source.
    args = {"type": "text", "title": "Returns", "body": "Returns within 7 days."}
    first = structured(await call(mcp_app, key, "add_knowledge", args))
    again = structured(await call(mcp_app, key, "add_knowledge", args))
    assert again == {**first, "duplicate_of_previous_call": True}
    assert len(await rows(engine, "SELECT 1 FROM knowledge_sources")) == 3


async def test_add_knowledge_counts_toward_the_plan_and_needs_the_fields(
    mcp_app: FastAPI,
    key: str,
    setup: Setup,
    engine: AsyncEngine,
    ingested: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["knowledge_characters"], "pro", 30)
    error = error_of(
        await call(
            mcp_app,
            key,
            "add_knowledge",
            {"type": "text", "title": "Long", "body": "x" * 31},
        )
    )
    assert (error["code"], error["entitlement"], error["limit"]) == (
        "quota_exceeded",
        "knowledge_characters",
        30,
    )
    assert ingested == []
    assert await rows(engine, "SELECT 1 FROM knowledge_sources") == []
    missing = error_of(
        await call(mcp_app, key, "add_knowledge", {"type": "faq", "body": "An answer"})
    )
    assert missing["code"] == "validation_error"
    assert missing["field_errors"][0]["field"] == "question"
    await set_plan(engine, setup.wid, "free")
    free = error_of(
        await call(mcp_app, key, "add_knowledge", {"type": "text", "title": "t", "body": "b"})
    )
    assert free["code"] == "entitlement_required"


# ---------------------------------------------------------------- pause and resume


async def test_pause_and_resume_an_automation(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    automation = str(
        await make_automation(engine, workspace_id=setup.wid, account_id=setup.account_id)
    )
    paused = structured(await call(mcp_app, key, "pause_automation", {"automation_id": automation}))
    assert (paused["status"], paused["changed"]) == ("paused", True)
    again = structured(await call(mcp_app, key, "pause_automation", {"automation_id": automation}))
    assert (again["status"], again["changed"]) == ("paused", False)
    resumed = structured(
        await call(mcp_app, key, "resume_automation", {"automation_id": automation})
    )
    assert (resumed["status"], resumed["changed"]) == ("active", True)
    live = structured(await call(mcp_app, key, "resume_automation", {"automation_id": automation}))
    assert live["changed"] is False
    # An identical pause a minute later still runs: there is no dedupe window to replay.
    second = structured(await call(mcp_app, key, "pause_automation", {"automation_id": automation}))
    assert second["status"] == "paused"
    assert second["duplicate_of_previous_call"] is False
    actions = [
        r["action"]
        for r in await rows(engine, "SELECT action FROM audit_events ORDER BY created_at")
    ]
    assert actions == ["automation.paused", "automation.resumed", "automation.paused"]


async def test_a_never_live_automation_cannot_be_resumed(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    draft = str(
        await make_automation(
            engine,
            workspace_id=setup.wid,
            account_id=setup.account_id,
            status="draft",
            activated_at=None,
        )
    )
    error = error_of(await call(mcp_app, key, "resume_automation", {"automation_id": draft}))
    assert (error["code"] == "conflict" and "Activate" in error["message"]) or "activate" in error[
        "message"
    ]
    nothing = structured(await call(mcp_app, key, "pause_automation", {"automation_id": draft}))
    assert nothing["changed"] is False
    missing = error_of(
        await call(mcp_app, key, "pause_automation", {"automation_id": str(uuid.uuid4())})
    )
    assert missing["code"] == "not_found"


async def test_automation_writes_need_pro(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine
) -> None:
    automation = str(
        await make_automation(engine, workspace_id=setup.wid, account_id=setup.account_id)
    )
    await set_plan(engine, setup.wid, "free")
    error = error_of(await call(mcp_app, key, "pause_automation", {"automation_id": automation}))
    assert error["code"] == "entitlement_required"


# ---------------------------------------------------------------- ask


@pytest.fixture
def queued(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    """No worker in tests: runs stay queued, and the wait is short."""
    seen: list[uuid.UUID] = []

    async def enqueue(run_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
        seen.append(run_id)
        return True

    monkeypatch.setattr(orchestrator, "enqueue_run", enqueue)
    monkeypatch.setattr(ask, "WAIT_S", 0.2)
    monkeypatch.setattr(ask, "POLL_S", 0.1)
    return seen


async def test_ask_returns_a_run_to_collect(
    mcp_app: FastAPI, key: str, setup: Setup, engine: AsyncEngine, queued: list[uuid.UUID]
) -> None:
    question = {"question": "What are people asking in my DMs this week?"}
    first = structured(await call(mcp_app, key, "ask_amplychat", question))
    assert (first["status"], first["finished"], first["answer"]) == ("queued", False, None)
    assert "get_ask_answer" in first["next_step"]
    [run] = await rows(engine, "SELECT * FROM agent_runs")
    assert str(run["id"]) == first["ask_run_id"]
    assert run["request"] == question["question"]
    assert queued == [run["id"]]
    again = structured(await call(mcp_app, key, "ask_amplychat", question))  # a retry
    assert again["ask_run_id"] == first["ask_run_id"]
    assert len(await rows(engine, "SELECT 1 FROM agent_runs")) == 1

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE agent_runs SET status = 'succeeded', answer = 'Mostly shipping [1].', "
                "credits = 3, completed_at = now()"
            )
        )
    done = structured(
        await call(mcp_app, key, "get_ask_answer", {"ask_run_id": first["ask_run_id"]})
    )
    assert (done["status"], done["finished"], done["credits_used"]) == ("succeeded", True, 3)
    assert done["answer"] == "Mostly shipping [1]."
    missing = error_of(
        await call(mcp_app, key, "get_ask_answer", {"ask_run_id": str(uuid.uuid4())})
    )
    assert missing["code"] == "not_found"


async def test_ask_uses_the_plans_credits_and_rate_limit(
    mcp_app: FastAPI,
    key: str,
    engine: AsyncEngine,
    queued: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ENTITLEMENTS["ai_credits_monthly"], "pro", 0)
    error = error_of(await call(mcp_app, key, "ask_amplychat", {"question": "How many DMs?"}))
    assert (error["code"], error["entitlement"]) == ("quota_exceeded", "ai_credits_monthly")
    assert await rows(engine, "SELECT 1 FROM agent_runs") == []
    assert queued == []


async def test_ask_needs_its_scope(
    client: httpx.AsyncClient, mcp_app: FastAPI, setup: Setup
) -> None:
    narrow, _ = await make_key(client, setup, "posts:read")
    error = error_of(await call(mcp_app, narrow, "ask_amplychat", {"question": "Hi"}))
    assert "ask scope" in error["message"]


# ---------------------------------------------------------------- prompts


async def test_the_two_prompts(mcp_app: FastAPI, key: str) -> None:
    async with connect(mcp_app, key) as mcp:
        listed = {p.name: p for p in (await mcp.list_prompts()).prompts}
        assert set(listed) == {"schedule_a_post", "weekly_inbox_digest"}
        schedule = await mcp.get_prompt("schedule_a_post", {"when": "Friday 6 pm"})
        digest = await mcp.get_prompt("weekly_inbox_digest")
    text_of = schedule.messages[0].content
    assert "Friday 6 pm" in text_of.text
    assert "confirmed: true" in text_of.text
    assert "list_conversations" in digest.messages[0].content.text  # type: ignore[union-attr]
