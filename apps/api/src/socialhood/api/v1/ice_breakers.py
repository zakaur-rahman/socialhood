"""Conversation starters (GR-11): an Instagram account's ice breakers. Any member can read them;
owners and admins change them (they set up automations). Saving pushes the list to Instagram: a
failed push still keeps the list and is reported as ``sync_error``. Another workspace's account is
404 not_found; a WhatsApp account gets a validation error."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Request

from socialhood.auth.deps import AnyMember, CanManageChannels, Session
from socialhood.models.automations import IceBreaker as IceBreakerRow
from socialhood.platforms.deps import deps_from
from socialhood.repositories import automation_runs as runs
from socialhood.schemas.ice_breakers import (
    IceBreaker,
    IceBreakerList,
    IceBreakersUpdate,
)
from socialhood.services import connections
from socialhood.services import ice_breakers as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["ice-breakers"])


async def _out(
    session: Session, rows: list[IceBreakerRow], *, error: str | None = None
) -> IceBreakerList:
    items: list[IceBreaker] = []
    for row in rows:
        automation = (
            await runs.get_automation(session, row.automation_id) if row.automation_id else None
        )
        items.append(
            IceBreaker(
                id=row.id,
                position=row.position,
                question=row.question,
                automation_id=row.automation_id,
                automation_name=automation.name if automation else None,
                answer_with_ai=row.answer_with_ai,
            )
        )
    synced: list[datetime] = [r.synced_at for r in rows if r.synced_at is not None]
    errors = [r.sync_error for r in rows if r.sync_error]
    return IceBreakerList(
        items=items,
        synced_at=max(synced) if synced else None,
        sync_error=error or (errors[0] if errors else None),
        max_items=service.MAX_STARTERS,
    )


@router.get("/social-accounts/{account_id}/ice-breakers", operation_id="list_ice_breakers")
async def list_ice_breakers(
    ctx: AnyMember, session: Session, account_id: uuid.UUID
) -> IceBreakerList:
    """The account's conversation starters in order, and how the last sync to Instagram went."""
    acct = await connections.get_or_404(session, account_id)
    return await _out(session, await service.listing(session, acct.id))


@router.put("/social-accounts/{account_id}/ice-breakers", operation_id="replace_ice_breakers")
async def replace_ice_breakers(
    request: Request,
    ctx: CanManageChannels,
    session: Session,
    account_id: uuid.UUID,
    body: IceBreakersUpdate,
) -> IceBreakerList:
    """Save the whole list (up to 4, in order) and push it to Instagram. 422 validation_error
    names each field; a failed push is not an error: the list is kept and ``sync_error`` says
    why."""
    acct = await connections.get_or_404(session, account_id)
    deps = deps_from(request.app.state.http, request.app.state.settings)
    rows, error = await service.save(
        session,
        acct,
        [service.StarterIn(i.question, i.automation_id, i.answer_with_ai) for i in body.items],
        deps=deps,
    )
    out = await _out(session, rows, error=error)
    await session.commit()
    return out


@router.post("/social-accounts/{account_id}/ice-breakers/sync", operation_id="sync_ice_breakers")
async def sync_ice_breakers(
    request: Request, ctx: CanManageChannels, session: Session, account_id: uuid.UUID
) -> IceBreakerList:
    """Push the saved starters to Instagram again."""
    acct = await connections.get_or_404(session, account_id)
    deps = deps_from(request.app.state.http, request.app.state.settings)
    rows, error = await service.sync(session, acct, deps=deps)
    out = await _out(session, rows, error=error)
    await session.commit()
    return out
