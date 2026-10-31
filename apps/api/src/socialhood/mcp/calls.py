"""The path of every ``tools/list`` and ``tools/call`` (C-165; 01-design.md §2.4):

    principal → tenancy → workspace mode → scope → role → plan → rate limits and the daily
    cap → arguments → idempotency → the tool → audit

Each refusal before the tool is a tool error (``isError``) in the app's own words, never an HTTP
error, so the model can tell the member what to do (§6.1). Only an unknown tool name is a
protocol error. Every call, refused or not, leaves one audit row (mcp/audit.py).
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cached_property
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import mcp_types as types
from mcp.shared.exceptions import MCPError
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.entitlements import entitlement_error, quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError, FieldError
from socialhood.mcp import audit, http, results
from socialhood.mcp.context import ToolCall
from socialhood.mcp.idempotency import WriteGuard
from socialhood.mcp.principal import McpPrincipal, McpRequest
from socialhood.mcp.registry import MODE_ADMITS, MODE_ORDER, McpRegistry, McpTool, WriteOutput
from socialhood.models.identity import Workspace
from socialhood.models.mcp import AiConnectionsMode, CallOutcome, CredentialKind
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.security import ratelimit
from socialhood.services.analytics.common import zone
from socialhood.settings import Settings

log = get_logger(__name__)

DAILY_CAP = "mcp_calls_daily"
OFF = (
    "AI connections are turned off for this workspace. An owner or admin can turn them on in "
    "Amplychat, under Settings."
)
ROLE = "Your role in this workspace can't use this, as in the app. Ask an owner or admin."
MODE_WORDS = {
    AiConnectionsMode.READ_ONLY: "only read",
    AiConnectionsMode.READ_DRAFTS: "only read and prepare drafts",
}
RATE_LIMITED = "Too many requests from AI apps just now. Try again in {s} seconds."


@dataclass(frozen=True)
class CallEnv:
    """The app's resources a call uses."""

    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    settings: Settings
    http: httpx.AsyncClient

    @cached_property
    def deps(self) -> PlatformDeps:
        """The platform deps tools take, with the agent's visuals off (they're the web's Ask
        panel's). Built on first use: an app that never serves a call needs no token keys."""
        no_visuals = self.settings.model_copy(update={"agent_visuals_enabled": False})
        return deps_from(self.http, no_visuals)

    @property
    def plans_url(self) -> str | None:
        site = (self.settings.site_url or "").rstrip("/")
        return f"{site}/pricing" if site else None


# ---------------------------------------------------------------- the workspace's mode


def plan_cap(plan: str) -> AiConnectionsMode:
    """The most a plan allows (D2: Free reads and saves drafts; Pro and Max everything)."""
    allowed = {AiConnectionsMode(m) for m in entitlement(plan, "ai_connections")}
    return max(allowed, key=MODE_ORDER.index)


def effective_mode(setting: str, plan: str) -> AiConnectionsMode:
    """The workspace's own setting, capped by its plan."""
    return min(AiConnectionsMode(setting), plan_cap(plan), key=MODE_ORDER.index)


async def workspace_state(
    session: AsyncSession, principal: McpPrincipal
) -> tuple[Workspace, str, AiConnectionsMode]:
    workspace = await session.get(Workspace, principal.workspace_id)
    if workspace is None:  # deleted between authentication and here
        raise ApiError("not_found", "This workspace no longer exists.")
    plan = await current_plan(session)
    return workspace, plan, effective_mode(workspace.ai_connections_mode, plan)


# ---------------------------------------------------------------- tools/list


async def list_tools(
    registry: McpRegistry, env: CallEnv, principal: McpPrincipal
) -> list[types.Tool]:
    with workspace_scope(principal.workspace_id):
        async with env.sessionmaker() as session:
            _, _, mode = await workspace_state(session, principal)
    return [
        t.definition()
        for t in registry.visible(scopes=principal.scopes, role=principal.role, mode=mode)
    ]


# ---------------------------------------------------------------- tools/call


