"""The PA contract's shared names agree with each other (FR-AGT-01…10, TR-AGT-02, TR-AGT-03,
TR-AGT-08): the API's statuses, tiers and modes are the stored ones, the tool registry refuses a
spec that breaks TR-AGT-03 (a tool without a tier first of all), event payloads are picks of the
REST shapes, plans are typed data, and every PA route is in the API."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any, get_args

import pydantic_ai
import pydantic_ai.models
import pytest
from pydantic import BaseModel, ValidationError
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from socialhood.agent import tools
from socialhood.agent.plan import Condition, Plan, Ref, Step
from socialhood.agent.registry import (
    CURRENT_RELEASE,
    DraftResult,
    Release,
    ToolContext,
    ToolRegistry,
    ToolRegistryError,
    ToolResult,
    ToolSpec,
    registry,
)
from socialhood.billing.plans import CREDIT_COSTS
from socialhood.main import create_app
from socialhood.models.agent import (
    DEFAULT_LIMITS,
    DEFAULT_PERMISSIONS,
    MAX_PLAN_STEPS,
    AgentCapability,
    AgentMode,
    AgentRunSource,
    AgentRunStatus,
    ApprovalStatus,
    RiskTier,
    StepKind,
    StepStatus,
)
from socialhood.models.billing import AiFeature
from socialhood.models.identity import Role
from socialhood.realtime.events import EventType
from socialhood.schemas.agent import (
    ActionKind,
    AgentLimits,
    AgentModeName,
    AgentPermissions,
    AgentRun,
    AgentRunEvent,
    AgentRunSourceName,
    AgentRunStatusName,
    AgentStep,
    AgentStepProgress,
    ApprovalStatusName,
    AutomationDraftAction,
    CommentReplyAction,
    RiskTierName,
    ScheduleMessageAction,
    StepKindName,
    StepStatusName,
)

# operation id -> (method, path, pending task; None once built): §2.15's agent rows.
PA_ROUTES = {
    "create_agent_run": ("post", "/v1/w/{wid}/agent/runs", None),
    "list_agent_runs": ("get", "/v1/w/{wid}/agent/runs", None),
    "get_agent_run": ("get", "/v1/w/{wid}/agent/runs/{run_id}", None),
    "cancel_agent_run": ("post", "/v1/w/{wid}/agent/runs/{run_id}/cancel", None),
    "list_agent_threads": ("get", "/v1/w/{wid}/agent/threads", None),
    "get_agent_policy": ("get", "/v1/w/{wid}/agent/policy", None),
    "update_agent_policy": ("put", "/v1/w/{wid}/agent/policy", "R2"),
    "list_agent_approvals": ("get", "/v1/w/{wid}/agent/approvals", "R2"),
    "approve_agent_approval": (
        "post",
        "/v1/w/{wid}/agent/approvals/{approval_id}/approve",
        "R2",
    ),
    "reject_agent_approval": ("post", "/v1/w/{wid}/agent/approvals/{approval_id}/reject", "R2"),
}


def test_api_names_are_the_stored_ones() -> None:
    assert set(get_args(AgentRunStatusName)) == set(AgentRunStatus)
    assert set(get_args(AgentRunSourceName)) == set(AgentRunSource)
    assert set(get_args(AgentModeName)) == set(AgentMode)
    assert set(get_args(StepKindName)) == set(StepKind)
    assert set(get_args(StepStatusName)) == set(StepStatus)
    assert set(get_args(RiskTierName)) == set(RiskTier)
    assert set(get_args(ApprovalStatusName)) == set(ApprovalStatus)


def test_policy_shapes_match_the_stored_defaults() -> None:
    assert set(AgentPermissions.model_fields) == set(AgentCapability)
    assert AgentPermissions.model_validate(DEFAULT_PERMISSIONS).model_dump() == DEFAULT_PERMISSIONS
    assert set(AgentLimits.model_fields) == set(DEFAULT_LIMITS)
    assert AgentLimits.model_validate(DEFAULT_LIMITS).model_dump() == DEFAULT_LIMITS
    assert not any(DEFAULT_PERMISSIONS.values())


def test_action_cards_cover_every_kind() -> None:
    kinds = [
        get_args(model.model_fields["kind"].annotation)
        for model in (ScheduleMessageAction, CommentReplyAction, AutomationDraftAction)
    ]
    assert kinds == [(kind,) for kind in get_args(ActionKind)]
    for model in (ScheduleMessageAction, CommentReplyAction, AutomationDraftAction):
        assert model.model_fields["kind"].is_required()  # the web narrows on it


def test_agent_turns_cost_one_credit() -> None:
    assert CREDIT_COSTS["agent_turn"] == 1
    assert set(CREDIT_COSTS) == set(AiFeature)


def test_agent_events_are_published_types() -> None:
    assert {"agent.run.updated", "agent.step", "agent.completed"} <= set(get_args(EventType))


def _shared(small: type[BaseModel], big: type[BaseModel]) -> list[str]:
    """Fields of ``small`` that ``big`` also has, checked to have the same type."""
    shared = [name for name in small.model_fields if name in big.model_fields]
    for name in shared:
        assert small.model_fields[name].annotation == big.model_fields[name].annotation, name
    return shared


def test_event_payloads_are_picks_of_the_rest_shapes() -> None:
    """The web types agent events as picks of AgentStep and AgentRun (they aren't in OpenAPI)."""
    assert set(_shared(AgentStepProgress, AgentStep)) == set(AgentStepProgress.model_fields)
    extra = set(AgentRunEvent.model_fields) - set(_shared(AgentRunEvent, AgentRun))
    assert extra == {"requested_by_user_id", "step_count"}
    # Runs belong to their requester: no text of theirs travels on the workspace's stream.
    for model in (AgentRunEvent, AgentStepProgress):
        assert not {"request", "answer", "answer_refs", "args", "result"} & set(model.model_fields)


# ---------------------------------------------------------------- the registry (TR-AGT-03)


class _Input(BaseModel):
    account: str | None = None


class _Result(ToolResult):
    count: int = 0


class _Draft(DraftResult):
    pass


async def _handler(ctx: ToolContext, args: Any) -> Any:
    raise NotImplementedError


def _spec(**changes: Any) -> ToolSpec[Any, Any]:
    spec: ToolSpec[Any, Any] = ToolSpec(
        name="get_latest_post",
        label="Looking up your latest post",
        description="The account's most recent post with its age and format.",
        input_model=_Input,
        result_model=_Result,
        tier=RiskTier.READ,
        release=Release.R1,
        handler=_handler,
    )
    return dataclasses.replace(spec, **changes)


def test_the_registry_refuses_a_tool_without_a_tier() -> None:
    tools_ = ToolRegistry()
    with pytest.raises(ToolRegistryError, match="has no risk tier"):
        tools_.register(_spec(tier=None))
    with pytest.raises(ToolRegistryError, match="has no risk tier"):
        tools_.register(_spec(tier="read"))  # a string is not a tier
    assert "get_latest_post" not in tools_
    assert len(tools_) == 0


def _sync_handler(ctx: ToolContext, args: Any) -> Any:
    raise NotImplementedError


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"name": "GetLatestPost"}, "snake_case"),
        ({"name": "x"}, "snake_case"),
        ({"label": " "}, "label and a description"),
        ({"description": ""}, "label and a description"),
        ({"release": "r1"}, "has no release"),
        ({"input_model": dict}, "input model"),
        ({"result_model": _Input}, "extend ToolResult"),
        ({"tier": RiskTier.DRAFT}, "extend DraftResult"),
        ({"tier": RiskTier.LOW, "release": Release.R2}, "needs a capability switch"),
        ({"capability": AgentCapability.SEND_REPLIES}, "can't have a capability switch"),
        (
            {"tier": RiskTier.HIGH, "capability": AgentCapability.SEND_REPLIES},
            "can't ship in R1",
        ),
        ({"handler": _sync_handler}, "async function"),
    ],
)
def test_the_registry_refuses_specs_that_break_the_rules(
    changes: dict[str, Any], problem: str
) -> None:
    tools_ = ToolRegistry()
    with pytest.raises(ToolRegistryError, match=problem):
        tools_.register(_spec(**changes))
    assert len(tools_) == 0


