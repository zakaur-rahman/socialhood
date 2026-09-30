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
  - ``DELETE /__e2e/users/{clerk_user_id}``: a signed-up user's workspaces (every tenant row
    cascades) and row (F-01). Other test data goes when the launcher drops the database.

It refuses to start unless the sandbox is on, Dodo is the fake and the app is not in production.
"""

from __future__ import annotations

import hmac
import os
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import delete

from socialhood.auth.deps import CurrentUser, Owner, Session
from socialhood.billing.registry import _process_fake
from socialhood.errors import ApiError
from socialhood.main import create_app
from socialhood.models.identity import User, Workspace
from socialhood.models.media import AssetPurpose, MediaAsset, ResourceType
from socialhood.repositories import users, workspaces
from socialhood.services.provisioning import slugify
from socialhood.settings import get_settings

settings = get_settings()
SEED_TOKEN = os.environ.get("E2E_SEED_TOKEN", "")
if (
    settings.is_production
    or not settings.sandbox_platform_enabled
    or settings.dodo_provider != "fake"
    or len(SEED_TOKEN) < 16
):
    raise RuntimeError(
        "The e2e API needs SANDBOX_PLATFORM_ENABLED=true, DODO_PROVIDER=fake, "
        "E2E_SEED_TOKEN and a non-production APP_ENV"
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
