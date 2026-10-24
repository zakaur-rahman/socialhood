"""Broadcasts: create, preview, start, pause, resume, cancel, and the reads for the pages (GR-23).
Nothing here commits; the routes do.

Rules:
- A broadcast sends one approved WhatsApp template (marketing or utility; authentication templates
  are one-time codes and are refused) from one connected number to a saved segment's contacts on
  that number who have agreed to WhatsApp marketing (services/broadcasts/audience.py).
- Plans (PD-4, decided 2026-10-24): Pro and Max, not Free, with a monthly recipient quota
  (``broadcast_recipients_monthly``: Pro 2,500, Max 25,000). Writing (preview, create, change,
  start, resume) is refused on a plan without it with 402 ``entitlement_required``; reading what
  already exists never is. The quota counts recipients handed to the send queue in the current
  billing period (failures after hand-over included, skipped contacts never). Starting a broadcast
  that would not fit is refused with 402 ``quota_exceeded`` and the numbers; one that runs out of
  quota while it sends pauses with the reason (services/broadcasts/dispatch.py).
- Start now, or schedule from a minute to 90 days ahead. The audience is fixed when it starts:
  people who agree later are not added, and consent is checked again for each person at their turn.
- Only a draft or scheduled broadcast can be changed. A broadcast that has started can be paused,
  resumed and cancelled (everyone still waiting is skipped as ``cancelled``); a draft, cancelled
  or failed one can be deleted.
- The cost estimate is Meta's rate card times the people to send to (services/broadcasts/rates.py):
  information, never a charge (PD-3: the business pays Meta directly).
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import entitlement_error, quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.broadcasts import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    QualityRating,
    SkipReason,
)
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.contacts import ContactSegment
from socialhood.models.inbox import Contact, Message
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.repositories import broadcasts as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories import usage
from socialhood.schemas import broadcasts as schemas
from socialhood.schemas.broadcasts import (
    BroadcastAvailability,
    BroadcastCounts,
    BroadcastCreate,
    BroadcastDraft,
    BroadcastList,
    BroadcastPreview,
    BroadcastTemplate,
    BroadcastUpdate,
    CostEstimate,
    NumberInfo,
    QuotaInfo,
    RateCardOut,
    Recipient,
    RecipientList,
    SamplePreview,
    VariableOut,
)
from socialhood.schemas.whatsapp import WhatsAppTemplate
from socialhood.services import contacts as contact_service
from socialhood.services import whatsapp_templates
from socialhood.services.broadcasts import audience, health, lifecycle, rates, throttle
from socialhood.services.broadcasts import variables as variable_rules
from socialhood.services.sending import readable_error

log = get_logger(__name__)

KEY = "broadcast_recipients_monthly"
MAX_AHEAD = timedelta(days=90)
MIN_AHEAD = timedelta(minutes=1)
LIST_MAX = 100
NOT_AVAILABLE = "Broadcasts aren't available yet."

SKIP_WORDS = {
    SkipReason.OPTED_OUT: "Asked not to get marketing messages.",
    SkipReason.NO_CONSENT: "Hasn't agreed to WhatsApp marketing.",
    SkipReason.MISSING_VALUE: "A template variable has no value for this person.",
    SkipReason.CANCELLED: "The broadcast was cancelled before their turn.",
}
AUTHENTICATION = "Authentication templates are one-time codes and can't be sent as a broadcast."


# ---------------------------------------------------------------- plan and quota


async def plan_limit(session: AsyncSession) -> int:
    """The plan's recipients a month; 402 entitlement_required when the plan has none (Free)."""
    limit = entitlement(await current_plan(session), KEY)
    if not limit:
        raise entitlement_error(KEY)
    return int(limit)


async def period(session: AsyncSession, today: date) -> tuple[datetime, datetime]:
    """The current billing period as datetimes (UTC midnights)."""
    start, end = usage.period_for(await usage.anchor_day(session), today)
    return (
        datetime.combine(start, time.min, tzinfo=UTC),
        datetime.combine(end, time.min, tzinfo=UTC),
    )


async def quota_used(session: AsyncSession, now: datetime) -> tuple[int, datetime, datetime]:
    start, end = await period(session, now.date())
    return await repo.dispatched_since(session, start, end), start, end


