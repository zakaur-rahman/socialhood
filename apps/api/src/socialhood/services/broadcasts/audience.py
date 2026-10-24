"""Who a broadcast reaches and who it skips (GR-23).

The audience is a saved segment (GR-17), narrowed to the contacts of the broadcast's WhatsApp
number. Marketing consent decides each one, from the contact's latest WhatsApp marketing record
(GR-02, ``contact_consents``; the latest by ``occurred_at`` wins, then by creation):

- ``granted``: sent to;
- ``revoked``: skipped as ``opted_out``;
- no record at all: skipped as ``no_consent``. Not knowing is not agreeing.

A contact whose template variable has no value and no fallback is skipped as ``missing_value``.
Skipped contacts are counted and listed, never sent. The segment's own platform and number are
replaced by the broadcast's (a segment saved for Instagram still means "these people, on this
number"). A segment can be at most ``AUDIENCE_CAP`` contacts.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.broadcasts import RecipientState, SkipReason
from socialhood.models.contacts import (
    ConsentChannel,
    ConsentPurpose,
    ConsentStatus,
    ContactConsent,
    ContactSegment,
)
from socialhood.models.inbox import Contact
from socialhood.schemas.broadcasts import AudienceCounts
from socialhood.schemas.contacts import ContactFilterSpec
from socialhood.services import contacts
from socialhood.services.broadcasts import variables as variable_rules
from socialhood.services.saved_replies import contact_values

AUDIENCE_CAP = 30_000
CHUNK = 500


@dataclass(frozen=True)
class Planned:
    """What happens to one contact in a broadcast."""

    contact_id: uuid.UUID
    position: int
    state: str  # pending or skipped
    skip_reason: str | None
    params: list[str]


def segment_filter(segment: ContactSegment, account_id: uuid.UUID) -> contacts.ContactFilter:
    """The segment's filter on the broadcast's WhatsApp number."""
    spec = ContactFilterSpec.model_validate(segment.filter or {})
    return replace(contacts.filter_from_spec(spec), platform="whatsapp", account_id=account_id)


def _latest_consent() -> Any:
    """The contact's latest WhatsApp marketing record's status (null: no record)."""
    return (
        select(ContactConsent.status)
        .where(
            ContactConsent.contact_id == Contact.id,
            ContactConsent.channel == ConsentChannel.WHATSAPP,
            ContactConsent.purpose == ConsentPurpose.MARKETING,
        )
        .order_by(ContactConsent.occurred_at.desc(), ContactConsent.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )


def _skip_for(consent: str | None) -> str | None:
    if consent == ConsentStatus.GRANTED:
        return None
    return SkipReason.OPTED_OUT if consent == ConsentStatus.REVOKED else SkipReason.NO_CONSENT


async def consent_counts(session: AsyncSession, filt: contacts.ContactFilter) -> dict[str, int]:
    """Matching contacts by their latest consent: granted, revoked, none."""
    # _filtered is the contacts list's query; reusing it keeps a segment's meaning in one place.
    sub = (
        contacts._filtered(filt)
        .with_only_columns(Contact.id, _latest_consent().label("consent"))
        .subquery()
    )
    rows = (
        await session.execute(select(sub.c.consent, func.count()).group_by(sub.c.consent))
    ).all()
    counts = {"granted": 0, "revoked": 0, "none": 0}
    for consent, count in rows:
        counts[consent if consent in counts else "none"] += int(count)
    return counts


async def plan(
    session: AsyncSession,
    filt: contacts.ContactFilter,
    variables: Sequence[Mapping[str, Any]],
) -> list[Planned]:
    """Every contact of the audience in a fixed order, each sent to or skipped, with the template
    parameters of those sent to. Refuses a segment over AUDIENCE_CAP."""
    rows = (
        await session.execute(
            contacts._filtered(filt)
            .with_only_columns(Contact.id, _latest_consent().label("consent"))
            .order_by(Contact.id)
            .limit(AUDIENCE_CAP + 1)
        )
    ).all()
    if len(rows) > AUDIENCE_CAP:
        raise ApiError(
            "validation_error",
            errors=[
                FieldError(
                    field="segment_id",
                    message=(
                        f"That segment has more than {AUDIENCE_CAP:,} contacts. "
                        "Narrow it to send a broadcast."
                    ),
                )
            ],
        )
    eligible = [contact_id for contact_id, consent in rows if _skip_for(consent) is None]
    params = await _parameters(session, eligible, variables)
    planned: list[Planned] = []
    for position, (contact_id, consent) in enumerate(rows):
        skip = _skip_for(consent)
        values = params.get(contact_id)
        if skip is None and values is None:
            skip = SkipReason.MISSING_VALUE
        planned.append(
            Planned(
                contact_id=contact_id,
                position=position,
                state=RecipientState.SKIPPED if skip else RecipientState.PENDING,
                skip_reason=skip,
                params=values or [],
            )
        )
    return planned


async def _parameters(
    session: AsyncSession, contact_ids: Sequence[uuid.UUID], variables: Sequence[Mapping[str, Any]]
) -> dict[uuid.UUID, list[str] | None]:
    """Template parameters for each contact (None: a value is missing). No variables: no loading."""
    if not variables:
        return {contact_id: [] for contact_id in contact_ids}
    out: dict[uuid.UUID, list[str] | None] = {}
    for start in range(0, len(contact_ids), CHUNK):
        chunk = contact_ids[start : start + CHUNK]
        found = (await session.scalars(select(Contact).where(Contact.id.in_(chunk)))).all()
        for contact in found:
            out[contact.id] = variable_rules.resolve(variables, contact_values(contact))
    return out


def counts_from(
    consent: Mapping[str, int], planned: Sequence[Planned] | None = None
) -> AudienceCounts:
    """The preview's numbers. With a plan, the eligible number already leaves out the contacts
    whose variables are missing; without one it is the granted count."""
    missing = sum(1 for p in planned or () if p.skip_reason == SkipReason.MISSING_VALUE)
    return AudienceCounts(
        matching=sum(consent.values()),
        eligible=consent.get("granted", 0) - missing,
        opted_out=consent.get("revoked", 0),
        no_consent=consent.get("none", 0),
        missing_value=missing,
    )


async def sample(
    session: AsyncSession, filt: contacts.ContactFilter, planned: Sequence[Planned]
) -> Contact | None:
    """A contact to draw the preview with: the first one that would be sent to, else the first
    contact of the segment, else none."""
    first = next((p.contact_id for p in planned if p.state == RecipientState.PENDING), None)
    if first is None:
        ids = await contacts.matching_ids(session, filt, limit=1)
        first = ids[0] if ids else None
    if first is None:
        return None
    return await session.scalar(select(Contact).where(Contact.id == first))
