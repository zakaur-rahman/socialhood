"""The planner (TR-AGT-02, FR-AGT-04, TA.2; agent-architecture.html §4 Planner, §15, §17).

A Pydantic AI agent, used only for the loop between the model and its tools. Run state, steps,
credits and audit are ours (models/agent.py); nothing here stores anything itself.

- Model: ``GoogleModel`` on ``settings.ai_model_agent`` (unset: ``settings.ai_model_reply``)
  through ``GoogleProvider(api_key=settings.gemini_api_key)``, at low temperature and the lowest
  thinking level the model takes (ai/gemini.thinking_level). ``AI_PROVIDER=fake`` (local runs
  without a key) answers with a fixed line and calls no tools.
- Dependencies: ``agent.registry.ToolContext`` as ``deps``; tools reach it as
  ``RunContext[ToolContext].deps``.
- Tools: ``registry.available(role=principal.role)`` for ``CURRENT_RELEASE``. Each spec becomes a
  ``pydantic_ai.Tool`` built from the input model's JSON schema (``Tool.from_schema``) whose body
  is ``executor.execute``: it validates the arguments with the input model (invalid: a retry,
  once), persists the step before and after, and returns the result with its refs numbered for
  citation. Tools run one at a time (``sequential``): they share the run's session and steps keep
  their order. A ``PreparedToolset`` withholds every tool once a cap is near (the last model
  turn, MAX_TOOL_CALLS used, the credit cap one turn away, under REPORT_RESERVE_S of wall time),
  so the model writes the answer with what it has.
- Answer loop (R1): ``UsageLimits(request_limit=MAX_MODEL_TURNS, tool_calls_limit=MAX_TOOL_CALLS)``
  is the hard stop behind that; a resumed run starts from the usage it already had.
- Metering: every model call goes through ``MeteredModel``, which checks the run first (cancelled,
  wall time, RUN_CREDIT_CAP), wraps the call in ``ai.metering.metered`` with feature
  ``agent_turn`` (1 credit, ref_type ``agent_run``; QuotaExceeded before any call when credits
  are out) and records the model, tokens and latency in ai_usage_events.
- Failures (§15): a timeout, a 429 or a 5xx is retried once, then ``ModelUnavailable``; the
  credits of each failed call are refunded by ``metered``.
- Prompt: ai/prompts/agent.v1.md (versioned like the other prompts) with trusted settings only:
  the workspace, brand voice, connected accounts and the time. The request and the thread's
  earlier exchanges travel as messages; tool results as tool returns (data, TR-AI-04).
- Plan first (R2): not built. Writes will be deferred (``ApprovalRequired``), decided by our
  gateway and resumed with ``DeferredToolResults``.

Tests never reach Gemini: ``pydantic_ai.models.ALLOW_MODEL_REQUESTS`` is off under pytest, and
tests script the model with ``FunctionModel`` through ``use_model``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, cast, get_args

import pydantic_ai
from pydantic_ai import (
    Agent,
    FunctionToolset,
    ModelAPIError,
    ModelHTTPError,
    PreparedToolset,
    RunContext,
    Tool,
    UsageLimits,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.settings import ModelSettings, ThinkingEffort
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

from socialhood.agent import executor
from socialhood.agent.context import AgentContext
from socialhood.agent.executor import RunLimitReached, RunState
from socialhood.agent.registry import (
    CURRENT_RELEASE,
    ToolContext,
    ToolRegistry,
    ToolSpec,
)
from socialhood.ai import prompts
from socialhood.ai.gemini import thinking_level
from socialhood.ai.metering import metered
from socialhood.ai.provider import AIError
from socialhood.models.agent import MAX_MODEL_TURNS, MAX_TOOL_CALLS, RUN_CREDIT_CAP
from socialhood.models.billing import AiFeature
from socialhood.observability.logging import get_logger
from socialhood.repositories.agent import REF_TYPE
from socialhood.settings import Settings

# Workers log structured lines; Pydantic AI's first-run banner would only add noise.
pydantic_ai.BANNER_ENABLED = False

log = get_logger(__name__)

PROMPT_TASK = "agent"
TEMPERATURE = 0.2  # the report at low temperature (§17)
MAX_OUTPUT_TOKENS = 2048
MODEL_CALL_TIMEOUT_S = 45.0
MODEL_ATTEMPTS = 2  # a timeout, 429 or 5xx is retried once (§15)
RETRYABLE_STATUS = frozenset({408, 429})
REPORT_RESERVE_S = 20.0  # wall time kept for the answer: under it, tools are withheld
FAKE_ANSWER = (
    "Ask Social Hood needs a Gemini key to answer. This server runs without one (AI_PROVIDER=fake)."
)
INTERRUPTED = "This call was interrupted before it returned. Call it again if you still need it."


class ModelUnavailable(Exception):
    """The model didn't answer after the retry (§15): the run fails with "The AI didn't
    respond"."""