async def availability(
    session: AsyncSession, *, enabled: bool, now: datetime
) -> BroadcastAvailability:
    if not enabled:
        return BroadcastAvailability(enabled=False)
    limit = int(entitlement(await current_plan(session), KEY) or 0)
    used, _, end = await quota_used(session, now)
    card = rates.RATE_CARD
    return BroadcastAvailability(
        enabled=True,
        plan_allowed=limit > 0,
        monthly_limit=limit,
        used_this_period=used,
        period_end=end,
        rate_card=RateCardOut(
            currency=card.currency,
            country=card.country,
            as_of=card.as_of,
            source=card.source,
            verified=card.verified,
            rates=card.rates,
        ),
    )


# ---------------------------------------------------------------- inputs


class Resolved:
    """A broadcast's inputs, checked: the number, the segment, the template and the variables."""

    def __init__(
        self,
        account: SocialAccount,
        segment: ContactSegment,
        template: WhatsAppTemplate,
        variables: list[dict[str, Any]],
    ) -> None:
        self.account = account
        self.segment = segment
        self.template = template
        self.variables = variables

    @property
    def filt(self) -> contact_service.ContactFilter:
        return audience.segment_filter(self.segment, self.account.id)


def _invalid(field: str, message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError(field, message)])


def stored_variables(items: list[Any]) -> list[dict[str, Any]]:
    """The mapping as saved: only what its source uses."""
    out: list[dict[str, Any]] = []
    for item in items:
        if item.source == "fixed":
            out.append({"source": "fixed", "field": None, "value": item.value, "fallback": None})
        else:
            fallback = (item.fallback or "").strip() or None
            out.append(
                {"source": "field", "field": item.field, "value": None, "fallback": fallback}
            )
    return out


async def resolve(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    account_id: uuid.UUID,
    segment_id: uuid.UUID,
    template_name: str,
    template_language: str,
    variables: list[dict[str, Any]],
) -> Resolved:
    acct = await accounts.get(session, account_id)
    if acct is None:
        raise ApiError("not_found", "That WhatsApp number wasn't found.")
    if acct.platform != "whatsapp":
        raise _invalid("social_account_id", "Choose a WhatsApp number.")
    segment = await session.scalar(select(ContactSegment).where(ContactSegment.id == segment_id))
    if segment is None:
        raise ApiError("not_found", "That segment wasn't found.")
    await plan_limit(session)  # after the lookups: another workspace's id is a 404 first
    approved = await whatsapp_templates.approved_templates(session, redis, deps, acct)
    template = next(
        (t for t in approved if t.name == template_name and t.language == template_language), None
    )
    if template is None:
        raise _invalid(
            "template_name", "That template isn't approved on this number. Choose another."
        )
    if template.category == "authentication":
        raise _invalid("template_name", AUTHENTICATION)
    keys = set((await contact_service._definitions(session)).keys())
    found = variable_rules.problems(variables, param_count=template.param_count, field_keys=keys)
    if found:
        raise ApiError(
            "validation_error",
            errors=[FieldError("variables", message) for _, message in found],
        )
    return Resolved(acct, segment, template, variables)


# ---------------------------------------------------------------- preview


def _number_info(row: Any, eligible: int) -> NumberInfo:
    limit, known = health.daily_limit_of(row)
    cap = throttle.usable(limit)
    days = 1 if cap is None else max(1, math.ceil(eligible / cap))
    return NumberInfo(
        quality_rating=row.quality_rating if row else QualityRating.UNKNOWN,
        daily_limit=limit,
        limit_known=known,
        days_to_send=days,
    )


def cost_of(category: str, recipients: int) -> CostEstimate:
    card = rates.RATE_CARD
    return CostEstimate(
        currency=card.currency,
        category=category,
        per_message=rates.rate_for(category),
        total=rates.estimate(category, recipients),
        as_of=card.as_of,
        source=card.source,
        verified=card.verified,
    )


