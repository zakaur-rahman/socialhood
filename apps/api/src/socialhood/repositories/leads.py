"""Lead lookups for the gone-cold job (GR-18). Cross-workspace: the caller opens
tenant_bypass_scope (jobs/ only)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.contacts import LeadStage
from socialhood.models.identity import Workspace
from socialhood.models.inbox import Contact, Conversation

COLD_STAGES = (LeadStage.QUALIFIED, LeadStage.FOLLOW_UP)
_FRESH = {"populate_existing": True}


async def lock_cold(
    session: AsyncSession, *, now: datetime, limit: int
) -> list[tuple[Contact, Conversation, int]]:
    """Qualified and follow-up leads whose customer last wrote, or whose stage last changed,
    whichever is later, more than their workspace's ``lead_cold_days`` ago, and that are not
    flagged since that message. Locked so two runs never flag one twice."""
    last_touch = func.greatest(
        Conversation.last_inbound_at,
        func.coalesce(Contact.lead_stage_at, Conversation.last_inbound_at),
    )
    days = Workspace.lead_cold_days
    statement = (
        select(Contact, Conversation, days)
        .join(
            Conversation,
            and_(
                Conversation.contact_id == Contact.id,
                Conversation.social_account_id == Contact.social_account_id,
            ),
        )
        .join(Workspace, Workspace.id == Contact.workspace_id)
        .where(
            Contact.lead_stage.in_(COLD_STAGES),
            Conversation.last_inbound_at.is_not(None),
            last_touch < now - literal_column("interval '1 day'") * days,
            or_(
                Contact.lead_cold_at.is_(None),
                Contact.lead_cold_at < Conversation.last_inbound_at,
            ),
        )
        .order_by(Conversation.last_inbound_at)
        .limit(limit)
        .with_for_update(skip_locked=True, of=(Contact, Conversation))
    )
    rows = (await session.execute(statement, execution_options=_FRESH)).all()
    return [(contact, conv, int(d)) for contact, conv, d in rows]
