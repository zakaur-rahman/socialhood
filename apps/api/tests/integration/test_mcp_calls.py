"""C-165 phase A: the call pipeline with test tools (the write tools arrive in phase B): the plan
and mode gates on drafts and writes, idempotency keys, the dedupe window, a handler's error and
an unexpected failure as tool errors, and the audit of each."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.errors import ApiError
from socialhood.mcp import calls
from socialhood.mcp.auth import AuthEnv, resolve_bearer
from socialhood.mcp.context import ToolCall
from socialhood.mcp.principal import McpRequest
from socialhood.mcp.registry import (
    Access,
    McpRegistry,
    ToolInput,
    ToolOutput,
    WriteInput,
    WriteOutput,
    tool,
)
from socialhood.models.identity import Role
from tests.support.automation_api import set_plan
from tests.support.mcp import (
    error_of,
    make_key,
    structured,
)
from tests.support.sending import Setup, clean_outbox


@pytest.fixture(autouse=True)
def _outbox() -> Any:
    yield from clean_outbox()


@pytest.fixture
def setup(mcp_setup: Setup) -> Setup:
    return mcp_setup


class NoteInput(WriteInput):
    note: str


class NoteOutput(WriteOutput):
    saved: int


class DraftInput(ToolInput):
    note: str


def make_registry() -> tuple[McpRegistry, list[str]]:
    registry = McpRegistry()
    saved: list[str] = []

    @tool(
        registry,
        name="save_note",
        title="Save a note",
        description="Saves a note.",
        input_model=NoteInput,
        output_model=NoteOutput,
        scope="knowledge:write",
        access=Access.WRITE,
        min_role=Role.ADMIN,
    )
    async def save_note(call: ToolCall, args: NoteInput) -> NoteOutput:
        saved.append(args.note)
        return NoteOutput(summary="Saved", saved=len(saved))

    @tool(
        registry,
        name="queue_note",
        title="Queue a note",
        description="Queues a note.",
        input_model=NoteInput,
        output_model=NoteOutput,
        scope="knowledge:write",
        access=Access.WRITE,
        dedupe_window_s=600,
    )
    async def queue_note(call: ToolCall, args: NoteInput) -> NoteOutput:
        saved.append(args.note)
        return NoteOutput(summary="Queued", saved=len(saved))

    @tool(
        registry,
        name="draft_note",
        title="Draft a note",
        description="Drafts a note.",
        input_model=DraftInput,
        output_model=ToolOutput,
        scope="knowledge:read",
        access=Access.DRAFT,
    )
    async def draft_note(call: ToolCall, args: DraftInput) -> ToolOutput:
        if args.note == "refuse":
            raise ApiError("conflict", "That note already exists.")
        if args.note == "crash":
            raise RuntimeError("boom: internal detail")
        return ToolOutput(summary="Drafted")

    return registry, saved


class Harness:
    def __init__(self, app: FastAPI, request: McpRequest) -> None:
        self.registry, self.saved = make_registry()
        self.request = request
        state = app.state
        self.env = calls.CallEnv(
            sessionmaker=state.sessionmaker,
            redis=state.redis,
            settings=state.settings,
            http=state.http,
        )

    async def call(self, name: str, args: dict[str, Any]) -> Any:
        return await calls.call_tool(self.registry, self.env, self.request, name, args)

    async def names(self) -> list[str]:
        return [
            t.name for t in await calls.list_tools(self.registry, self.env, self.request.principal)
        ]


@pytest.fixture
async def harness(client: httpx.AsyncClient, setup: Setup, mcp_app: FastAPI) -> Harness:
    key, _ = await make_key(client, setup, "knowledge:read", "knowledge:write")
    state = mcp_app.state
    principal = await resolve_bearer(key, AuthEnv(state.sessionmaker, state.redis))
    return Harness(mcp_app, McpRequest(principal=principal, client_ip="127.0.0.1"))


async def set_mode(engine: AsyncEngine, wid: str, mode: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET ai_connections_mode = :m WHERE id = :w"),
            {"m": mode, "w": wid},
        )


async def test_free_gets_drafts_but_not_writes(
    harness: Harness, setup: Setup, engine: AsyncEngine
) -> None:
    assert await harness.names() == ["draft_note", "queue_note", "save_note"]
    await set_plan(engine, setup.wid, "free")
    assert await harness.names() == ["draft_note"]
    structured(await harness.call("draft_note", {"note": "hello"}))
    error = error_of(await harness.call("save_note", {"note": "hello"}))
    assert error["code"] == "entitlement_required"
    assert error["entitlement"] == "ai_connections"
    assert "part of Pro" in error["message"]
    assert harness.saved == []


async def test_the_workspace_mode_admits_by_access(
    harness: Harness, setup: Setup, engine: AsyncEngine
) -> None:
    await set_mode(engine, setup.wid, "read_drafts")
    assert await harness.names() == ["draft_note"]
    error = error_of(await harness.call("save_note", {"note": "x"}))
    assert error["code"] == "forbidden"
    assert "only read and prepare drafts" in error["message"]
    await set_mode(engine, setup.wid, "read_only")
    assert await harness.names() == []
    error = error_of(await harness.call("draft_note", {"note": "x"}))
    assert "only read" in error["message"]


async def test_an_idempotency_key_returns_the_first_result(harness: Harness) -> None:
    args = {"note": "Diwali", "idempotency_key": "retry-0001"}
    first = structured(await harness.call("save_note", args))
    again = structured(await harness.call("save_note", args))
    assert (first["saved"], first["duplicate_of_previous_call"]) == (1, False)
    assert (again["saved"], again["duplicate_of_previous_call"]) == (1, True)
    assert harness.saved == ["Diwali"]
    error = error_of(
        await harness.call("save_note", {"note": "Holi", "idempotency_key": "retry-0001"})
    )
    assert error["code"] == "idempotency_conflict"
    structured(await harness.call("save_note", {"note": "Holi"}))  # no key, no dedupe: runs
    structured(await harness.call("save_note", {"note": "Holi"}))
    assert harness.saved == ["Diwali", "Holi", "Holi"]


async def test_the_dedupe_window_catches_a_resent_write(harness: Harness) -> None:
    first = structured(await harness.call("queue_note", {"note": "Reel"}))
    again = structured(await harness.call("queue_note", {"note": "Reel"}))
    other = structured(await harness.call("queue_note", {"note": "Story"}))
    assert again == {**first, "duplicate_of_previous_call": True}
    assert other["saved"] == 2
    assert harness.saved == ["Reel", "Story"]


async def test_errors_are_tool_errors_in_plain_words(harness: Harness, engine: AsyncEngine) -> None:
    refused = error_of(await harness.call("draft_note", {"note": "refuse"}))
    assert refused == {"code": "conflict", "message": "That note already exists."}
    crashed = error_of(await harness.call("draft_note", {"note": "crash"}))
    assert crashed["code"] == "internal"
    assert "boom" not in crashed["message"]  # internals never leak
    invalid = error_of(await harness.call("draft_note", {"note": 3, "extra": True}))
    assert invalid["code"] == "validation_error"
    assert {f["field"] for f in invalid["field_errors"]} == {"note", "extra"}
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT outcome, error_code FROM mcp_tool_calls ORDER BY created_at")
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("error", "conflict"),
        ("error", "internal"),
        ("refused", "validation_error"),
    ]


async def test_the_audit_redacts_secrets_and_long_text(
    harness: Harness, engine: AsyncEngine
) -> None:
    structured(
        await harness.call("save_note", {"note": "n" * 500, "idempotency_key": "secret-key-1"})
    )
    async with engine.connect() as conn:
        arguments = (await conn.execute(text("SELECT arguments FROM mcp_tool_calls"))).scalar_one()
    assert arguments["idempotency_key"] == "[redacted]"
    assert len(arguments["note"]) == 200