async def preview(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    body: BroadcastDraft,
    *,
    now: datetime,
) -> BroadcastPreview:
    r = await resolve(
        session,
        redis,
        deps,
        account_id=body.social_account_id,
        segment_id=body.segment_id,
        template_name=body.template_name,
        template_language=body.template_language,
        variables=stored_variables(body.variables),
    )
    limit = await plan_limit(session)
    consent = await audience.consent_counts(session, r.filt)
    planned = await audience.plan(session, r.filt, r.variables)
    counts = audience.counts_from(consent, planned)
    used, _, end = await quota_used(session, now)
    remaining = max(0, limit - used)
    row = await health.current(session, deps, r.account, now=now)
    sample = await audience.sample(session, r.filt, planned)
    params = next(
        (p.params for p in planned if p.contact_id == (sample.id if sample else None)), []
    )
    if sample is not None and not params and r.variables:
        params = variable_rules.resolve(r.variables, _values(sample)) or [
            f"[{i}]" for i in range(1, len(r.variables) + 1)
        ]
    problems: list[str] = []
    if counts.eligible == 0:
        problems.append(
            "No one in this segment can be sent to yet. People need to have agreed to WhatsApp "
            "marketing first."
        )
    if counts.eligible > remaining:
        problems.append(
            f"Your plan includes {limit:,} broadcast recipients a month and {remaining:,} are "
            f"left. This broadcast has {counts.eligible:,}."
        )
    if row is not None and row.quality_rating == QualityRating.RED:
        problems.append(health.RED_REASON)
    return BroadcastPreview(
        audience=counts,
        cost=cost_of(r.template.category, counts.eligible),
        quota=QuotaInfo(
            limit=limit,
            used=used,
            remaining=remaining,
            period_end=end,
            fits=counts.eligible <= remaining,
        ),
        number=_number_info(row, counts.eligible),
        sample=SamplePreview(
            contact_name=contact_service.display_name(sample) if sample else None,
            text=variable_rules.render_body(r.template.body, params),
        ),
        problems=problems,
    )


def _values(contact: Contact) -> dict[str, str | None]:
    from socialhood.services.saved_replies import contact_values

    return contact_values(contact)


# ---------------------------------------------------------------- create and change