def test_the_registry_lists_tools_by_release_and_role() -> None:
    tools_ = ToolRegistry()
    read = tools_.register(_spec())
    draft = tools_.register(
        _spec(
            name="prepare_automation",
            tier=RiskTier.DRAFT,
            result_model=_Draft,
            min_role=Role.ADMIN,
        )
    )
    write = tools_.register(
        _spec(
            name="send_message",
            tier=RiskTier.HIGH,
            release=Release.R2,
            capability=AgentCapability.SEND_REPLIES,
        )
    )
    with pytest.raises(ToolRegistryError, match="already registered"):
        tools_.register(_spec())
    assert tools_.get("get_latest_post") is read
    assert tools_.get("nope") is None
    assert CURRENT_RELEASE == Release.R1
    assert tools_.available() == [read, draft]
    assert tools_.available(role=Role.AGENT) == [read]
    assert tools_.available(release=Release.R2) == [read, draft, write]


def test_the_shipped_tools_are_read_or_draft() -> None:
    """FR-AGT-02: no R1 tool changes anything (the modules are empty until TA.4)."""
    for spec in tools.load_tools():
        assert spec.tier in (RiskTier.READ, RiskTier.DRAFT) or spec.release != Release.R1
    assert tools.load_tools() is registry


# ---------------------------------------------------------------- plans (R2, FR-AGT-12)


