"""TA.1, TA.2, TA.6: the agent runtime (FR-AGT-01, FR-AGT-04, FR-AGT-06, FR-AGT-07, TR-AGT-02,
TR-AGT-07, TR-AGT-08). Done when: a run is stored with its steps; caps stop a runaway loop;
credits are recorded per turn; the report cites every number from stored results; a killed
worker resumes a run without repeating a step.

The model is a scripted FunctionModel (tests/support/agent_runtime.py) and the tools are
test-only: nothing reaches Gemini, and the shipped tools (TA.4) are tested on their own.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic_ai import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.agent import planner
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks import agent as agent_jobs
from socialhood.models.agent import MAX_MODEL_TURNS, MAX_TOOL_CALLS, RUN_CREDIT_CAP
from socialhood.platforms.deps import deps_from
from socialhood.services import agent_runs
from socialhood.settings import Settings
from tests.support.agent_runtime import (
    COMMENT,
    EARLIER_POST,
    LATEST_POST,
    Desk,
    Script,
    call,
    event_texts,
    say,
)
from tests.support.analysis import add_owner_member, use_credits
from tests.support.inbox import make_workspace
from tests.support.ingest import jobs

POST_REF = {"kind": "post", "id": str(LATEST_POST), "label": "Reel of 26 Sep", "parent_id": None}
COMMENT_REF = {
    "kind": "comment",
    "id": str(COMMENT),
    "label": "“Love this!”",
    "parent_id": None,
}
EARLIER_REF = {
    "kind": "post",
    "id": str(EARLIER_POST),
    "label": "Post of 20 Sep",
    "parent_id": None,
}


@pytest.fixture
async def desk(
    engine: AsyncEngine, redis: Redis, api_settings: Settings, clean_db: None
) -> AsyncIterator[Desk]:
    wid = await make_workspace(engine)
    await add_owner_member(engine, wid)
    async with engine.connect() as conn:
        owner = (
            await conn.execute(
                text("SELECT owner_user_id FROM workspaces WHERE id = :w"), {"w": wid}
            )
        ).scalar_one()
    async with httpx.AsyncClient() as http:
        yield Desk(engine, redis, deps_from(http, api_settings), wid, owner)


def sentiment_of_latest(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return call("sentiment_distribution", post_id=str(LATEST_POST))


def shape(steps: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [(s["ordinal"], s["kind"], s["tool"], s["tier"], s["status"]) for s in steps]


# ---------------------------------------------------------------- a run end to end


async def test_a_run_answers_from_its_steps_and_cites_them(desk: Desk) -> None:
    run_id = await desk.ask("How did my latest post do?")
    script = Script(
        call("get_latest_post"),
        sentiment_of_latest,
        # [2] is the comment, [1] the post; [7] points at no record and is dropped.
        say("71% of 83 analysed comments are positive [2], on your latest reel [1][2] [7]."),
    )
    await desk.run(run_id, script)

    run = await desk.run_row(run_id)
    assert run["status"] == "succeeded"
    assert (
        run["answer"] == "71% of 83 analysed comments are positive [1], on your latest reel [2][1]."
    )
    assert run["answer_refs"] == [COMMENT_REF, POST_REF]  # in order of first use
    assert (run["model"], run["prompt_version"]) == ("scripted-model", "agent.v1")
    assert run["credits"] == 3  # one per model turn
    assert run["input_tokens"] > 0
    assert run["output_tokens"] > 0
    assert run["started_at"] <= run["completed_at"]
    assert run["error_code"] is None

    steps = await desk.steps(run_id)
    assert shape(steps) == [
        (0, "tool", "get_latest_post", "read", "succeeded"),
        (1, "tool", "sentiment_distribution", "read", "succeeded"),
        (2, "report", None, None, "succeeded"),
    ]
    assert steps[1]["args"] == {"post_id": str(LATEST_POST)}  # the validated input
    assert steps[1]["result"]["summary"] == "83 of 91 comments analysed: 71% positive"
    assert steps[1]["result"]["refs"] == [POST_REF, COMMENT_REF]  # stored without numbers
    assert [s["idempotency_key"] for s in steps] == [f"{run_id}:{n}" for n in range(3)]
    assert all(s["attempts"] == 1 and s["latency_ms"] >= 0 for s in steps)
    assert all(s["started_at"] and s["completed_at"] for s in steps)
    assert steps[2]["result"] == {"summary": "Wrote the answer"}

    # Every model call is metered as agent_turn, 1 credit, against the run.
    usage = await desk.usage(run_id)
    assert [(u["feature"], u["credits"], u["outcome"]) for u in usage] == [
        ("agent_turn", 1, "ok")
    ] * 3
    assert {u["model"] for u in usage} == {"scripted-model"}
    assert await desk.credits_used() == 3

    # The model was told the rules and the workspace, and shown numbered refs to cite.
    messages, info = script.seen[0]
    assert info.instructions is not None
    assert "Answer only from what the tools returned" in info.instructions
    assert "Now: " in info.instructions
    assert "(UTC, UTC+00:00)" in info.instructions
    first = messages[0]
    assert isinstance(first, ModelRequest)
    assert [p.content for p in first.parts if isinstance(p, UserPromptPart)] == [
        "How did my latest post do?"
    ]
    returned = script.returns(2)
    assert [r.tool_name for r in returned] == ["get_latest_post", "sentiment_distribution"]
    assert returned[1].content["refs"] == [{"n": 1, **POST_REF}, {"n": 2, **COMMENT_REF}]
    assert returned[1].content["caveats"] == ["8 comments aren't analysed yet"]

    # Live progress: statuses and plain-word steps, never the request or the answer.
    events = await desk.events()
    statuses = [p["run"]["status"] for k, p in events if k == "agent.run.updated"]
    assert statuses[:2] == ["planning", "running"]
    assert statuses[-1] == "succeeded"
    assert [p["run"]["status"] for k, p in events if k == "agent.completed"] == ["succeeded"]
    step_events = [
        (p["step"]["label"], p["step"]["status"]) for k, p in events if k == "agent.step"
    ]
    assert step_events == [
        ("Looking up your latest post", "running"),
        ("Looking up your latest post", "succeeded"),
        ("Reading the comments' sentiment", "running"),
        ("Reading the comments' sentiment", "succeeded"),
        ("Writing the answer", "succeeded"),
    ]
    published = event_texts(events)
    assert "How did my latest post do" not in published
    assert "analysed comments are positive" not in published


async def test_a_duplicate_job_leaves_a_finished_run_alone(desk: Desk) -> None:
    run_id = await desk.ask()
    await desk.run(run_id, Script(say("Nothing to look up.")))
    before = await desk.run_row(run_id)
    await desk.run(run_id, Script())  # the script is empty: any model call would fail
    assert await desk.run_row(run_id) == before


async def test_the_requesters_role_bounds_the_tools(desk: Desk) -> None:
    member = await desk.join("agent")
    run_id = await desk.ask(user_id=member)
    script = Script(say("Done."))
    await desk.run(run_id, script)
    offered = script.offered(0)
    assert "list_automations" not in offered  # owners and admins only
    assert {"get_latest_post", "prepare_comment_reply"} <= set(offered)

    owner_run = await desk.ask()
    owner_script = Script(say("Done."))
    await desk.run(owner_run, owner_script)
    assert "list_automations" in owner_script.offered(0)


async def test_the_thread_passes_earlier_exchanges_as_context(desk: Desk) -> None:
    first = await desk.ask("How did my latest post do?")
    await desk.run(first, Script(say("It reached 4,120 people.")))
    follow_up = await desk.ask("And the one before?", thread_id=first)
    script = Script(say("The one before reached 2,900."))
    await desk.run(follow_up, script)
    messages, _ = script.seen[0]
    texts = [
        part.content
        for message in messages
        for part in message.parts
        if isinstance(part, UserPromptPart | TextPart)
    ]
    assert texts == [
        "How did my latest post do?",
        "It reached 4,120 people.",
        "And the one before?",
    ]


async def test_a_requester_who_left_the_workspace_gets_no_answer(desk: Desk) -> None:
    member = await desk.join("agent")
    run_id = await desk.ask(user_id=member)
    await desk.execute("DELETE FROM workspace_members WHERE user_id = :u", u=member)
    script = Script(say("Never."))
    await desk.run(run_id, script)
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"]) == ("failed", "forbidden")
    assert script.calls == 0


# ---------------------------------------------------------------- tools and arguments


async def test_invalid_arguments_go_back_to_the_model_once(desk: Desk) -> None:
    run_id = await desk.ask()
    script = Script(
        call("sentiment_distribution", post_id="not-a-uuid"),
        sentiment_of_latest,
        say("71% positive [2]."),
    )
    await desk.run(run_id, script)
    retry = [
        part
        for message in script.seen[1][0]
        for part in message.parts
        if isinstance(part, RetryPromptPart)
    ]
    assert len(retry) == 1
    assert "post_id" in str(retry[0].content)
    steps = await desk.steps(run_id)
    assert shape(steps) == [  # the invalid call is not a step
        (0, "tool", "sentiment_distribution", "read", "succeeded"),
        (1, "report", None, None, "succeeded"),
    ]
    assert (await desk.run_row(run_id))["status"] == "succeeded"


async def test_a_second_invalid_call_fails_the_run(desk: Desk) -> None:
    run_id = await desk.ask()
    script = Script(
        call("sentiment_distribution", post_id="nope"),
        call("sentiment_distribution", post_id="still nope"),
    )
    await desk.run(run_id, script)
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"]) == ("failed", "ai_invalid_output")
    assert run["error_message"] == "The AI couldn't put an answer together. Try asking again."
    assert await desk.steps(run_id) == []
    assert run["credits"] == 2  # both calls answered, so both are charged


async def test_a_failed_tool_is_reported_and_the_run_is_partial(desk: Desk) -> None:
    desk.calls.errors["flaky_lookup"] = [RuntimeError("connection reset by peer at 10.0.0.3")]
    run_id = await desk.ask()
    script = Script(call("flaky_lookup"), say("I couldn't look that up just now."))
    await desk.run(run_id, script)
    [returned] = script.returns(1)
    assert returned.outcome == "failed"
    assert "Say this data isn't available" in str(returned.content)
    assert "10.0.0.3" not in str(returned.content)  # internals stay in the logs
    steps = await desk.steps(run_id)
    assert (steps[0]["status"], steps[0]["error_code"], steps[0]["attempts"]) == (
        "failed",
        "tool_error",
        1,
    )
    assert steps[0]["error_message"] == "Something went wrong while fetching this."
    run = await desk.run_row(run_id)
    assert (run["status"], run["answer"]) == ("partial", "I couldn't look that up just now.")


async def test_a_transient_tool_error_is_retried_once(desk: Desk) -> None:
    desk.calls.errors["flaky_lookup"] = [TimeoutError()]
    run_id = await desk.ask()
    await desk.run(run_id, Script(call("flaky_lookup"), say("It worked.")))
    [step, _] = await desk.steps(run_id)
    assert (step["status"], step["attempts"]) == ("succeeded", 2)
    assert desk.calls.counts["flaky_lookup"] == 2
    assert (await desk.run_row(run_id))["status"] == "succeeded"


async def test_draft_steps_become_the_runs_action_cards(desk: Desk) -> None:
    run_id = await desk.ask("Reply thanks to the top comment")
    await desk.run(
        run_id,
        Script(
            call("prepare_comment_reply", comment_id=str(COMMENT), text="Thank you!"),
            say("I prepared a reply to the comment [1]; send it from the post."),
        ),
    )
    with workspace_scope(desk.wid), planner.use_tools(desk.tools):
        async with desk.maker() as session:
            row = await agent_runs.visible_run(session, _owner_ctx(desk), run_id)
            detail = await agent_runs.detail_out(session, row)
    [card] = detail.action_cards
    assert card.kind == "reply_to_comment"
    assert card.prefill.model_dump(mode="json") == {
        "comment_id": str(COMMENT),
        "post_id": str(LATEST_POST),
        "text": "Thank you!",
        "private": False,
    }
    assert [s.label for s in detail.steps] == ["Preparing a reply", "Writing the answer"]
    assert detail.steps[0].tier == "draft"
    assert detail.answer_refs[0].id == COMMENT


def _owner_ctx(desk: Desk) -> Any:
    from socialhood.auth.deps import WorkspaceContext
    from socialhood.models.identity import Role

    class _User:
        id = desk.owner_id

    return WorkspaceContext(workspace=None, role=Role.OWNER, user=_User())  # type: ignore[arg-type]


# ---------------------------------------------------------------- caps (TR-AGT-02, §15)


def forever(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """A runaway model: it calls a tool every turn, offered or not."""
    return call("count_things")


async def test_caps_stop_a_runaway_loop(desk: Desk) -> None:
    run_id = await desk.ask()
    script = Script(*[forever] * (MAX_MODEL_TURNS + 3))
    await desk.run(run_id, script)

    assert script.calls == MAX_MODEL_TURNS  # never more model turns than the cap
    assert script.offered(MAX_MODEL_TURNS - 2) != []
    assert script.offered(MAX_MODEL_TURNS - 1) == []  # the last turn is for the answer
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"]) == ("partial", "limit_reached")
    assert run["credits"] == MAX_MODEL_TURNS
    tool_steps = [s for s in await desk.steps(run_id) if s["kind"] == "tool"]
    assert len(tool_steps) == MAX_MODEL_TURNS - 1
    # What the finished steps found, from their stored results, with their citations.
    assert run["answer"].startswith(
        "I stopped before finishing because it needed more steps than one answer allows."
    )
    assert run["answer"].count("- Counted 3 things [1]") == MAX_MODEL_TURNS - 1
    assert run["answer_refs"] == [EARLIER_REF]


async def test_the_tool_call_cap_stops_parallel_calls(desk: Desk) -> None:
    three = ModelResponse(parts=[ToolCallPart("count_things", {}) for _ in range(3)])
    run_id = await desk.ask()
    script = Script(three, three, three, say("never"))
    await desk.run(run_id, script)
    assert script.calls == 3
    tool_steps = [s for s in await desk.steps(run_id) if s["kind"] == "tool"]
    assert len(tool_steps) == 6  # the third turn's calls would pass MAX_TOOL_CALLS
    assert len(tool_steps) <= MAX_TOOL_CALLS
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"]) == ("partial", "limit_reached")


async def test_a_model_that_heeds_the_caps_answers_on_the_last_turn(desk: Desk) -> None:
    def polite(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return call("count_things") if info.function_tools else say("I counted 3 things [1].")

    run_id = await desk.ask()
    await desk.run(run_id, Script(*[polite] * MAX_MODEL_TURNS))
    run = await desk.run_row(run_id)
    assert (run["status"], run["answer"], run["answer_refs"]) == (
        "succeeded",
        "I counted 3 things [1].",
        [EARLIER_REF],
    )
    assert run["credits"] == MAX_MODEL_TURNS


async def test_the_credit_cap_stops_asking_the_model(desk: Desk) -> None:
    run_id = await desk.ask()
    script = Script(
        call("charged_lookup", credits=4),  # turn 1 + 4 = 5
        call("charged_lookup", credits=4),  # turn 2 + 4 = 10
        say("never"),
    )
    await desk.run(run_id, script)
    assert script.calls == 2
    run = await desk.run_row(run_id)
    assert run["credits"] == RUN_CREDIT_CAP
    assert (run["status"], run["error_code"]) == ("partial", "limit_reached")
    assert "more than 10 AI credits" in run["error_message"]
    assert [(u["feature"], u["credits"]) for u in await desk.usage(run_id)] == [
        ("agent_turn", 1),
        ("knowledge_test", 4),
        ("agent_turn", 1),
        ("knowledge_test", 4),
    ]


async def test_the_wall_time_cap_reports_what_it_has(
    desk: Desk, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow(ctx: Any) -> None:
        monkeypatch.setattr("socialhood.agent.executor.RunState.time_left", lambda self: -1.0)

    desk.calls.hooks["get_latest_post"] = slow
    run_id = await desk.ask()
    script = Script(call("get_latest_post"), say("never"))
    await desk.run(run_id, script)
    assert script.calls == 1
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"]) == ("partial", "timeout")
    assert run["answer"].startswith("I stopped before finishing because it took longer than two")


# ---------------------------------------------------------------- the model's failures


def unavailable(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise ModelHTTPError(503, "scripted-model", {"error": "overloaded"})


def refused(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise ModelHTTPError(400, "scripted-model", {"error": "bad request"})


async def test_a_model_error_is_retried_once_and_refunded(desk: Desk) -> None:
    run_id = await desk.ask()
    await desk.run(run_id, Script(unavailable, say("Here you go.")))
    run = await desk.run_row(run_id)
    assert (run["status"], run["credits"]) == ("succeeded", 1)
    assert [(u["credits"], u["outcome"]) for u in await desk.usage(run_id)] == [
        (0, "error"),
        (1, "ok"),
    ]
    assert await desk.credits_used() == 1


async def test_a_model_that_doesnt_answer_fails_the_run(desk: Desk) -> None:
    run_id = await desk.ask()
    script = Script(unavailable, unavailable, say("never"))
    await desk.run(run_id, script)
    assert script.calls == 2  # one retry
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"], run["credits"]) == ("failed", "ai_unavailable", 0)
    assert run["error_message"] == "The AI didn't respond. Try again in a moment."
    assert [(u["credits"], u["outcome"]) for u in await desk.usage(run_id)] == [(0, "error")] * 2
    assert await desk.credits_used() == 0  # refunded
    completed = [p for k, p in await desk.events() if k == "agent.completed"]
    assert completed[0]["run"]["error"]["code"] == "ai_unavailable"


async def test_a_refused_request_is_not_retried(desk: Desk) -> None:
    run_id = await desk.ask()
    script = Script(refused, say("never"))
    await desk.run(run_id, script)
    assert script.calls == 1
    assert (await desk.run_row(run_id))["error_code"] == "ai_unavailable"


async def test_without_a_key_the_run_fails_before_any_call(
    desk: Desk, api_settings: Settings
) -> None:
    run_id = await desk.ask()
    with workspace_scope(desk.wid), planner.use_tools(desk.tools):
        from socialhood.agent import orchestrator

        await orchestrator.run(
            desk.maker, desk.redis, desk.platform, run_id=run_id, workspace_id=desk.wid
        )
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"]) == ("failed", "ai_not_configured")
    assert await desk.usage(run_id) == []


async def test_the_fake_provider_answers_without_a_model(
    desk: Desk, api_settings: Settings
) -> None:
    run_id = await desk.ask()
    fake = api_settings.model_copy(update={"ai_provider": "fake"})
    async with httpx.AsyncClient() as http:
        platform = deps_from(http, fake)
        with workspace_scope(desk.wid), planner.use_tools(desk.tools):
            from socialhood.agent import orchestrator

            await orchestrator.run(
                desk.maker, desk.redis, platform, run_id=run_id, workspace_id=desk.wid
            )
    run = await desk.run_row(run_id)
    assert (run["status"], run["answer"], run["model"]) == (
        "succeeded",
        planner.FAKE_ANSWER,
        "fake-agent",
    )


# ---------------------------------------------------------------- credits


async def test_no_credits_fails_the_run_before_any_call(desk: Desk) -> None:
    await use_credits(desk.engine, desk.wid, 200, now=datetime.now(UTC))  # the Free plan's 200
    run_id = await desk.ask()
    script = Script(say("never"))
    await desk.run(run_id, script)
    assert script.calls == 0
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"], run["credits"]) == ("failed", "quota_exceeded", 0)
    assert run["error_message"] == "Your workspace has used its AI credits for this period."
    assert await desk.usage(run_id) == []
    assert await desk.steps(run_id) == []


async def test_credits_running_out_mid_run_report_what_it_found(desk: Desk) -> None:
    await use_credits(desk.engine, desk.wid, 199, now=datetime.now(UTC))
    run_id = await desk.ask()
    script = Script(call("get_latest_post"), say("never"))
    await desk.run(run_id, script)
    assert script.calls == 1
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"], run["credits"]) == ("partial", "quota_exceeded", 1)
    assert run["answer"] == (
        "I stopped before finishing because your workspace's AI credits ran out. Here is what I"
        " found so far:\n\n- Found your latest post, a reel published 26 hours ago [1]\n\n"
        "Ask again with a narrower question to get a full answer."
    )
    assert run["answer_refs"] == [POST_REF]


# ---------------------------------------------------------------- cancel


async def test_a_cancelled_run_stops_at_the_next_step(desk: Desk) -> None:
    run_id = await desk.ask()

    async def member_cancels(ctx: Any) -> None:
        await desk.execute(
            "UPDATE agent_runs SET status = 'cancelled', completed_at = now() WHERE id = :id",
            id=run_id,
        )

    desk.calls.hooks["get_latest_post"] = member_cancels
    script = Script(call("get_latest_post"), say("never"))
    await desk.run(run_id, script)
    assert script.calls == 1  # no model turn after the cancel
    run = await desk.run_row(run_id)
    assert (run["status"], run["answer"], run["credits"]) == ("cancelled", None, 1)
    # The step already running finished and is kept; nothing ran after it.
    assert shape(await desk.steps(run_id)) == [(0, "tool", "get_latest_post", "read", "succeeded")]


# ---------------------------------------------------------------- crash and resume (TA.6)


class WorkerKilled(BaseException):
    """The worker process dies mid-step (nothing in the job catches a BaseException)."""


async def test_a_killed_worker_resumes_without_repeating_a_step(desk: Desk, queue: None) -> None:
    run_id = await desk.ask("How did my latest post do?")
    desk.calls.errors["sentiment_distribution"] = [WorkerKilled()]
    with pytest.raises(WorkerKilled):
        await desk.run(run_id, Script(call("get_latest_post"), sentiment_of_latest))
    assert (await desk.run_row(run_id))["status"] == "running"
    assert shape(await desk.steps(run_id)) == [
        (0, "tool", "get_latest_post", "read", "succeeded"),
        (1, "tool", "sentiment_distribution", "read", "running"),
    ]

    assert await agent_jobs.sweep(desk.maker, desk.redis) == {"resumed": 0, "failed": 0}  # fresh
    await desk.age(run_id, 11)
    assert await agent_jobs.sweep(desk.maker, desk.redis) == {"resumed": 1, "failed": 0}
    [job] = await jobs("run_agent")
    assert job["queueing_lock"] == f"agent:{run_id}"
    assert job["args"] == {"run_id": str(run_id), "workspace_id": str(desk.wid)}
    # The job is waiting: the next sweep leaves the run to it.
    assert await agent_jobs.sweep(desk.maker, desk.redis) == {"resumed": 0, "failed": 0}

    script = Script(sentiment_of_latest, say("71% are positive [2] on your latest reel [1]."))
    await desk.run(run_id, script)  # the worker runs the job

    # The finished step is replayed, not run again; the interrupted one is offered again.
    returned = script.returns(0)
    assert [(r.tool_name, r.outcome) for r in returned] == [
        ("get_latest_post", "success"),
        ("sentiment_distribution", "failed"),
    ]
    assert returned[0].content["refs"] == [{"n": 1, **POST_REF}]
    assert desk.calls.counts == {"get_latest_post": 1, "sentiment_distribution": 2}
    steps = await desk.steps(run_id)
    assert shape(steps) == [
        (0, "tool", "get_latest_post", "read", "succeeded"),
        (1, "tool", "sentiment_distribution", "read", "failed"),
        (2, "tool", "sentiment_distribution", "read", "succeeded"),
        (3, "report", None, None, "succeeded"),
    ]
    assert steps[1]["error_code"] == "interrupted"
    run = await desk.run_row(run_id)
    assert run["status"] == "succeeded"  # the interrupted call was made again
    assert run["answer"] == "71% are positive [1] on your latest reel [2]."
    assert run["answer_refs"] == [COMMENT_REF, POST_REF]
    assert run["credits"] == 4  # two turns before the crash, two after


async def test_the_sweeper_queues_a_run_whose_job_was_lost(desk: Desk, queue: None) -> None:
    run_id = await desk.ask()
    await desk.age(run_id, 11)
    assert await agent_jobs.sweep(desk.maker, desk.redis) == {"resumed": 1, "failed": 0}
    await desk.run(run_id, Script(say("Here you go.")))
    assert (await desk.run_row(run_id))["status"] == "succeeded"


async def test_the_sweeper_fails_a_run_too_old_to_resume(desk: Desk, queue: None) -> None:
    run_id = await desk.ask(status="running", started_at=datetime.now(UTC))
    await desk.age(run_id, 45)
    assert await agent_jobs.sweep(desk.maker, desk.redis) == {"resumed": 0, "failed": 1}
    run = await desk.run_row(run_id)
    assert (run["status"], run["error_code"]) == ("failed", "interrupted")
    assert await jobs("run_agent") == []


async def test_the_sweeper_leaves_finished_and_waiting_runs_alone(desk: Desk, queue: None) -> None:
    done = await desk.ask(status="succeeded")
    waiting = await desk.ask(status="awaiting_approval")
    for run_id in (done, waiting):
        await desk.age(run_id, 60)
    assert await agent_jobs.sweep(desk.maker, desk.redis) == {"resumed": 0, "failed": 0}


async def test_another_workspaces_run_id_is_not_run(desk: Desk) -> None:
    other = await make_workspace(desk.engine)
    run_id = await desk.ask()
    script = Script(say("never"))
    with planner.use_model(script.model()), planner.use_tools(desk.tools):
        from socialhood.agent import orchestrator

        with workspace_scope(other):
            await orchestrator.run(
                desk.maker, desk.redis, desk.platform, run_id=run_id, workspace_id=other
            )
    assert script.calls == 0
    assert (await desk.run_row(run_id))["status"] == "queued"