async def get(session: AsyncSession, broadcast_id: uuid.UUID, *, lock: bool = False) -> Broadcast:
    query = select(Broadcast).where(Broadcast.id == broadcast_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await session.scalar(query)
    if row is None:
        raise ApiError("not_found", "That broadcast wasn't found.")
    return row


def _apply(row: Broadcast, r: Resolved) -> None:
    row.social_account_id = r.account.id
    row.segment_id = r.segment.id
    row.segment_name = r.segment.name
    row.template_name = r.template.name
    row.template_language = r.template.language
    row.template_category = r.template.category
    row.template_body = r.template.body
    row.variables = r.variables


async def create(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    body: BroadcastCreate,
    *,
    user_id: uuid.UUID | None,
    now: datetime,
) -> schemas.Broadcast:
    r = await resolve(
        session,
        redis,
        deps,
        account_id=body.social_account_id,
        segment_id=body.segment_id,
        template_name=body.template_name,
        template_language=body.template_language,
        variables=stored_variables(body.variables),
    )
    row = Broadcast(
        name=body.name.strip(),
        status=BroadcastStatus.DRAFT,
        created_by_user_id=user_id,
        audience_size=0,
        cost_currency=rates.RATE_CARD.currency,
    )
    _apply(row, r)
    session.add(row)
    await session.flush()
    return await to_out(session, row)


async def update(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    broadcast_id: uuid.UUID,
    body: BroadcastUpdate,
) -> schemas.Broadcast:
    row = await get(session, broadcast_id, lock=True)
    await plan_limit(session)
    if row.status not in (BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED):
        raise ApiError("conflict", "Only a draft or a scheduled broadcast can be changed.")
    given = body.model_fields_set
    r = await resolve(
        session,
        redis,
        deps,
        account_id=body.social_account_id or row.social_account_id,
        segment_id=body.segment_id or _segment_of(row),
        template_name=body.template_name or row.template_name,
        template_language=body.template_language or row.template_language,
        variables=(
            stored_variables(body.variables)
            if "variables" in given and body.variables is not None
            else row.variables
        ),
    )
    if body.name is not None:
        row.name = body.name.strip()
    _apply(row, r)
    await session.flush()
    return await to_out(session, row)


def _segment_of(row: Broadcast) -> uuid.UUID:
    if row.segment_id is None:
        raise _invalid("segment_id", "The segment this broadcast used was deleted. Choose another.")
    return row.segment_id


async def delete(session: AsyncSession, broadcast_id: uuid.UUID) -> None:
    row = await get(session, broadcast_id, lock=True)
    if row.status not in (
        BroadcastStatus.DRAFT,
        BroadcastStatus.CANCELLED,
        BroadcastStatus.FAILED,
    ):
        raise ApiError(
            "conflict", "Cancel the broadcast first. One that has been sent stays as a record."
        )
    await repo.delete_broadcast(session, row.id)


# ---------------------------------------------------------------- start, pause, resume, cancel


async def start(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    broadcast_id: uuid.UUID,
    *,
    scheduled_at: datetime | None,
    now: datetime,
) -> tuple[schemas.Broadcast, bool]:
    """Send now or schedule. Returns the broadcast and whether it is sending now (the route then
    queues its first batch after the commit)."""
    row = await get(session, broadcast_id, lock=True)
    await plan_limit(session)
    if row.status == BroadcastStatus.SENDING:
        return await to_out(session, row), False  # a double click: already on its way
    if row.status not in (BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED):
        raise ApiError("conflict", "This broadcast can't be started again.")
    r = await resolve(
        session,
        redis,
        deps,
        account_id=row.social_account_id,
        segment_id=_segment_of(row),
        template_name=row.template_name,
        template_language=row.template_language,
        variables=row.variables,
    )
    if scheduled_at is not None:
        if scheduled_at.tzinfo is None:
            raise _invalid("scheduled_at", "Include the time zone in the date.")
        if scheduled_at < now + MIN_AHEAD:
            raise _invalid("scheduled_at", "Choose a time at least a minute from now.")
        if scheduled_at > now + MAX_AHEAD:
            raise _invalid("scheduled_at", "Choose a time within the next 90 days.")
        await _check_fits(session, r, now)
        row.status = BroadcastStatus.SCHEDULED
        row.scheduled_at = scheduled_at
        await session.flush()
        return await to_out(session, row), False
    row.scheduled_at = None
    row.variables = r.variables
    await launch(session, row, account=r.account, segment=r.segment, now=now, strict=True)
    return await to_out(session, row), True


async def _check_fits(session: AsyncSession, r: Resolved, now: datetime) -> int:
    """402 when the people to send to would not fit in the month's quota; returns how many."""
    limit = await plan_limit(session)
    consent = await audience.consent_counts(session, r.filt)
    eligible = consent.get("granted", 0)
    used, _, _ = await quota_used(session, now)
    if used + eligible > limit:
        raise quota_error(
            KEY,
            limit,
            f"Your plan includes {limit:,} broadcast recipients a month and "
            f"{max(0, limit - used):,} are left. This broadcast has {eligible:,}.",
        )
    return eligible


class CannotStart(Exception):
    """A scheduled broadcast whose number or segment is gone when its time comes."""


async def launch_inputs(
    session: AsyncSession, row: Broadcast
) -> tuple[SocialAccount, ContactSegment]:
    """The number and segment a stored broadcast sends with (the scheduler's, which does not call
    Meta: a template withdrawn since then fails each message with WhatsApp's reason)."""
    acct = await accounts.get(session, row.social_account_id)
    if acct is None:
        raise CannotStart("This WhatsApp number was removed.")
    if row.segment_id is None:
        raise CannotStart("The segment this broadcast used was deleted.")
    segment = await session.scalar(
        select(ContactSegment).where(ContactSegment.id == row.segment_id)
    )
    if segment is None:
        raise CannotStart("The segment this broadcast used was deleted.")
    return acct, segment


async def launch(
    session: AsyncSession,
    row: Broadcast,
    *,
    account: SocialAccount,
    segment: ContactSegment,
    now: datetime,
    strict: bool,
) -> None:
    """Fix the audience and start sending. ``strict`` (a member pressed Send) raises what stops
    it; the scheduler passes ``strict=False`` and the broadcast fails with the reason instead."""
    try:
        if account.status in (AccountStatus.NEEDS_RECONNECT, AccountStatus.DISCONNECTED):
            raise ApiError(
                "account_needs_reconnect",
                "This WhatsApp number needs reconnecting before it sends.",
            )
        filt = audience.segment_filter(segment, account.id)
        planned = await audience.plan(session, filt, row.variables)
        eligible = sum(1 for p in planned if p.state == "pending")
        if eligible == 0:
            raise _invalid(
                "segment_id",
                "No one in that segment can be sent to. People need to have agreed to WhatsApp "
                "marketing first.",
            )
        if strict:
            limit = await plan_limit(session)
            used, _, _ = await quota_used(session, now)
            if used + eligible > limit:
                raise quota_error(
                    KEY,
                    limit,
                    f"Your plan includes {limit:,} broadcast recipients a month and "
                    f"{max(0, limit - used):,} are left. This broadcast has {eligible:,}.",
                )
    except ApiError as error:
        if strict:
            raise
        await lifecycle.fail(
            session, row, error.detail or "The broadcast couldn't start.", now, code="start"
        )
        return
    for start_at in range(0, len(planned), 1000):
        session.add_all(
            [
                BroadcastRecipient(
                    broadcast_id=row.id,
                    contact_id=p.contact_id,
                    position=p.position,
                    state=p.state,
                    skip_reason=p.skip_reason,
                    params=p.params,
                )
                for p in planned[start_at : start_at + 1000]
            ]
        )
        await session.flush()
    row.audience_size = eligible
    row.rate_per_message = rates.rate_for(row.template_category)
    row.estimated_cost = rates.estimate(row.template_category, eligible)
    row.cost_currency = rates.RATE_CARD.currency
    row.status = BroadcastStatus.SENDING
    row.started_at = now
    row.paused_code = None
    row.paused_reason = None
    await session.flush()
    log.info("broadcast_started", broadcast_id=str(row.id), eligible=eligible, total=len(planned))


async def pause(session: AsyncSession, broadcast_id: uuid.UUID) -> schemas.Broadcast:
    row = await get(session, broadcast_id, lock=True)
    if row.status == BroadcastStatus.PAUSED:
        return await to_out(session, row)
    if row.status != BroadcastStatus.SENDING:
        raise ApiError("conflict", "Only a broadcast that is sending can be paused.")
    await lifecycle.pause(session, row, code="member", reason="Paused by your team.", notify=False)
    return await to_out(session, row)


async def resume(
    session: AsyncSession, deps: PlatformDeps, broadcast_id: uuid.UUID, *, now: datetime
) -> tuple[schemas.Broadcast, bool]:
    row = await get(session, broadcast_id, lock=True)
    limit = await plan_limit(session)
    if row.status == BroadcastStatus.SENDING:
        return await to_out(session, row), False
    if row.status != BroadcastStatus.PAUSED:
        raise ApiError("conflict", "Only a paused broadcast can be resumed.")
    acct = await accounts.get(session, row.social_account_id)
    if acct is None or acct.status in (AccountStatus.NEEDS_RECONNECT, AccountStatus.DISCONNECTED):
        raise ApiError("account_needs_reconnect", "Reconnect this WhatsApp number to resume.")
    number = await health.current(session, deps, acct, now=now)
    if number is not None and number.quality_rating == QualityRating.RED:
        raise ApiError("conflict", health.RED_REASON)
    used, _, _ = await quota_used(session, now)
    if used >= limit:
        raise quota_error(KEY, limit, f"You've used this month's {limit:,} broadcast recipients.")
    lifecycle.resume(row)
    await session.flush()
    return await to_out(session, row), True


async def cancel(session: AsyncSession, broadcast_id: uuid.UUID) -> schemas.Broadcast:
    row = await get(session, broadcast_id, lock=True)
    if row.status == BroadcastStatus.CANCELLED:
        return await to_out(session, row)
    if row.status not in (*lifecycle.OPEN, BroadcastStatus.SENDING):
        raise ApiError("conflict", "This broadcast has finished.")
    await repo.skip_pending(session, row.id, SkipReason.CANCELLED)
    row.status = BroadcastStatus.CANCELLED
    row.completed_at = datetime.now(UTC)
    await session.flush()
    return await to_out(session, row)


# ---------------------------------------------------------------- reads


def _counts_out(raw: dict[str, int]) -> BroadcastCounts:
    return BroadcastCounts(
        total=raw["total"],
        queued=raw["queued"],
        sent=raw["sent"],
        delivered=raw["delivered"],
        read=raw["read"],
        failed=raw["failed"],
        skipped=raw["skipped"],
        replied=raw["replied"],
        stopped=raw["stopped"],
    )


def _label(acct: SocialAccount | None) -> str | None:
    if acct is None:
        return None
    return acct.display_name or (f"@{acct.username}" if acct.username else None)


def _out(row: Broadcast, raw: dict[str, int], acct: SocialAccount | None) -> schemas.Broadcast:
    cost = None
    if row.estimated_cost is not None and row.rate_per_message is not None:
        card = rates.RATE_CARD
        cost = CostEstimate(
            currency=row.cost_currency,
            category=row.template_category,
            per_message=Decimal(row.rate_per_message),
            total=Decimal(row.estimated_cost),
            as_of=card.as_of,
            source=card.source,
            verified=card.verified,
        )
    return schemas.Broadcast(
        id=row.id,
        name=row.name,
        status=row.status,
        social_account_id=row.social_account_id,
        account_label=_label(acct),
        segment_id=row.segment_id,
        segment_name=row.segment_name,
        template=BroadcastTemplate(
            name=row.template_name,
            language=row.template_language,
            category=row.template_category,
            body=row.template_body,
        ),
        variables=[VariableOut.model_validate(v) for v in row.variables],
        scheduled_at=row.scheduled_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        paused_code=row.paused_code,
        paused_reason=row.paused_reason,
        audience_size=row.audience_size,
        cost=cost,
        counts=_counts_out(raw),
        created_at=row.created_at,
    )


async def to_out(session: AsyncSession, row: Broadcast) -> schemas.Broadcast:
    raw = await repo.counts(session, row.id)
    return _out(row, raw, await accounts.get(session, row.social_account_id))


async def get_out(session: AsyncSession, broadcast_id: uuid.UUID) -> schemas.Broadcast:
    return await to_out(session, await get(session, broadcast_id))


async def list_out(
    session: AsyncSession, *, status: str | None, limit: int, offset: int
) -> BroadcastList:
    query = select(Broadcast)
    total_query = select(func.count()).select_from(Broadcast)
    if status:
        query = query.where(Broadcast.status == status)
        total_query = total_query.where(Broadcast.status == status)
    rows = (
        await session.scalars(
            query.order_by(Broadcast.created_at.desc(), Broadcast.id.desc())
            .limit(min(limit, LIST_MAX))
            .offset(offset)
        )
    ).all()
    raw = await repo.counts_for(session, [r.id for r in rows])
    labels = {a.id: a for a in await accounts.list_all(session)}
    return BroadcastList(
        items=[_out(r, raw[r.id], labels.get(r.social_account_id)) for r in rows],
        total=int(await session.scalar(total_query) or 0),
    )


def reason_for(recipient: BroadcastRecipient, message: Message | None) -> str | None:
    """Why a recipient was skipped or failed, in plain words: the skip's reason, what stopped the
    hand-over, or WhatsApp's reason for a failed message (its code mapped to our words, else the
    reason WhatsApp gave)."""
    if recipient.skip_reason:
        return SKIP_WORDS.get(SkipReason(recipient.skip_reason))
    if recipient.state == "failed":
        return recipient.error_message or "The message couldn't be handed to WhatsApp."
    if message is None or message.status != "failed":
        return None
    code = message.error_code or ""
    if code in _READABLE:
        return readable_error(code, "whatsapp", platform_message=message.error_message or "")
    return message.error_message or "WhatsApp couldn't deliver this message."


_READABLE = frozenset(
    {
        "reply_window_closed",
        "account_needs_reconnect",
        "capability_unavailable",
        "recipient_unavailable",
        "platform_rate_limited",
        "platform_unavailable",
        "delivery_unknown",
    }
)


async def recipients(
    session: AsyncSession,
    broadcast_id: uuid.UUID,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> RecipientList:
    await get(session, broadcast_id)  # 404 for another workspace's broadcast
    rows, total = await repo.recipient_page(
        session, broadcast_id, status=status, limit=min(limit, LIST_MAX), offset=offset
    )
    contacts_by_id = {
        c.id: c
        for c in (
            await session.scalars(
                select(Contact).where(Contact.id.in_([r[0].contact_id for r in rows]))
            )
        ).all()
    }
    conversations = await _conversations(session, [r[0].contact_id for r in rows])
    items: list[Recipient] = []
    for recipient, shown, message in rows:
        contact = contacts_by_id.get(recipient.contact_id)
        items.append(
            Recipient(
                id=recipient.id,
                contact_id=recipient.contact_id,
                contact_name=contact_service.display_name(contact) if contact else "Customer",
                username=contact.username if contact else None,
                status=shown,
                reason=reason_for(recipient, message) if shown in ("failed", "skipped") else None,
                replied=recipient.replied_at is not None,
                stopped=recipient.stopped_at is not None,
                dispatched_at=recipient.dispatched_at,
                conversation_id=conversations.get(recipient.contact_id),
            )
        )
    return RecipientList(items=items, total=total)


async def _conversations(
    session: AsyncSession, contact_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    from socialhood.models.inbox import Conversation

    if not contact_ids:
        return {}
    rows = await session.execute(
        select(Conversation.contact_id, Conversation.id).where(
            Conversation.contact_id.in_(contact_ids)
        )
    )
    return {contact_id: conv_id for contact_id, conv_id in rows.all()}
