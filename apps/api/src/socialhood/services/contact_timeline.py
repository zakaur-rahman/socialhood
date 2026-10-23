"""One contact's timeline (GR-17): what happened with them, newest first, read-only.

Sources today: their conversation, their comments, automation runs on them, story mentions,
consent records, tags added and lead stage moves (GR-18). (Captured answers have no table of
their own until GR-14 and broadcasts arrive in GR-23; each adds a source here.)

Rules:
- Each source is read newest first with the same keyset, (time, id) before the cursor, and the
  merge keeps the newest ``limit``. Ids are unique across tables, so the cursor, the time and id of
  the last item, never repeats or skips one.
- Text is cut short: a comment shows its first 200 characters. Raw payloads, platform ids, message
  bodies and error text are never returned.
- Everything is workspace-scoped by the session; a contact of another workspace is a 404.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.automations import (
    Automation,
    AutomationRun,
    Comment,
    RunResult,
    StoryMention,
)
from socialhood.models.contacts import (
    ConsentStatus,
    ContactConsent,
    ContactTag,
    LeadStage,
    LeadStageChange,
    Tag,
)
from socialhood.models.inbox import Contact, Conversation, EntrySource
from socialhood.schemas.contacts import TimelineItem, TimelineKind, TimelineList
from socialhood.services import leads
from socialhood.services.contacts import _decode, _encode

DEFAULT_LIMIT = 30
EXCERPT = 200

ENTRY_DETAIL: dict[str, str] = {
    EntrySource.LINK: "From an entry link",
    EntrySource.AD: "From an ad",
    EntrySource.ICE_BREAKER: "From a conversation starter",
    EntrySource.OTHER: "From a referral",
}
RUN_DETAIL: dict[str, str] = {
    RunResult.SENT: "Replied",
    RunResult.QUEUED: "Reply waiting to go out",
    RunResult.PARTIAL: "Only part of the reply went out",
    RunResult.FAILED: "The reply failed",
    RunResult.SKIPPED_COOLDOWN: "Skipped: already replied recently",
    RunResult.SKIPPED_EXPIRED: "Skipped: the comment was too old",
    RunResult.ESCALATED: "Handed to your team",
    RunResult.AWAITING_REPLY: "Waiting for their answer",
    RunResult.SKIPPED_READ_ONLY: "Skipped: the account is read-only",
}
CHANNEL_LABEL = {"instagram": "Instagram", "whatsapp": "WhatsApp", "email": "email"}
CONSENT_SOURCE = {
    "platform_optin": "Opted in on the platform",
    "flow": "Answered in a conversation",
    "stop_reply": "Replied STOP",
    "member": "Recorded by your team",
    "import": "Imported",
}


def _before[*Ts](
    query: Select[*Ts], at: Any, row_id: Any, cursor: tuple[datetime, uuid.UUID] | None
) -> Select[*Ts]:
    """Only rows older than the cursor's (time, id)."""
    if cursor is None:
        return query
    when, last = cursor
    return query.where(or_(at < when, and_(at == when, row_id < last)))


def _item(
    row_id: uuid.UUID,
    kind: TimelineKind,
    at: datetime,
    title: str,
    detail: str | None = None,
    conversation_id: uuid.UUID | None = None,
) -> TimelineItem:
    return TimelineItem(
        id=row_id,
        kind=kind,
        occurred_at=at,
        title=title,
        detail=detail,
        conversation_id=conversation_id,
    )


def consent_title(channel: str, status: str) -> str:
    label = CHANNEL_LABEL.get(channel, channel)
    if status == ConsentStatus.GRANTED:
        return f"Agreed to marketing on {label}"
    return f"Withdrew marketing consent on {label}"


def _stage_detail(
    from_stage: str, actor_kind: str, user_name: str | None, reason: str | None
) -> str:
    """ "From New. By Priya. Asked for a quote.": where it moved from, who did it, and why."""
    parts = [
        f"From {leads.STAGE_LABEL[LeadStage(from_stage)]}",
        leads.actor_phrase(actor_kind, user_name),
    ]
    if reason:
        parts.append(reason.rstrip("."))
    return ". ".join(parts) + "."


