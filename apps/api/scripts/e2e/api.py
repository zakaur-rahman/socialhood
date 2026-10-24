"""The API as the end-to-end suite runs it (T9.4, TR-TEST-01; apps/web/e2e). Test-only: the
launcher (scripts/e2e-stack.mjs) serves it as ``api:app`` from this folder, never anything else.

It is the normal app (``socialhood.main``) plus two things the suite needs:

- the fake Dodo's products: ``DODO_PROVIDER=fake`` starts with none, so checkout (F-15) would
  answer "service unavailable"; the Pro and Max products from the settings are added here;
- seed routes under ``/__e2e`` that need ``X-E2E-Token: $E2E_SEED_TOKEN``:

  - ``POST /__e2e/workspaces {name}``: a fresh workspace owned by the signed-in user (Clerk
    bearer), so every spec file starts clean (the API has no "new workspace" endpoint in R1);
  - ``POST /__e2e/workspaces/{wid}/media-assets``: an image in the media library without
    Cloudinary (F-13), as a finished signed upload would have registered it;
  - ``POST /__e2e/workspaces/{wid}/agent-runs``: a finished Ask run of the signed-in owner
    (GR-38), because the fake model calls no tools. With ``visual`` it also seeds account
    metrics for the last ``days`` days and the ``days`` before them, and the run's
    compare_periods step holds the visual the real service and builder make from them, so the
    spec can check the cards against GET …/analytics/account-metrics;
  - ``POST /__e2e/workspaces/{wid}/plan {plan}`` (GR-27): the workspace's plan, without Dodo's
    checkout (F-15 covers that), for specs that need Pro;
  - ``GET /__e2e/google-sheets/{sheet_id}`` and ``POST …/{sheet_id}/delete`` (GR-27): the header
    and rows the fake Google holds for a sheet (GOOGLE_PROVIDER=fake keeps them in Redis, which the
    API and the worker share), and deleting it as the person would in Google Drive;
  - ``POST /__e2e/workspaces/{wid}/agent-proposals`` (GR-36): a finished Ask run whose draft step
    called propose_flow or propose_segment through the real tool and gateway (the fake model
    calls no tools), so the spec has a pending approval and its card to decide in the browser;
  - ``PUT /__e2e/workspaces/{wid}/plan {plan}``: the workspace's plan (GR-25: the public API is Pro
    and Max), without a checkout;
  - ``DELETE /__e2e/users/{clerk_user_id}``: a signed-up user's workspaces (every tenant row
    cascades) and row (F-01). Other test data goes when the launcher drops the database.

It refuses to start unless the sandbox is on, Dodo and Google are fakes and the app is not in
production.
"""

from __future__ import annotations

import hmac
import os
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete

from socialhood.agent import visuals
from socialhood.agent.registry import Principal, ToolContext
from socialhood.agent.tools import load_tools
from socialhood.auth.deps import CurrentUser, Owner, Session
from socialhood.billing.registry import _process_fake
from socialhood.errors import ApiError
from socialhood.google.registry import process_fake
from socialhood.main import create_app
from socialhood.models.agent import AgentRun, AgentStep
from socialhood.models.analytics import AccountDailyMetric
from socialhood.models.billing import Subscription
from socialhood.models.identity import Role, User, Workspace
from socialhood.models.media import AssetPurpose, MediaAsset, ResourceType
from socialhood.platforms.capabilities import Capability
from socialhood.repositories import social_accounts, users, workspaces
from socialhood.repositories.base import scoped_update
from socialhood.services.analytics import account_metrics
from socialhood.services.analytics.common import View
from socialhood.services.provisioning import slugify
from socialhood.settings import get_settings

settings = get_settings()
SEED_TOKEN = os.environ.get("E2E_SEED_TOKEN", "")
if (
    settings.is_production
    or not settings.sandbox_platform_enabled
    or settings.dodo_provider != "fake"
    or settings.google_provider != "fake"
    or len(SEED_TOKEN) < 16
):
    raise RuntimeError(
        "The e2e API needs SANDBOX_PLATFORM_ENABLED=true, DODO_PROVIDER=fake, "
        "GOOGLE_PROVIDER=fake, E2E_SEED_TOKEN and a non-production APP_ENV"
    )

dodo = _process_fake()
for product in (settings.dodo_product_pro_monthly, settings.dodo_product_max_monthly):
    if product:
        dodo.add_product(product, amount_minor=99900, currency="INR", trial_period_days=7)


def _seed_token(x_e2e_token: Annotated[str, Header()] = "") -> None:
    if not hmac.compare_digest(x_e2e_token, SEED_TOKEN):
        raise ApiError("not_found")


router = APIRouter(prefix="/__e2e", include_in_schema=False, dependencies=[Depends(_seed_token)])


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class AssetIn(BaseModel):
    filename: str = "e2e-post.jpg"
    width: int = 1080
    height: int = 1080


