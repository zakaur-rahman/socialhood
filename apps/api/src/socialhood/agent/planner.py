"""The planner (TR-AGT-02, FR-AGT-04, TA.2; agent-architecture.html §4 Planner, §15, §17).

A Pydantic AI agent, used only for the loop between the model and its tools. Run state, steps,
credits and audit are ours (models/agent.py); nothing here stores anything itself.

- Model: ``pydantic_ai.models.google.GoogleModel`` on ``settings.ai_model_agent`` (unset: the reply
  model, ``settings.ai_model_reply``) through ``pydantic_ai.providers.google.GoogleProvider``
  with ``settings.gemini_api_key``; the report at low temperature.
- Dependencies: ``agent.registry.ToolContext`` (session, workspace, principal, time zone, now,
  run id) as ``deps``; tools reach it as ``RunContext[ToolContext].deps``.
- Tools: ``registry.available(role=principal.role)``, each wrapped as a Pydantic AI tool whose
  arguments are validated by the spec's input model; every call goes through the executor, which
  persists it as a step before and after.
- Answer loop (R1): read and draft tools, at most MAX_TOOL_CALLS tool calls and MAX_MODEL_TURNS
  model turns (``pydantic_ai.UsageLimits(request_limit=…, tool_calls_limit=…)``), then the answer.
- Plan first (R2): any write returns a typed ``agent.plan.Plan`` instead; writes are then deferred
  (``pydantic_ai.ApprovalRequired`` / ``DeferredToolRequests``), decided by our gateway, and the
  run resumes with ``DeferredToolResults`` (``ToolApproved`` / ``ToolDenied``).
- Report: written from stored step results only (no new facts); every number cites its record
  as ``[n]`` into answer_refs, and the time range and sample size are stated (FR-AGT-04).
- Metering: every model call is wrapped in ``ai.metering.metered`` with feature ``agent_turn``
  (1 credit, ref_type ``agent_run``); a run stops asking the model past RUN_CREDIT_CAP or when
  credits run out, and reports what it finished.
- Failures (§15): a model timeout or 5xx is retried once, then the run fails with "The AI didn't
  respond" (credits for failed calls refunded); an invalid tool call goes back to the model once.
- Prompt: ai/prompts/agent.v1.md (versioned like the other prompts).

Tests never reach Gemini: ``pydantic_ai.models.ALLOW_MODEL_REQUESTS`` is off under pytest, and
tests script the model with ``pydantic_ai.models.function.FunctionModel`` or ``TestModel``.
"""

from __future__ import annotations