class ModelNotConfigured(Exception):
    """No Gemini key: the run fails before any call."""


# ---------------------------------------------------------------- the model

_models: list[Model] = []
_tools: list[ToolRegistry] = []


@contextmanager
def use_model(model: Model) -> Iterator[Model]:
    """Tests: every run in the block uses ``model`` (a FunctionModel or TestModel)."""
    _models.append(model)
    try:
        yield model
    finally:
        _models.pop()


@contextmanager
def use_tools(tools: ToolRegistry) -> Iterator[ToolRegistry]:
    """Tests: runs and step labels in the block use ``tools`` instead of the shipped registry."""
    _tools.append(tools)
    try:
        yield tools
    finally:
        _tools.pop()


def current_tools() -> ToolRegistry:
    """The tool registry runs use: agent/tools/* loaded (or a test's registry)."""
    if _tools:
        return _tools[-1]
    from socialhood.agent.tools import load_tools

    return load_tools()


def model_name(settings: Settings) -> str:
    return settings.ai_model_agent or settings.ai_model_reply


def _fake_answer(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(FAKE_ANSWER)])


@lru_cache(maxsize=8)
def _google_model(name: str, api_key: str) -> Model:
    return GoogleModel(name, provider=GoogleProvider(api_key=api_key))


def base_model(settings: Settings) -> Model:
    """The model runs call (before metering): a test's, the fake's, or Gemini."""
    if _models:
        return _models[-1]
    if settings.ai_provider == "fake":
        return FunctionModel(_fake_answer, model_name="fake-agent")
    key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
    if not key:
        raise ModelNotConfigured("GEMINI_API_KEY is not set")
    return _google_model(model_name(settings), key)


def model_settings(settings: Settings) -> ModelSettings:
    level = thinking_level(model_name(settings), settings.ai_thinking_levels).lower()
    effort = cast(ThinkingEffort, level) if level in get_args(ThinkingEffort) else "low"
    return ModelSettings(temperature=TEMPERATURE, max_tokens=MAX_OUTPUT_TOKENS, thinking=effort)