class AssetOut(BaseModel):
    id: uuid.UUID
    public_id: str
    secure_url: str


@router.post("/workspaces", status_code=201)
async def create_workspace(body: WorkspaceIn, user: CurrentUser, session: Session) -> WorkspaceOut:
    slug = f"{slugify(body.name)[:36].strip('-')}-{secrets.token_hex(3)}"
    workspace, children = workspaces.new_workspace_rows(
        name=body.name, slug=slug, owner_id=user.id, today=datetime.now(UTC).date()
    )
    session.add(workspace)
    await session.flush()
    session.add_all(children)
    await session.flush()
    await users.set_last_workspace(session, user.id, workspace.id)
    await session.commit()
    return WorkspaceOut(id=workspace.id, slug=workspace.slug, name=workspace.name)


class PlanIn(BaseModel):
    plan: str = Field(pattern="^(free|pro|max)$", max_length=4)


@router.post("/workspaces/{wid}/plan", status_code=204)
async def set_plan(body: PlanIn, ctx: Owner, session: Session) -> None:
    """GR-19: put the workspace on a plan, so a second seat exists without a checkout."""
    await session.execute(
        scoped_update(Subscription, workspace_id=ctx.workspace_id).values(plan=body.plan)
    )
    await session.commit()


@router.post("/workspaces/{wid}/media-assets", status_code=201)
async def create_media_asset(body: AssetIn, ctx: Owner, session: Session) -> AssetOut:
    stem = body.filename.rsplit(".", 1)[0]
    public_id = f"ws/{ctx.workspace_id}/{AssetPurpose.POST.value}/{stem}-{secrets.token_hex(4)}"
    secure_url = f"https://res.cloudinary.com/e2e/image/upload/v1/{public_id}.jpg"
    asset = MediaAsset(
        public_id=public_id,
        resource_type=ResourceType.IMAGE.value,
        purpose=AssetPurpose.POST.value,
        format="jpg",
        original_filename=body.filename,
        secure_url=secure_url,
        bytes=180_000,
        width=body.width,
        height=body.height,
        created_by_user_id=ctx.user.id,
    )
    session.add(asset)
    await session.commit()
    return AssetOut(id=asset.id, public_id=public_id, secure_url=secure_url)


class AgentRunIn(BaseModel):
    request: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)
    account_id: uuid.UUID | None = None
    visual: bool = False  # seed account metrics and attach a metric_comparison visual
    days: int = Field(default=14, ge=2, le=60)


