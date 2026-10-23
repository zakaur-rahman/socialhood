"""How a customer DM was entered (GR-08, GR-09): which entry link or ad it came from, for the
``entry_link`` and ``ad_click`` triggers. Reads the conversation's ``last_referral`` (GR-01 stores
every referral there, from the message itself or from a ``messaging_referral`` event).

A DM is an entry only when it is the first customer message after the referral and arrives within
REFERRAL_WINDOW of it, so a link or an ad starts its automation once, not on every later message.
The runtime's cooldown still applies on top. A referral Meta delivers after the first message
(GR-01's upgrade window) is not seen by the run, which looks at the conversation about a second
after the message arrives. Pure parts are ``parse`` and ``in_scope``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import Automation, PostScope
from socialhood.models.inbox import Conversation, Message
from socialhood.repositories import entry_links

REFERRAL_WINDOW = timedelta(hours=1)  # the same window as GR-01's (services/ingest)
LINK_TRIGGER = "entry_link"
AD_TRIGGER = "ad_click"


@dataclass(frozen=True)
class Entry:
    source: str  # "link" or "ad"
    ref: str | None = None  # the entry link's code
    ad_id: str | None = None
    link_automation_id: uuid.UUID | None = None  # the entry link's automation, for a known link

    @property
    def trigger(self) -> str:
        return LINK_TRIGGER if self.source == "link" else AD_TRIGGER


def parse(record: dict[str, Any] | None) -> tuple[Entry, datetime] | None:
    """The entry a stored referral describes and when it was made; None for anything else."""
    if not record or record.get("source") not in ("link", "ad"):
        return None
    try:
        at = datetime.fromisoformat(str(record.get("at")))
    except ValueError:
        return None
    return Entry(record["source"], record.get("ref"), record.get("ad_id")), at


async def of_message(session: AsyncSession, msg: Message, conv: Conversation) -> Entry | None:
    """The entry ``msg`` was sent from, or None (an ordinary DM)."""
    parsed = parse(conv.last_referral)
    if parsed is None:
        return None
    entry, at = parsed
    if at.tzinfo is None or not timedelta(0) <= msg.occurred_at - at <= REFERRAL_WINDOW:
        return None
    if await entry_links.has_inbound_since(session, conv.id, since=at, before=msg):
        return None  # they had already written after the referral
    if entry.source == "link":
        if not entry.ref:
            return None
        link = await entry_links.get_by_code(session, msg.social_account_id, entry.ref)
        if link is None:
            return None  # a ref that is not one of our links
        return Entry("link", entry.ref, None, link.automation_id)
    return entry


def in_scope(automation: Automation, entry: Entry) -> bool:
    """Whether an entry link or ad click automation answers this entry. An entry link automation
    answers the links that point at it; an ad click one answers any ad, or its chosen ads. Other
    triggers are not limited by the entry."""
    if automation.trigger == LINK_TRIGGER:
        return entry.source == "link" and automation.id == entry.link_automation_id
    if automation.trigger == AD_TRIGGER:
        if entry.source != "ad":
            return False
        if automation.post_scope != PostScope.SELECTED:
            return True
        return entry.ad_id is not None and entry.ad_id in (automation.ad_ids or [])
    return True