def test_a_plan_is_typed_data() -> None:
    plan = Plan(
        goal="Schedule a similar post if the latest one did well",
        steps=[
            Step(id="s1", tool="get_latest_post", args={"account": "instagram"}),
            Step(
                id="s2",
                tool="compare_posts",
                refs={"post_id": Ref(step="s1", path="post.id")},
                depends_on=["s1"],
            ),
            Step(
                id="s3",
                tool="schedule_post",
                depends_on=["s2"],
                when=[
                    Condition(
                        left=Ref(step="s2", path="engagement_rate.delta_pct"), op=">", right=0
                    )
                ],
            ),
        ],
    )
    assert Plan.model_validate_json(plan.model_dump_json()) == plan
    with pytest.raises(ValidationError):
        Step(id="step1", tool="get_latest_post")
    with pytest.raises(ValidationError):
        Ref(step="s1", path="post id")
    with pytest.raises(ValidationError):
        Condition(left=Ref(step="s1", path="x"), op="=~", right=1)  # type: ignore[arg-type]
    too_many = [Step(id=f"s{i}", tool="get_posts") for i in range(1, MAX_PLAN_STEPS + 2)]
    with pytest.raises(ValidationError):
        Plan(goal="Too long", steps=too_many)


# ---------------------------------------------------------------- Pydantic AI (TR-AGT-02)


def test_pydantic_ai_is_installed_and_no_test_reaches_a_model() -> None:
    assert pydantic_ai.__version__
    assert GoogleModel.__name__ == "GoogleModel"
    assert GoogleProvider.__name__ == "GoogleProvider"
    for name in ("DeferredToolRequests", "DeferredToolResults", "ToolApproved", "ToolDenied"):
        assert hasattr(pydantic_ai, name)
    assert pydantic_ai.models.ALLOW_MODEL_REQUESTS is False


# ---------------------------------------------------------------- routes


def test_every_pa_route_is_in_the_api(api_settings: Any) -> None:
    openapi = create_app(api_settings).openapi()
    found = {
        operation["operationId"]: (method, path, operation.get("x-pending"))
        for path, operations in openapi["paths"].items()
        for method, operation in operations.items()
        if operation.get("operationId") in PA_ROUTES
    }
    assert found == PA_ROUTES
    assert {
        operation["tags"][0]
        for path, operations in openapi["paths"].items()
        if "/agent/" in path
        for operation in operations.values()
    } == {"agent"}
    assert "202" in openapi["paths"]["/v1/w/{wid}/agent/runs"]["post"]["responses"]


def test_a_run_answer_serialises_with_its_cards() -> None:
    run = AgentRun.model_validate(
        {
            "id": uuid.uuid4(),
            "thread_id": uuid.uuid4(),
            "request": "Schedule a message to Priya tomorrow at 10",
            "source": "ask",
            "mode": "read_only",
            "status": "succeeded",
            "answer": "Priya's window closes tomorrow at 8:12 AM [1].",
            "answer_refs": [{"kind": "conversation", "id": uuid.uuid4(), "label": "Priya Nair"}],
            "action_cards": [
                {
                    "kind": "schedule_message",
                    "label": "Schedule this message",
                    "route": "inbox/c1?schedule=1",
                    "note": "Priya's window closes tomorrow at 8:12 AM.",
                    "prefill": {"conversation_id": uuid.uuid4(), "text": "Your order ships Monday"},
                }
            ],
            "credits": 3,
            "created_at": "2026-09-29T10:00:00Z",
        }
    )
    [card] = run.action_cards
    assert isinstance(card, ScheduleMessageAction)
    assert card.prefill.send_at is None
    assert run.model_dump(mode="json")["action_cards"][0]["kind"] == "schedule_message"