class AgentRunOut(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID


@router.post("/workspaces/{wid}/agent-runs", status_code=201)
async def create_agent_run(body: AgentRunIn, ctx: Owner, session: Session) -> AgentRunOut:
    now = datetime.now(UTC)
    steps: list[dict[str, object]] = []
    if body.visual:
        if body.account_id is None:
            raise ApiError("validation_error", "A visual needs an account_id.")
        acct = await social_accounts.get(session, body.account_id)
        if acct is None:
            raise ApiError("not_found")
        view = View(
            timezone=ctx.workspace.timezone,
            now=now,
            capabilities=lambda _: frozenset({Capability.ACCOUNT_INSIGHTS}),
        )
        last = account_metrics.complete_until(view)
        current = account_metrics.span_of(last - timedelta(days=body.days - 1), last)
        previous = account_metrics.span_of(
            current.since - timedelta(days=body.days), current.since - timedelta(days=1)
        )
        for span, reach, taps in ((previous, 80, 4), (current, 100, 5)):
            for i in range(span.days):
                day: date = span.since + timedelta(days=i)
                session.add(
                    AccountDailyMetric(
                        social_account_id=acct.id,
                        date=day,
                        followers_count=1000 + (day - previous.since).days,
                        metrics={"reach": reach, "total_interactions": 10, "unfollows": taps},
                        captured_at=now,
                    )
                )
        await session.flush()
        figures = await account_metrics.account_metrics(
            session,
            view,
            current=current,
            previous=previous,
            account_id=acct.id,
            metrics=["reach", "interactions", "followers", "unfollows"],
        )
        visual = visuals.metric_comparison(
            figures, account_label=f"@{acct.username}" if acct.username else None, note=None
        )
        steps.append(
            {
                "tool": "compare_periods",
                "result": {
                    "summary": "Compared two periods",
                    "refs": [],
                    "caveats": [],
                    "visual": visual.model_dump(mode="json"),
                },
            }
        )
    run_id = uuid.uuid4()
    run = AgentRun(
        id=run_id,
        thread_id=run_id,
        requested_by_user_id=ctx.user.id,
        request=body.request,
        mode="read_only",
        status="succeeded",
        answer=body.answer,
        answer_refs=[],
        model="e2e",
        prompt_version="agent.v4",
        credits=1,
        started_at=now - timedelta(seconds=3),
        completed_at=now,
    )
    session.add(run)
    await session.flush()
    for ordinal, step in enumerate(steps):
        session.add(
            AgentStep(
                run_id=run.id,
                ordinal=ordinal,
                idempotency_key=f"{run.id}:{ordinal}",
                kind="tool",
                tool=str(step["tool"]),
                tier="read",
                args={},
                status="succeeded",
                attempts=1,
                latency_ms=40,
                result=step["result"],
                started_at=now - timedelta(seconds=2),
                completed_at=now - timedelta(seconds=1),
            )
        )
    await session.commit()
    return AgentRunOut(id=run.id, thread_id=run.thread_id)


@router.get("/google-sheets/{sheet_id}")
async def google_sheet(sheet_id: str, request: Request) -> dict[str, Any]:
    fake = process_fake(settings, request.app.state.redis)
    return {"header": await fake.header(sheet_id), "rows": await fake.rows(sheet_id)}


@router.post("/google-sheets/{sheet_id}/delete", status_code=204)
async def delete_google_sheet(sheet_id: str, request: Request) -> None:
    await process_fake(settings, request.app.state.redis).delete_sheet(sheet_id)


class ProposalIn(BaseModel):
    request: str = Field(min_length=1, max_length=500)
    kind: Literal["flow", "segment"]
    name: str = Field(min_length=1, max_length=60)
    keyword: str = Field(default="PRICE", min_length=1, max_length=40)  # flows: the comment trigger
    tag: str = Field(default="vip", min_length=1, max_length=40)  # segments: must exist


class ProposalOut(BaseModel):
    run_id: uuid.UUID
    thread_id: uuid.UUID
    approval_id: uuid.UUID


@router.post("/workspaces/{wid}/agent-proposals", status_code=201)
async def create_agent_proposal(
    request: Request, body: ProposalIn, ctx: Owner, session: Session
) -> ProposalOut:
    now = datetime.now(UTC)
    tool_name = "propose_flow" if body.kind == "flow" else "propose_segment"
    args: dict[str, object] = (
        {
            "request": body.request,
            "name": body.name,
            "trigger": "comment_keyword",
            "keywords": [body.keyword],
            "steps": [{"type": "send", "text": "Here is our price list: example.com/prices"}],
        }
        if body.kind == "flow"
        else {"name": body.name, "tags": [body.tag], "has_email": True}
    )
    run_id = uuid.uuid4()
    run = AgentRun(
        id=run_id,
        thread_id=run_id,
        requested_by_user_id=ctx.user.id,
        request=body.request,
        mode="read_only",
        status="succeeded",
        answer="I've drafted this and it is waiting for your approval. Nothing is saved yet.",
        answer_refs=[],
        model="e2e",
        prompt_version="agent.v4",
        credits=1,
        started_at=now - timedelta(seconds=3),
        completed_at=now,
    )
    session.add(run)
    await session.flush()
    step = AgentStep(
        run_id=run.id,
        ordinal=0,
        idempotency_key=f"{run.id}:0",
        kind="tool",
        tool=tool_name,
        tier="draft",
        args=args,
        status="running",
        attempts=1,
        latency_ms=40,
        started_at=now - timedelta(seconds=2),
    )
    session.add(step)
    await session.flush()
    spec = load_tools().get(tool_name)
    if spec is None:
        raise ApiError("not_found")
    tool_ctx = ToolContext(
        session=session,
        sessionmaker=request.app.state.sessionmaker,
        platform=None,  # type: ignore[arg-type]  # the proposal tools make no platform calls
        workspace_id=ctx.workspace_id,
        timezone=ZoneInfo(ctx.workspace.timezone),
        now=now,
        principal=Principal(user_id=ctx.user.id, role=Role.OWNER),
        run_id=run.id,
        step_id=step.id,
        step_key=step.idempotency_key,
    )
    result = await spec.handler(tool_ctx, spec.input_model.model_validate(args))
    step.status = "succeeded"
    step.result = result.model_dump(mode="json")
    step.completed_at = now
    await session.commit()
    return ProposalOut(
        run_id=run.id,
        thread_id=run.thread_id,
        approval_id=result.approval_id,  # type: ignore[attr-defined]
    )


@router.delete("/users/{clerk_user_id}", status_code=204)
async def delete_user(clerk_user_id: str, session: Session) -> None:
    user = await users.get_by_clerk_id(session, clerk_user_id)
    if user is None:
        return
    # Test data only, so no purge job: the row goes at once and every tenant row cascades.
    await session.execute(delete(Workspace).where(Workspace.owner_user_id == user.id))
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()


app = create_app(settings)
app.include_router(router)
