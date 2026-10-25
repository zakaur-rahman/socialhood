"""Leads routes (GR-18): moving a contact's lead stage, the stage counts and weekly conversions,
and the days after which a lead goes cold. The lead list is ``GET /contacts?stage=`` (the same
filters, search and paging as the contacts page); the rules are in services/leads.py.

Who may do what: any member moves a lead's stage (agents work leads) and reads the summary; admins
change when a lead goes cold.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from socialhood.auth.deps import AnyMember, CanManageSettings, CanTag, Session
from socialhood.schemas.contacts import ContactRecord
from socialhood.schemas.leads import LeadSettings, LeadSettingsPatch, LeadStageUpdate, LeadSummary
from socialhood.services import audit, leads
from socialhood.services import contacts as contacts_service

router = APIRouter(prefix="/v1/w/{wid}", tags=["leads"])


@router.post("/contacts/{contact_id}/lead-stage", operation_id="set_lead_stage")
async def set_lead_stage(
    contact_id: uuid.UUID, body: LeadStageUpdate, ctx: CanTag, session: Session
) -> ContactRecord:
    """Move a lead to any stage; the note is why. The same stage again changes nothing."""
    await leads.member_set_stage(
        session, contact_id, body.stage, user_id=ctx.user.id, note=body.note
    )
    out = await contacts_service.get_record(session, contact_id)
    await session.commit()
    return out


@router.get("/leads/summary", operation_id="get_lead_summary")
async def get_lead_summary(ctx: AnyMember, session: Session) -> LeadSummary:
    """Contacts per stage, how many open leads have gone cold, and the last 8 weeks of leads
    qualified and won."""
    return await leads.summary(session)


@router.get("/leads/settings", operation_id="get_lead_settings")
async def get_lead_settings(ctx: AnyMember, session: Session) -> LeadSettings:
    return await leads.get_settings(session)


@router.patch("/leads/settings", operation_id="update_lead_settings")
async def update_lead_settings(
    body: LeadSettingsPatch, ctx: CanManageSettings, session: Session
) -> LeadSettings:
    """Days without a customer message before a qualified or follow-up lead goes cold (1 to 90)."""
    out = await leads.set_cold_days(session, body.cold_after_days)
    await audit.record(session, ctx, "settings.updated", "lead_settings")
    await session.commit()
    return out
