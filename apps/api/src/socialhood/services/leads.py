"""Leads (GR-18): the stage of a contact as a lead, how it moves and what it records.

A lead is a contact. Its stage lives on the contact (``lead_stage``) and every move is a row in
``lead_stage_changes``: from, to, who or what moved it (a member, an automation, a rule) and why.

Stages: new, qualified, follow_up, won, lost. New, qualified and follow up are open; won and lost
are closed.

Rules:
- A member can move a lead to any stage, any time (a note is the reason). Moving to the stage it is
  already in changes nothing and records nothing.
- Automatic qualification only ever moves a lead out of ``new``. A lead a member or an earlier rule
  has moved on is never pulled back. A rule qualifies when the latest analysis has a lead score of
  at least 60 (the inbox's lead line), or a buying intent (pricing, purchase) with a score of at
  least 40; a captured email also qualifies (``on_capture``, for the flow engine's question step
  and GR-14's lead capture).
- Gone cold (the job in jobs/tasks/leads.py): a qualified or follow-up lead whose customer has not
  written for the workspace's ``lead_cold_days`` (7 unless changed), counted from their last
  message or from the last stage change, whichever is later. A qualified lead moves to follow up
  (rule ``gone_cold``); a follow-up lead stays. Both are flagged (``lead_cold_at``) and the
  members are told once. A lead is cold while the flag is later than its last customer message,
  so a new message ends it with no write; any stage change clears it.
- Every real move emits ``lead.stage_changed`` (GR-04).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.errors import ApiError
from socialhood.models.contacts import LeadStage, LeadStageChange, StageActor
from socialhood.models.identity import User, Workspace
from socialhood.models.inbox import Contact, Conversation
from socialhood.models.notifications import NotificationType
from socialhood.schemas.leads import LeadSettings, LeadStageCount, LeadSummary, LeadWeek
from socialhood.services.inbox_views import LEAD_SCORE

OPEN_STAGES = (LeadStage.NEW, LeadStage.QUALIFIED, LeadStage.FOLLOW_UP)
COLD_STAGES = (LeadStage.QUALIFIED, LeadStage.FOLLOW_UP)
STAGE_LABEL = {
    LeadStage.NEW: "New",
    LeadStage.QUALIFIED: "Qualified",
    LeadStage.FOLLOW_UP: "Follow up",
    LeadStage.WON: "Won",
    LeadStage.LOST: "Lost",
}
BUYING_INTENTS = frozenset({"pricing", "purchase"})
BUYING_SCORE = 40
DEFAULT_COLD_DAYS = 7
SUMMARY_WEEKS = 8

# Rule names recorded with an automatic move.
RULE_SCORE = "lead_score"
RULE_INTENT = "intent"
RULE_EMAIL = "email_captured"
RULE_COLD = "gone_cold"


@dataclass(frozen=True)
class Qualified:
    rule: str
    reason: str


def qualification(score: int | None, intent: str | None) -> Qualified | None:
    """Whether an analysis qualifies a lead: by score, or by a buying intent at a lower score."""
    if score is None:
        return None
    if score >= LEAD_SCORE:
        return Qualified(RULE_SCORE, f"Lead score reached {score}.")
    if intent in BUYING_INTENTS and score >= BUYING_SCORE:
        asked = "asked about pricing" if intent == "pricing" else "want to buy"
        return Qualified(RULE_INTENT, f"They {asked} (lead score {score}).")
    return None


def is_cold(contact: Contact, last_inbound_at: datetime | None) -> bool:
    """Flagged by the job and not written to since."""
    flagged = contact.lead_cold_at
    return flagged is not None and (last_inbound_at is None or flagged > last_inbound_at)


# ---------------------------------------------------------------- moving a stage


async def set_stage(
    session: AsyncSession,
    contact: Contact,
    stage: str,
    *,
    actor: StageActor,
    user_id: uuid.UUID | None = None,
    rule: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Move the contact to ``stage``; False (and nothing recorded) when it is there already.
    Runs in the contact's workspace scope; the caller commits."""
    from socialhood.services.webhooks import events

    if stage not in set(LeadStage):
        raise ValueError(f"unknown lead stage {stage}")
    before = contact.lead_stage
    if before == stage:
        return False
    now = now or datetime.now(UTC)
    cleaned = (reason or "").strip()[:300] or None
    contact.lead_stage = stage
    contact.lead_stage_at = now
    contact.lead_stage_reason = cleaned
    contact.lead_cold_at = None
    session.add(
        LeadStageChange(
            contact_id=contact.id,
            from_stage=before,
            to_stage=stage,
            actor_kind=actor,
            actor_user_id=user_id,
            rule=rule,
            reason=cleaned,
            created_at=now,
        )
    )
    await session.flush()
    await events.lead_stage_changed(
        session,
        contact,
        from_stage=before,
        to_stage=stage,
        actor_kind=actor,
        actor_user_id=user_id,
        rule=rule,
        reason=cleaned,
    )
    return True


async def member_set_stage(
    session: AsyncSession,
    contact_id: uuid.UUID,
    stage: str,
    *,
    user_id: uuid.UUID,
    note: str | None,
) -> bool:
    """A member's move. 404 for a contact that isn't in the workspace."""
    contact = await session.scalar(select(Contact).where(Contact.id == contact_id))
    if contact is None:
        raise ApiError("not_found", "That contact wasn't found.")
    return await set_stage(
        session, contact, stage, actor=StageActor.MEMBER, user_id=user_id, reason=note
    )


# ---------------------------------------------------------------- automatic qualification