class _Refused(Exception):
    def __init__(self, error: ApiError, *, challenge: str | None = None) -> None:
        super().__init__(error.code)
        self.error = error
        # OAuth step-up: a WWW-Authenticate value for the result's _meta (ChatGPT, §3.1).
        self.challenge = challenge


# The tool result's key ChatGPT reads to show its "connect again with more access" UI.
WWW_AUTHENTICATE_META = "mcp/www_authenticate"


def _gate(
    tool: McpTool[Any, Any],
    principal: McpPrincipal,
    workspace: Workspace,
    plan: str,
    settings: Settings | None = None,
) -> None:
    """Mode, scope, role and plan, in that order (the first refusal is the one reported).

    A missing scope on an OAuth connection is a step-up (§3.4): the member can allow more by
    connecting again. Spec-following clients got an HTTP 403 before the call reached here
    (mcp/http.py); for the rest the tool error carries the same challenge in
    ``_meta["mcp/www_authenticate"]``, which ChatGPT turns into its linking UI."""
    mode = effective_mode(workspace.ai_connections_mode, plan)
    if mode is AiConnectionsMode.OFF and not tool.always_listed:
        raise _Refused(ApiError("forbidden", OFF))
    if tool.scope not in principal.scopes and principal.credential is CredentialKind.OAUTH:
        text = http.insufficient_scope_text(tool.scope)
        challenge = (
            http.scope_challenge(settings, principal, tool.scope, text) if settings else None
        )
        raise _Refused(ApiError("forbidden", text), challenge=challenge)
    if tool.scope not in principal.scopes:
        raise _Refused(
            ApiError(
                "forbidden",
                f"This connection doesn't have the {tool.scope} scope. Connect again with it "
                "(for an API key: make a new key with that scope).",
            )
        )
    if not tool.allowed_for(scopes=principal.scopes, role=principal.role):
        raise _Refused(ApiError("forbidden", ROLE))
    if tool.admitted_by(mode):
        return
    if tool.access in MODE_ADMITS[AiConnectionsMode(workspace.ai_connections_mode)]:
        raise _Refused(entitlement_error("ai_connections"))  # the setting allows it, the plan not
    words = MODE_WORDS.get(mode, "not do this")
    raise _Refused(
        ApiError(
            "forbidden",
            f"This workspace lets AI apps {words}. An owner or admin can change that in "
            "Amplychat, under Settings.",
        )
    )


async def _limit(env: CallEnv, name: str, subject: str) -> None:
    if not env.settings.rate_limits_enabled:
        return
    try:
        wait = await ratelimit.hit(env.redis, ratelimit.LIMITS[name], subject)
    except Exception as error:
        log.warning("rate_limit_unavailable", limit=name, error=type(error).__name__)
        return
    if wait > 0:
        seconds = max(1, math.ceil(wait))
        raise _Refused(
            ApiError(
                "rate_limited",
                RATE_LIMITED.format(s=seconds),
                headers={"Retry-After": str(seconds)},
            )
        )


async def _daily_cap(env: CallEnv, principal: McpPrincipal, plan: str, now: datetime) -> None:
    limit = entitlement(plan, DAILY_CAP)
    if limit is None:
        return
    key = f"mcp-calls:{principal.workspace_id}:{now:%Y-%m-%d}"
    try:
        used = int(await env.redis.incr(key))
        if used == 1:
            await env.redis.expire(key, 2 * 86_400)
    except Exception as error:
        log.warning("mcp_daily_cap_unavailable", error=type(error).__name__)
        return
    if used > limit:
        raise _Refused(
            quota_error(
                DAILY_CAP,
                limit,
                f"Your plan includes {limit:,} AI app tool calls a day. They reset at midnight "
                "UTC.",
            )
        )


def _invalid(error: ValidationError) -> ApiError:
    fields = [
        FieldError(".".join(str(p) for p in e["loc"]) or "arguments", e["msg"])
        for e in error.errors(include_url=False)
    ]
    return ApiError(
        "validation_error", "Some arguments aren't valid. Fix them and try again.", errors=fields
    )


