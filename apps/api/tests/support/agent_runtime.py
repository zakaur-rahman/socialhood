"""The agent runtime under test (TA.1, TA.2, TA.6): a workspace with members, a registry of
test-only tools (the shipped ones are TA.4's), and a scripted model.

Nothing here reaches a model: ``Script`` is a FunctionModel body that plays the responses it is
given in order and records what the model was shown. ``Desk.run`` runs run_agent's body in the
workspace's scope with the script and the test tools, as the worker would.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.agent import orchestrator
from socialhood.agent.planner import use_model, use_tools
from socialhood.agent.registry import (
    DraftResult,
    Release,
    ToolContext,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from socialhood.ai.metering import metered
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.models.agent import RiskTier
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps
from socialhood.schemas.agent import AnswerRef, CommentReplyAction
from tests.support.agent import make_agent_run
from tests.support.ingest import stream

LATEST_POST = uuid.UUID("5d1f1d8e-0000-4000-8000-000000000001")
EARLIER_POST = uuid.UUID("5d1f1d8e-0000-4000-8000-000000000002")
COMMENT = uuid.UUID("5d1f1d8e-0000-4000-8000-000000000003")


# ---------------------------------------------------------------- test-only tools


class LatestPostIn(BaseModel):
    account: str | None = None


class LatestPostOut(ToolResult):
    post_id: uuid.UUID
    format: str
    age_hours: int


class SentimentIn(BaseModel):
    post_id: uuid.UUID


class SentimentOut(ToolResult):
    analysed: int
    positive_share: float


class NothingIn(BaseModel):
    pass


class CountOut(ToolResult):
    count: int


class ReplyIn(BaseModel):
    comment_id: uuid.UUID
    text: str


class ReplyDraft(DraftResult):
    pass


class ChargedIn(BaseModel):
    credits: int = 4


Hook = Callable[[ToolContext], Awaitable[None]]


@dataclass
class Calls:
    """How often each test tool ran, and code to run inside one (a cancel, a crash)."""

    counts: dict[str, int] = field(default_factory=dict)
    hooks: dict[str, Hook] = field(default_factory=dict)
    # Tool -> errors to raise on its next calls, in order (then it works).
    errors: dict[str, list[BaseException]] = field(default_factory=dict)

    async def enter(self, name: str, ctx: ToolContext) -> None:
        self.counts[name] = self.counts.get(name, 0) + 1
        hook = self.hooks.get(name)
        if hook is not None:
            await hook(ctx)
        pending = self.errors.get(name)
        if pending:
            raise pending.pop(0)


def scripted_tools(calls: Calls) -> ToolRegistry:
    """Five read tools, an admin-only read tool and a draft tool, registered like TA.4's."""
    tools = ToolRegistry()

    async def latest_post(ctx: ToolContext, args: LatestPostIn) -> LatestPostOut:
        await calls.enter("get_latest_post", ctx)
        return LatestPostOut(
            summary="Found your latest post, a reel published 26 hours ago",
            refs=[AnswerRef(kind="post", id=LATEST_POST, label="Reel of 26 Sep")],
            post_id=LATEST_POST,
            format="reel",
            age_hours=26,
        )

    async def sentiment(ctx: ToolContext, args: SentimentIn) -> SentimentOut:
        await calls.enter("sentiment_distribution", ctx)
        return SentimentOut(
            summary="83 of 91 comments analysed: 71% positive",
            refs=[
                AnswerRef(kind="post", id=args.post_id, label="Reel of 26 Sep"),
                AnswerRef(kind="comment", id=COMMENT, label="“Love this!”"),
            ],
            caveats=["8 comments aren't analysed yet"],
            analysed=83,
            positive_share=0.71,
        )

    async def count_things(ctx: ToolContext, args: NothingIn) -> CountOut:
        await calls.enter("count_things", ctx)
        return CountOut(
            summary="Counted 3 things",
            refs=[AnswerRef(kind="post", id=EARLIER_POST, label="Post of 20 Sep")],
            count=3,
        )

    async def flaky(ctx: ToolContext, args: NothingIn) -> CountOut:
        await calls.enter("flaky_lookup", ctx)
        return CountOut(summary="The flaky lookup worked", count=1)

    async def charged(ctx: ToolContext, args: ChargedIn) -> CountOut:
        """An AI-calling tool metered against the run (like a knowledge answer)."""
        await calls.enter("charged_lookup", ctx)
        async with metered(
            ctx.sessionmaker,
            workspace_id=ctx.workspace_id,
            feature="knowledge_test",
            ref_type="agent_run",
            ref_id=ctx.run_id,
            cost=args.credits,
        ) as meter:
            meter.model = "fake-model"
        return CountOut(summary=f"Asked the knowledge base ({args.credits} credits)", count=1)

    async def admin_only(ctx: ToolContext, args: NothingIn) -> CountOut:
        await calls.enter("list_automations", ctx)
        return CountOut(summary="2 automations", count=2)

    async def prepare_reply(ctx: ToolContext, args: ReplyIn) -> ReplyDraft:
        await calls.enter("prepare_comment_reply", ctx)
        return ReplyDraft(
            summary="Prepared a reply to the comment",
            refs=[AnswerRef(kind="comment", id=args.comment_id, label="“Love this!”")],
            action_card=CommentReplyAction(
                kind="reply_to_comment",
                label="Reply to this comment",
                route=f"posts/{LATEST_POST}?comment={args.comment_id}",
                prefill={  # type: ignore[arg-type]
                    "comment_id": args.comment_id,
                    "post_id": LATEST_POST,
                    "text": args.text,
                },
            ),
        )

    def read(
        name: str, label: str, input_model: type[BaseModel], result: type[ToolResult], handler: Any
    ) -> None:
        tools.register(
            ToolSpec(
                name=name,
                label=label,
                description=f"{label} (test tool).",
                input_model=input_model,
                result_model=result,
                tier=RiskTier.READ,
                release=Release.R1,
                handler=handler,
            )
        )

    read("get_latest_post", "Looking up your latest post", LatestPostIn, LatestPostOut, latest_post)
    read(
        "sentiment_distribution",
        "Reading the comments' sentiment",
        SentimentIn,
        SentimentOut,
        sentiment,
    )
    read("count_things", "Counting things", NothingIn, CountOut, count_things)
    read("flaky_lookup", "Looking something up", NothingIn, CountOut, flaky)
    read("charged_lookup", "Asking the knowledge base", ChargedIn, CountOut, charged)
    tools.register(
        ToolSpec(
            name="list_automations",
            label="Listing your automations",
            description="Automations (test tool, owners and admins).",
            input_model=NothingIn,
            result_model=CountOut,
            tier=RiskTier.READ,
            release=Release.R1,
            min_role=Role.ADMIN,
            handler=admin_only,
        )
    )
    tools.register(
        ToolSpec(
            name="prepare_comment_reply",
            label="Preparing a reply",
            description="A reply card for a comment (test tool).",
            input_model=ReplyIn,
            result_model=ReplyDraft,
            tier=RiskTier.DRAFT,
            release=Release.R1,
            handler=prepare_reply,
        )
    )
    return tools


