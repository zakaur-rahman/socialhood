"""A number's quality rating and daily limit, and the pause when quality drops (GR-23).

``whatsapp_number_health`` holds what WhatsApp last said about a number: from the
``phone_number_quality_update`` webhook (a flag, an upgrade or a downgrade, with the tier after
it) and from reading the number (``adapter.get_number_health``, before a broadcast starts and
when its health is more than ``STALE_AFTER`` old). *Unverified against a live number; see
platforms/whatsapp/health.py.*

Pausing: a sending broadcast of the number pauses with a plain reason when

- the rating falls (green to yellow, or to red) while it sends, or is red when a batch is due;
- WhatsApp lowers the number's tier (DOWNGRADE).

The owner resumes it; resuming while the rating is red is refused. The limit only paces a broadcast
(services/broadcasts/throttle.py); a number whose tier is not known gets the conservative default.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.broadcasts import QualityRating, WhatsAppNumberHealth
from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.whatsapp.health import NumberHealth, QualityEvent
from socialhood.services.broadcasts import lifecycle, throttle

log = get_logger(__name__)

STALE_AFTER = timedelta(minutes=30)
# Higher is better. An unknown rating is neutral: not knowing is not a drop.
RANK = {
    QualityRating.GREEN: 3,
    QualityRating.UNKNOWN: 3,
    QualityRating.YELLOW: 1,
    QualityRating.RED: 0,
}
RATING_WORDS = {
    QualityRating.GREEN: "High",
    QualityRating.YELLOW: "Medium",
    QualityRating.RED: "Low",
    QualityRating.UNKNOWN: "unknown",
}
RED_REASON = (
    "WhatsApp rated this number's quality Low. Sending is paused to protect the number. "
    "Resume it once the rating recovers."
)


def drop_reason(rating: str) -> str:
    word = RATING_WORDS.get(QualityRating(rating), rating)
    return (
        f"WhatsApp lowered this number's quality rating to {word}. "
        "Sending is paused to protect the number. Resume it when you are ready."
    )


def tier_reason(daily_limit: int | None) -> str:
    people = f"{daily_limit:,} people" if daily_limit else "fewer people"
    return (
        f"WhatsApp lowered how many people this number can message a day to {people}. "
        "Sending is paused so the broadcast does not run past it. Resume it when you are ready."
    )


@runtime_checkable
class HealthSource(Protocol):
    async def get_number_health(self, acct: SocialAccount) -> NumberHealth: ...


@dataclass(frozen=True)
class Change:
    """What recording a health reading changed."""

    before: str
    after: str
    limit_before: int | None
    limit_after: int | None

    @property
    def dropped(self) -> bool:
        return RANK[QualityRating(self.after)] < RANK[QualityRating(self.before)]

    @property
    def tier_lowered(self) -> bool:
        if self.limit_before is None or self.limit_after is None:
            return False
        return self.limit_after < self.limit_before


def daily_limit_of(row: WhatsAppNumberHealth | None) -> tuple[int | None, bool]:
    """(people a day, whether WhatsApp told us). None people: no limit. A number whose tier is
    not known gets the conservative default."""
    if row is None or row.messaging_tier is None:
        return throttle.DEFAULT_DAILY_LIMIT, False
    if row.messaging_tier == "TIER_UNLIMITED":
        return None, True
    return row.daily_limit or throttle.DEFAULT_DAILY_LIMIT, row.daily_limit is not None


async def get(session: AsyncSession, account_id: uuid.UUID) -> WhatsAppNumberHealth | None:
    return await session.scalar(
        select(WhatsAppNumberHealth).where(WhatsAppNumberHealth.social_account_id == account_id)
    )


async def record(
    session: AsyncSession,
    acct: SocialAccount,
    *,
    quality: str | None,
    tier: str | None,
    source: str,
    now: datetime,
) -> Change:
    """Store a reading. ``quality`` or ``tier`` left None keep what was known."""
    row = await get(session, acct.id)
    before = row.quality_rating if row else QualityRating.UNKNOWN
    limit_before = row.daily_limit if row else None
    if row is None:
        row = WhatsAppNumberHealth(
            social_account_id=acct.id,
            quality_rating=QualityRating.UNKNOWN,
            source=source,
            checked_at=now,
        )
        try:
            # Two requests reading a new number at once both find no row (the broadcast page
            # asks for a preview twice): the one that loses the insert takes the winner's row.
            async with session.begin_nested():
                session.add(row)
        except IntegrityError:
            row = await get(session, acct.id)
            if row is None:
                raise
    if quality is not None:
        row.quality_rating = quality
    if tier is not None:
        row.messaging_tier = tier
        row.daily_limit = throttle.limit_for_tier(tier)
    row.source = source
    row.checked_at = now
    await session.flush()
    return Change(str(before), str(row.quality_rating), limit_before, row.daily_limit)


async def pause_if_worse(
    session: AsyncSession, acct: SocialAccount, change: Change
) -> list[uuid.UUID]:
    """Pause the number's sending broadcasts when the reading is a drop."""
    if change.tier_lowered:
        return await lifecycle.pause_running_for_account(
            session, acct.id, code="quality", reason=tier_reason(change.limit_after)
        )
    if change.dropped and change.after in (QualityRating.YELLOW, QualityRating.RED):
        reason = RED_REASON if change.after == QualityRating.RED else drop_reason(change.after)
        return await lifecycle.pause_running_for_account(
            session, acct.id, code="quality", reason=reason
        )
    return []


async def apply_event(
    session: AsyncSession, acct: SocialAccount, event: QualityEvent, *, now: datetime | None = None
) -> list[uuid.UUID]:
    """A ``phone_number_quality_update`` for the number: store it, pause its broadcasts on a drop.
    Returns the ids of the broadcasts it paused."""
    now = now or datetime.now(UTC)
    change = await record(
        session,
        acct,
        quality=event.quality_rating,
        tier=event.messaging_tier,
        source="webhook",
        now=now,
    )
    if event.event == "DOWNGRADE" and not change.tier_lowered:
        # WhatsApp says the tier went down but the tier given is not lower than what we held
        # (or we held none): treat it as a drop all the same.
        return await lifecycle.pause_running_for_account(
            session, acct.id, code="quality", reason=tier_reason(change.limit_after)
        )
    return await pause_if_worse(session, acct, change)


async def current(
    session: AsyncSession,
    deps: PlatformDeps,
    acct: SocialAccount,
    *,
    now: datetime | None = None,
    refresh: bool = True,
) -> WhatsAppNumberHealth | None:
    """What is known about the number now: the stored reading, read again from WhatsApp when it
    is older than ``STALE_AFTER`` (a failed read keeps what we have)."""
    now = now or datetime.now(UTC)
    row = await get(session, acct.id)
    if not refresh or (row is not None and now - row.checked_at < STALE_AFTER):
        return row
    try:
        adapter = adapter_for(acct, deps)
        if not isinstance(adapter, HealthSource):
            return row
        reading = await adapter.get_number_health(acct)
    except PlatformError as error:
        log.warning("number_health_failed", account_id=str(acct.id), error_code=error.code)
        return row
    # An unknown rating (a new number has none yet) is no news: it never overwrites a known one.
    known = reading.quality_rating != QualityRating.UNKNOWN
    await record(
        session,
        acct,
        quality=reading.quality_rating if known else None,
        tier=reading.messaging_tier,
        source="api",
        now=now,
    )
    return await get(session, acct.id)