def client_of(
    meta: Mapping[str, Any] | None, user_agent: str | None
) -> tuple[str | None, str | None]:
    """The client's name and version: the request's ``clientInfo`` (2026-07-28 ``_meta``), else
    the User-Agent header."""
    info = (meta or {}).get(types.CLIENT_INFO_META_KEY)
    if isinstance(info, Mapping) and info.get("name"):
        version = info.get("version")
        return str(info["name"]), str(version) if version is not None else None
    return user_agent, None


async def call_tool(
    registry: McpRegistry,
    env: CallEnv,
    request: McpRequest,
    name: str,
    arguments: dict[str, Any],
    *,
    meta: Mapping[str, Any] | None = None,
) -> types.CallToolResult:
    tool = registry.get(name)
    if tool is None:
        raise MCPError(types.INVALID_PARAMS, f"Unknown tool: {name[:64]}")
    principal = request.principal
    started = time.monotonic()
    outcome, code = CallOutcome.OK, None
    try:
        result = await _run(tool, env, principal, arguments)
    except _Refused as refused:
        outcome, code = CallOutcome.REFUSED, refused.error.code
        result = results.failure(refused.error, plans_url=env.plans_url)
        if refused.challenge is not None:
            result.meta = {WWW_AUTHENTICATE_META: [refused.challenge]}
    except ApiError as error:
        outcome, code = CallOutcome.ERROR, error.code
        result = results.failure(error, plans_url=env.plans_url)
    except Exception:
        log.exception("mcp_tool_failed", tool=name)
        outcome, code = CallOutcome.ERROR, "internal"
        result = results.failure(ApiError("internal", results.INTERNAL))
    client_name, client_version = client_of(meta, request.user_agent)
    await audit.record(
        env.sessionmaker,
        audit.CallRecord(
            principal=principal,
            tool=name,
            arguments=arguments,
            outcome=outcome,
            error_code=code,
            latency_ms=int((time.monotonic() - started) * 1000),
            client_name=client_name,
            client_version=client_version,
            request_id=request.request_id,
        ),
    )
    return result


async def _run(
    tool: McpTool[Any, Any], env: CallEnv, principal: McpPrincipal, arguments: dict[str, Any]
) -> types.CallToolResult:
    now = datetime.now(UTC)
    with workspace_scope(principal.workspace_id):
        async with env.sessionmaker() as session:
            workspace, plan, mode = await workspace_state(session, principal)
            _gate(tool, principal, workspace, plan, env.settings)
            await _limit(env, "mcp", str(principal.credential_id))
            await _limit(env, "mcp_workspace", str(principal.workspace_id))
            await _daily_cap(env, principal, plan, now)
            try:
                args = tool.input_model.model_validate(arguments)
            except ValidationError as error:
                raise _Refused(_invalid(error)) from error
            guard = (
                None
                if tool.read_only
                else WriteGuard(
                    env.redis,
                    principal,
                    tool.name,
                    args.model_dump(mode="json"),
                    tool.dedupe_window_s,
                )
            )
            if guard is not None and (stored := await guard.begin()) is not None:
                replay = tool.output_model.model_validate(stored)
                assert isinstance(replay, WriteOutput)
                return results.success(
                    replay.model_copy(update={"duplicate_of_previous_call": True})
                )
            call = ToolCall(
                principal=principal,
                session=session,
                sessionmaker=env.sessionmaker,
                redis=env.redis,
                settings=env.settings,
                deps=env.deps,
                workspace=workspace,
                plan=plan,
                mode=mode,
                now=now,
                timezone=_zone(workspace.timezone),
            )
            try:
                output = await tool.handler(call, args)
                if tool.read_only:
                    await session.rollback()
                else:
                    await session.commit()
            except BaseException:
                await session.rollback()
                if guard is not None:
                    await guard.release()
                raise
            if not isinstance(output, tool.output_model):
                raise TypeError(f"tool {tool.name} returned {type(output).__name__}")
            if guard is not None:
                await guard.complete(output.model_dump(mode="json"))
            return results.success(output)


def _zone(name: str | None) -> ZoneInfo:
    return zone(name or "UTC")