async def timeline(
    session: AsyncSession, contact_id: uuid.UUID, *, cursor: str | None, limit: int = DEFAULT_LIMIT
) -> TimelineList:
    if await session.scalar(select(Contact.id).where(Contact.id == contact_id)) is None:
        raise ApiError("not_found", "That contact wasn't found.")
    after = _decode(cursor) if cursor else None
    take = limit + 1
    items: list[TimelineItem] = []

    conversations = await session.execute(
        _before(
            select(Conversation.id, Conversation.created_at, Conversation.entry_source).where(
                Conversation.contact_id == contact_id
            ),
            Conversation.created_at,
            Conversation.id,
            after,
        )
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .limit(take)
    )
    items += [
        _item(i, "conversation", at, "Conversation started", ENTRY_DETAIL.get(source or ""), i)
        for i, at, source in conversations.all()
    ]

    comments = await session.execute(
        _before(
            select(Comment.id, Comment.commented_at, Comment.text, Comment.is_live).where(
                Comment.contact_id == contact_id
            ),
            Comment.commented_at,
            Comment.id,
            after,
        )
        .order_by(Comment.commented_at.desc(), Comment.id.desc())
        .limit(take)
    )
    items += [
        _item(
            i, "comment", at, "Commented on a live video" if live else "Commented", text[:EXCERPT]
        )
        for i, at, text, live in comments.all()
    ]

    runs = await session.execute(
        _before(
            select(
                AutomationRun.id,
                AutomationRun.created_at,
                AutomationRun.result,
                AutomationRun.conversation_id,
                Automation.name,
            )
            .join(Automation, Automation.id == AutomationRun.automation_id)
            .where(AutomationRun.contact_id == contact_id),
            AutomationRun.created_at,
            AutomationRun.id,
            after,
        )
        .order_by(AutomationRun.created_at.desc(), AutomationRun.id.desc())
        .limit(take)
    )
    items += [
        _item(i, "automation_run", at, f"Automation: {name}", RUN_DETAIL.get(result), conv)
        for i, at, result, conv, name in runs.all()
    ]

    mentions = await session.execute(
        _before(
            select(StoryMention.id, StoryMention.mentioned_at).where(
                StoryMention.contact_id == contact_id
            ),
            StoryMention.mentioned_at,
            StoryMention.id,
            after,
        )
        .order_by(StoryMention.mentioned_at.desc(), StoryMention.id.desc())
        .limit(take)
    )
    items += [_item(i, "story_mention", at, "Mentioned you in a story") for i, at in mentions.all()]

    consents = await session.execute(
        _before(
            select(
                ContactConsent.id,
                ContactConsent.occurred_at,
                ContactConsent.channel,
                ContactConsent.status,
                ContactConsent.source,
            ).where(ContactConsent.contact_id == contact_id),
            ContactConsent.occurred_at,
            ContactConsent.id,
            after,
        )
        .order_by(ContactConsent.occurred_at.desc(), ContactConsent.id.desc())
        .limit(take)
    )
    items += [
        _item(i, "consent", at, consent_title(channel, status), CONSENT_SOURCE.get(source))
        for i, at, channel, status, source in consents.all()
    ]

    tags = await session.execute(
        _before(
            select(ContactTag.id, ContactTag.created_at, Tag.name)
            .join(Tag, Tag.id == ContactTag.tag_id)
            .where(ContactTag.contact_id == contact_id),
            ContactTag.created_at,
            ContactTag.id,
            after,
        )
        .order_by(ContactTag.created_at.desc(), ContactTag.id.desc())
        .limit(take)
    )
    items += [_item(i, "tag", at, f"Tagged {name}") for i, at, name in tags.all()]

    moves = (
        await session.execute(
            _before(
                select(
                    LeadStageChange.id,
                    LeadStageChange.created_at,
                    LeadStageChange.from_stage,
                    LeadStageChange.to_stage,
                    LeadStageChange.actor_kind,
                    LeadStageChange.actor_user_id,
                    LeadStageChange.reason,
                ).where(LeadStageChange.contact_id == contact_id),
                LeadStageChange.created_at,
                LeadStageChange.id,
                after,
            )
            .order_by(LeadStageChange.created_at.desc(), LeadStageChange.id.desc())
            .limit(take)
        )
    ).all()
    names = await leads.user_names(session, [m.actor_user_id for m in moves if m.actor_user_id])
    items += [
        _item(
            m.id,
            "lead_stage",
            m.created_at,
            f"Lead stage: {leads.STAGE_LABEL[LeadStage(m.to_stage)]}",
            _stage_detail(
                m.from_stage,
                m.actor_kind,
                names.get(m.actor_user_id) if m.actor_user_id else None,
                m.reason,
            ),
        )
        for m in moves
    ]

    items.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    page = items[:limit]
    next_cursor = _encode(page[-1].occurred_at, page[-1].id) if len(items) > limit else None
    return TimelineList(items=page, next_cursor=next_cursor)