class MeteredModel(WrapperModel):
    """Every model call of a run: checked, metered as agent_turn, retried once (§15, §17)."""

    def __init__(self, wrapped: Model, state: RunState) -> None:
        super().__init__(wrapped)
        self.state = state

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        await self.state.check_open()
        used = await self.state.credits_used()
        if used + 1 > RUN_CREDIT_CAP:
            raise RunLimitReached(
                "limit_reached", f"it would use more than {RUN_CREDIT_CAP} AI credits"
            )
        for attempt in range(1, MODEL_ATTEMPTS + 1):
            try:
                response = await self._call(messages, model_settings, model_request_parameters)
            except AIError as error:
                if not error.retryable or attempt == MODEL_ATTEMPTS:
                    raise ModelUnavailable(error.code) from error
                log.info("agent_turn_retry", run_id=str(self.state.run_id), code=error.code)
                continue
            await self.state.store_usage()
            return response
        raise AssertionError("unreachable")  # pragma: no cover

    async def _call(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        state = self.state
        async with metered(
            state.sessionmaker,
            workspace_id=state.workspace_id,
            feature=AiFeature.AGENT_TURN,
            ref_type=REF_TYPE,
            ref_id=state.run_id,
        ) as meter:
            meter.model = self.model_name
            at = datetime.now(UTC)
            started = time.monotonic()
            try:
                async with asyncio.timeout(MODEL_CALL_TIMEOUT_S):
                    response = await self.wrapped.request(
                        messages, model_settings, model_request_parameters
                    )
            except TimeoutError as error:
                raise AIError("timeout", "The model took too long", retryable=True) from error
            except ModelHTTPError as error:
                retryable = error.status_code in RETRYABLE_STATUS or error.status_code >= 500
                raise AIError("provider_error", str(error), retryable=retryable) from error
            except ModelAPIError as error:  # connection errors and the like
                raise AIError("provider_error", str(error), retryable=True) from error
            latency = round((time.monotonic() - started) * 1000)
            meter.model = response.model_name or self.model_name
            meter.input_tokens = response.usage.input_tokens
            meter.output_tokens = response.usage.output_tokens
            meter.latency_ms = latency
            state.last_turn = (at, latency)
        return response


# ---------------------------------------------------------------- tools


def _tool(spec: ToolSpec[Any, Any], state: RunState) -> Tool[ToolContext]:
    async def call(ctx: RunContext[ToolContext], **arguments: Any) -> dict[str, Any]:
        return await executor.execute(state, ctx.deps, spec, arguments)

    return Tool.from_schema(
        call,
        name=spec.name,
        description=spec.description,
        json_schema=spec.input_model.model_json_schema(),
        takes_ctx=True,
        sequential=True,
    )


def toolset(specs: Sequence[ToolSpec[Any, Any]], state: RunState) -> AbstractToolset[ToolContext]:
    """The run's tools, withheld once a cap is near so the model answers with what it has."""

    async def within_budget(
        ctx: RunContext[ToolContext], definitions: list[ToolDefinition]
    ) -> list[ToolDefinition]:
        spent = (
            ctx.usage.requests >= MAX_MODEL_TURNS - 1
            or ctx.usage.tool_calls >= MAX_TOOL_CALLS
            or state.time_left() < REPORT_RESERVE_S
            or await state.credits_used() + 2 > RUN_CREDIT_CAP
        )
        state.tools_withheld = spent
        return [] if spent else definitions

    functions = FunctionToolset([_tool(spec, state) for spec in specs], max_retries=1)
    return PreparedToolset(functions, within_budget)


# ---------------------------------------------------------------- prompt and messages


def system_prompt(context: AgentContext) -> str:
    local = context.now.astimezone(context.timezone)
    offset = local.strftime("%z")
    return prompts.load(PROMPT_TASK).render(
        workspace_name=context.workspace_name,
        brand_voice=context.brand_voice or "not described",
        accounts="; ".join(context.accounts) if context.accounts else "none connected",
        now=f"{local:%a %d %b %Y, %H:%M}",
        timezone=f"{context.timezone.key}, UTC{offset[:3]}:{offset[3:]}",
        max_tool_calls=str(MAX_TOOL_CALLS),
    )


def prompt_version() -> str:
    return prompts.load(PROMPT_TASK).version


def thread_messages(context: AgentContext) -> list[ModelMessage]:
    """The thread's earlier exchanges as earlier turns (context, not instructions)."""
    messages: list[ModelMessage] = []
    for exchange in context.history:
        answer = exchange.answer or "(This question didn't get an answer.)"
        messages.append(ModelRequest(parts=[UserPromptPart(exchange.request)]))
        messages.append(ModelResponse(parts=[TextPart(answer)]))
    return messages


def replayed_call(
    tool: str, args: dict[str, Any], call_id: str, outcome: dict[str, Any] | str, *, failed: bool
) -> list[ModelMessage]:
    """A step a crashed job finished, replayed to the model instead of running it again."""
    return [
        ModelResponse(parts=[ToolCallPart(tool, args, tool_call_id=call_id)]),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool, outcome, tool_call_id=call_id, outcome="failed" if failed else "success"
                )
            ]
        ),
    ]


async def answer(
    state: RunState,
    deps: ToolContext,
    context: AgentContext,
    *,
    request: str,
    replay: Sequence[ModelMessage] = (),
    usage: RunUsage | None = None,
    model: Model,
    settings: Settings,
) -> str:
    """The answer loop (R1): tools until the model writes the answer, within the caps. Raises
    what stopped it (RunStopped, RunLimitReached, QuotaExceeded, ModelUnavailable,
    UsageLimitExceeded, UnexpectedModelBehavior)."""
    specs = state.tools.available(release=CURRENT_RELEASE, role=deps.principal.role)
    agent: Agent[ToolContext, str] = Agent(
        output_type=str,
        instructions=system_prompt(context),
        deps_type=ToolContext,
        toolsets=[toolset(specs, state)],
        retries=1,
        name="ask_social_hood",
    )
    history = thread_messages(context)
    if replay:  # resuming: the request, then the steps a crashed job finished
        history += [ModelRequest(parts=[UserPromptPart(request)]), *replay]
    result = await agent.run(
        None if replay else request,
        message_history=history or None,
        deps=deps,
        model=MeteredModel(model, state),
        model_settings=model_settings(settings),
        usage_limits=UsageLimits(request_limit=MAX_MODEL_TURNS, tool_calls_limit=MAX_TOOL_CALLS),
        usage=usage,
    )
    return result.output