# ---------------------------------------------------------------- the scripted model

Turn = ModelResponse | Callable[[list[ModelMessage], AgentInfo], ModelResponse]


def call(tool: str, **args: Any) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool, args)])


def say(answer: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(answer)])


class Script:
    """A FunctionModel body: plays ``turns`` in order; records what each turn was shown."""

    def __init__(self, *turns: Turn) -> None:
        self.turns = list(turns)
        self.seen: list[tuple[list[ModelMessage], AgentInfo]] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.seen.append((list(messages), info))
        assert self.turns, f"the model was called {len(self.seen)} times; the script ran out"
        turn = self.turns.pop(0)
        return turn(messages, info) if callable(turn) else turn

    @property
    def calls(self) -> int:
        return len(self.seen)

    def offered(self, turn: int) -> list[str]:
        """The tools offered on a turn (0-based)."""
        return [t.name for t in self.seen[turn][1].function_tools]

    def returns(self, turn: int) -> list[ToolReturnPart]:
        """The tool returns the model had seen by a turn."""
        return [
            part
            for message in self.seen[turn][0]
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]

    def model(self) -> Model:
        return FunctionModel(self, model_name="scripted-model")


# ---------------------------------------------------------------- the desk


@dataclass
class Desk:
    engine: AsyncEngine
    redis: Redis
    platform: PlatformDeps
    wid: uuid.UUID
    owner_id: uuid.UUID
    calls: Calls = field(default_factory=Calls)

    @property
    def maker(self) -> async_sessionmaker[AsyncSession]:
        return make_sessionmaker(self.engine)

    @property
    def tools(self) -> ToolRegistry:
        return scripted_tools(self.calls)

    async def ask(
        self,
        request: str = "How did my latest post do?",
        *,
        user_id: uuid.UUID | None = None,
        thread_id: uuid.UUID | None = None,
        **values: Any,
    ) -> uuid.UUID:
        """A queued run, as POST …/agent/runs stores it."""
        made = await make_agent_run(
            self.engine,
            workspace_id=self.wid,
            requested_by_user_id=user_id or self.owner_id,
            thread_id=thread_id,
            steps=(),
            **{
                "request": request,
                "status": "queued",
                "answer": None,
                "answer_refs": [],
                "model": None,
                "prompt_version": None,
                "credits": None,
                "input_tokens": None,
                "output_tokens": None,
                "started_at": None,
                "completed_at": None,
                **values,
            },
        )
        return made.id

    async def run(
        self, run_id: uuid.UUID, script: Script | Model, tools: ToolRegistry | None = None
    ) -> None:
        """run_agent's body, as the worker runs it."""
        model = script.model() if isinstance(script, Script) else script
        with use_model(model), use_tools(tools or self.tools), workspace_scope(self.wid):
            await orchestrator.run(
                self.maker, self.redis, self.platform, run_id=run_id, workspace_id=self.wid
            )

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)

    async def run_row(self, run_id: uuid.UUID) -> dict[str, Any]:
        [row] = await self.rows("SELECT * FROM agent_runs WHERE id = :id", id=run_id)
        return row

    async def steps(self, run_id: uuid.UUID) -> list[dict[str, Any]]:
        return await self.rows(
            "SELECT * FROM agent_steps WHERE run_id = :id ORDER BY ordinal", id=run_id
        )

    async def usage(self, run_id: uuid.UUID) -> list[dict[str, Any]]:
        return await self.rows(
            "SELECT feature, credits, outcome, model, input_tokens, output_tokens"
            " FROM ai_usage_events WHERE ref_type = 'agent_run' AND ref_id = :id"
            " ORDER BY created_at, id",
            id=run_id,
        )

    async def credits_used(self) -> int:
        rows = await self.rows(
            "SELECT coalesce(sum(used), 0) AS used FROM usage_counters WHERE workspace_id = :w",
            w=self.wid,
        )
        return int(rows[0]["used"])

    async def events(self) -> list[tuple[str, dict[str, Any]]]:
        return [(kind, payload) for kind, payload in await stream(self.redis, self.wid)]

    async def join(self, role: str = "agent") -> uuid.UUID:
        """Another user, a member of this workspace with ``role``."""
        suffix = uuid.uuid4().hex[:10]
        async with self.engine.begin() as conn:
            user_id: uuid.UUID = (
                await conn.execute(
                    text(
                        "INSERT INTO users (clerk_user_id, email, name) VALUES (:c, :e, :n)"
                        " RETURNING id"
                    ),
                    {"c": f"user_{suffix}", "e": f"{suffix}@example.com", "n": "Priya"},
                )
            ).scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO workspace_members (workspace_id, user_id, role)"
                    " VALUES (:w, :u, :r)"
                ),
                {"w": self.wid, "u": user_id, "r": role},
            )
        return user_id

    async def age(self, run_id: uuid.UUID, minutes: int) -> None:
        """Move the run and its steps ``minutes`` into the past (no progress since)."""
        for table, column in (("agent_runs", "id"), ("agent_steps", "run_id")):
            await self.execute(
                f"UPDATE {table} SET updated_at = updated_at - make_interval(mins => :m),"  # noqa: S608
                f" created_at = created_at - make_interval(mins => :m) WHERE {column} = :id",
                m=minutes,
                id=run_id,
            )


def event_texts(events: list[tuple[str, dict[str, Any]]]) -> str:
    return json.dumps([payload for kind, payload in events if kind.startswith("agent.")])