async def _qualify(session: AsyncSession, contact: Contact | None, found: Qualified) -> bool:
    if contact is None or contact.lead_stage != LeadStage.NEW:
        return False
    return await set_stage(
        session,
        contact,
        LeadStage.QUALIFIED,
        actor=StageActor.RULE,
        rule=found.rule,
        reason=found.reason,
    )


async def on_analysis(
    session: AsyncSession, conv: Conversation, *, score: int | None, intent: str | None
) -> bool:
    """A conversation's newest analysis (lead score and intent): qualifies a new lead."""
    found = qualification(score, intent)
    if found is None:
        return False
    contact = await session.scalar(select(Contact).where(Contact.id == conv.contact_id))
    return await _qualify(session, contact, found)


async def on_capture(session: AsyncSession, contact: Contact, kind: str) -> bool:
    """Something was captured from the contact: ``kind`` is "email", "phone" or "field". A
    captured email qualifies a new lead. Called by the flow engine's question step, and by GR-14's
    lead capture when it saves an email."""
    if kind != "email":
        return False
    return await _qualify(session, contact, Qualified(RULE_EMAIL, "They gave their email address."))


# ---------------------------------------------------------------- gone cold


async def go_cold(
    session: AsyncSession, contact: Contact, conv: Conversation, *, days: int, now: datetime
) -> None:
    """Flag a stale lead, move a qualified one to follow up and tell the members, once per flag.
    Runs in the contact's workspace scope; the caller commits."""
    from socialhood.services.contacts import display_name
    from socialhood.services.notifications import notify_members

    if contact.lead_stage == LeadStage.QUALIFIED:
        await set_stage(
            session,
            contact,
            LeadStage.FOLLOW_UP,
            actor=StageActor.RULE,
            rule=RULE_COLD,
            reason=f"No reply for {days} days.",
            now=now,
        )
    contact.lead_cold_at = now
    await session.flush()
    name = display_name(contact)
    await notify_members(
        session,
        type=NotificationType.LEAD_COLD,
        severity="info",
        title=f"{name} has gone cold",
        body=f"{name} hasn't replied in {days} days. A follow-up could win them back.",
        link=f"/inbox/{conv.id}",
        dedupe_key=f"lead_cold:{contact.id}:{now.isoformat()}",
    )


# ---------------------------------------------------------------- summary and settings


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def summary(session: AsyncSession, *, now: datetime | None = None) -> LeadSummary:
    """Contacts per stage, the open leads that are cold, and the last 8 weeks of qualified and
    won (each contact once per week and stage)."""
    now = now or datetime.now(UTC)
    counts = dict(
        (
            await session.execute(
                select(Contact.lead_stage, func.count()).group_by(Contact.lead_stage)
            )
        ).all()
    )
    cold = await session.scalar(
        select(func.count())
        .select_from(Contact)
        .outerjoin(
            Conversation,
            and_(
                Conversation.contact_id == Contact.id,
                Conversation.social_account_id == Contact.social_account_id,
            ),
        )
        .where(
            Contact.lead_stage.in_(COLD_STAGES),
            Contact.lead_cold_at.is_not(None),
            or_(
                Conversation.last_inbound_at.is_(None),
                Contact.lead_cold_at > Conversation.last_inbound_at,
            ),
        )
    )
    first = _monday(now.date()) - timedelta(weeks=SUMMARY_WEEKS - 1)
    start = datetime(first.year, first.month, first.day, tzinfo=UTC)
    week = func.date_trunc("week", func.timezone("UTC", LeadStageChange.created_at))
    rows = (
        await session.execute(
            select(
                week,
                LeadStageChange.to_stage,
                func.count(func.distinct(LeadStageChange.contact_id)),
            )
            .where(
                LeadStageChange.created_at >= start,
                LeadStageChange.to_stage.in_((LeadStage.QUALIFIED, LeadStage.WON)),
            )
            .group_by(week, LeadStageChange.to_stage)
        )
    ).all()
    found: dict[tuple[date, str], int] = {(at.date(), stage): int(n) for at, stage, n in rows}
    weeks = [
        LeadWeek(
            week_start=day,
            qualified=found.get((day, LeadStage.QUALIFIED), 0),
            won=found.get((day, LeadStage.WON), 0),
        )
        for day in (first + timedelta(weeks=i) for i in range(SUMMARY_WEEKS))
    ]
    return LeadSummary(
        stages=[LeadStageCount(stage=s, count=int(counts.get(s, 0))) for s in LeadStage],
        cold=int(cold or 0),
        weeks=weeks,
        cold_after_days=await cold_days(session),
    )


async def cold_days(session: AsyncSession) -> int:
    days = await session.scalar(
        select(Workspace.lead_cold_days).where(Workspace.id == require_workspace())
    )
    return int(days or DEFAULT_COLD_DAYS)


async def get_settings(session: AsyncSession) -> LeadSettings:
    return LeadSettings(cold_after_days=await cold_days(session))


async def set_cold_days(session: AsyncSession, days: int) -> LeadSettings:
    workspace = await session.get(Workspace, require_workspace())
    if workspace is None:  # pragma: no cover - the request's workspace exists
        raise ApiError("not_found", "That workspace wasn't found.")
    workspace.lead_cold_days = days
    await session.flush()
    return LeadSettings(cold_after_days=days)


# ---------------------------------------------------------------- history


def actor_phrase(actor_kind: str, user_name: str | None) -> str:
    """Who or what moved a lead, in words."""
    if actor_kind == StageActor.MEMBER:
        return f"By {user_name}" if user_name else "By a team member"
    if actor_kind == StageActor.AUTOMATION:
        return "By an automation"
    if actor_kind == StageActor.RULE:
        return "Automatically"
    return "By Amplychat"


async def user_names(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.name, User.email).where(User.id.in_(ids)))
    return {i: (name or email) for i, name, email in rows.all()}
