"""Plans and conditions (FR-AGT-12, TR-AGT-02; agent-architecture.html §4 Plan and conditions).

R2. For any request with a write, the planner returns a typed ``Plan``: numbered steps, each a
tool call that may depend on earlier steps and run only when its conditions hold. The plan is
validated (``validate``) and shown to the member before anything runs; the executor then runs it
itself. Conditions are data: the model writes them, code evaluates them (``evaluate``) on the
stored results of earlier steps, and every evaluation is recorded as a ``condition`` step. The
model is never asked whether a condition held.

Example ("if engagement is above my 30-day average and sentiment is positive, schedule a similar
post tomorrow at 7 PM"):

    s1 get_latest_post(account)
    s3 compare_posts(post_id ← s1.post.id, baseline=last 30 days)
    s4 sentiment_distribution(post_id ← s1.post.id)
    s7 schedule_post(...) when s3.engagement_rate.delta_pct > 0 and s4.positive_share >= 0.6

The functions below are the interface; their bodies come with the R2 plan-first work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import CURRENT_RELEASE, Release, ToolRegistry
from socialhood.models.agent import MAX_PLAN_STEPS

StepId = Annotated[str, Field(pattern=r"^s[1-9][0-9]?$")]  # "s1" … "s99"
# A dotted path into a step's typed result; list items by index ("items.0.id").
ResultPath = Annotated[
    str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")
]
Op = Literal[">", ">=", "<", "<=", "==", "!="]


class _PlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Ref(_PlanModel):
    """A value in an earlier step's stored result: ``Ref(step="s2", path="engagement_rate")`` is
    s2.engagement_rate."""

    step: StepId
    path: ResultPath


class Condition(_PlanModel):
    """``left op right``, where right is another value or a number."""

    left: Ref
    op: Op
    right: Ref | float


class Step(_PlanModel):
    """One tool call in a plan."""

    id: StepId
    tool: str  # a registered tool's name
    # The tool's arguments, validated by its input model once ``refs`` are filled in.
    args: dict[str, Any] = Field(default_factory=dict)
    # Arguments taken from earlier results: argument name → value, filled in before validation.
    refs: dict[str, Ref] = Field(default_factory=dict)
    depends_on: list[StepId] = Field(default_factory=list)
    # Every condition must hold (and); empty: the step always runs. A step whose condition
    # doesn't hold is skipped, and so are the steps that depend on it.
    when: list[Condition] = Field(default_factory=list)


class Plan(_PlanModel):
    """What the member sees before anything runs (FR-AGT-12)."""

    goal: str = Field(min_length=1, max_length=300)  # one line, in plain words
    steps: list[Step] = Field(min_length=1, max_length=MAX_PLAN_STEPS)


class ConditionOutcome(_PlanModel):
    """One evaluated condition, stored as a ``condition`` step's result."""

    held: bool
    left: Any = None  # the values compared, as found
    right: Any = None
    # Why it didn't hold when a value was missing or not comparable ("s3 has no
    # engagement_rate: the post has no reach yet"); the report says which data was missing.
    reason: str | None = None


class PlanProblem(_PlanModel):
    """Why a plan was refused; the first invalid plan goes back to the model once (§15)."""

    step: StepId | None = None
    message: str


class MissingValue(LookupError):
    """A Ref points at a step without a stored result, or a path that isn't in it."""


def resolve(ref: Ref, results: Mapping[str, Mapping[str, Any]]) -> Any:
    """The value at ``ref`` in ``results`` (step id → stored result); ``MissingValue`` when the
    step has no result or the path isn't there."""
    raise NotImplementedError("R2")


def evaluate(condition: Condition, results: Mapping[str, Mapping[str, Any]]) -> ConditionOutcome:
    """Evaluate one condition on stored results. A missing or non-comparable value makes it false
    with a reason, never an error."""
    raise NotImplementedError("R2")


def validate(
    plan: Plan, tools: ToolRegistry, *, release: Release = CURRENT_RELEASE
) -> Sequence[PlanProblem]:
    """Every problem with ``plan``, or none: each tool exists and has shipped, its arguments
    validate (refs aside), step ids are unique, ``depends_on``, ``refs`` and ``when`` name only
    earlier steps (so dependencies form a chain without cycles), at most MAX_PLAN_STEPS steps."""
    raise NotImplementedError("R2")
