"""Contacts as records (GR-02): list and filter, edit, tag, custom fields, consent, export.

Rules:
- A contact is one channel identity (PD-10). Its lead score and conversation come from its one
  conversation on that account, when it has messaged.
- The list is newest activity first, then id, as a keyset cursor. Activity is the latest of the
  conversation's last message (either way: every send path keeps it), the contact's
  ``last_activity_at`` (a comment, ``touch_activity`` from comment intake) and when the contact
  was created.
- An email is normalised to lower case and checked for shape; a phone to E.164, with a ten-digit
  Indian mobile number (6 to 9 first) taken as +91. Set by a member, either is "member" and not
  verified.
- Custom field values are validated by their definition's type; an unknown key is refused. A
  definition's key and type never change; deleting one removes its values from every contact.
  The number of definitions is capped by the plan's ``contact_fields``.
- Consent is append-only: each record says what changed, where it came from and its evidence;
  the latest per (contact, channel, purpose) is current.
- Tags are case-insensitively unique per workspace. Contacts are never metered (PD-2).
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from sqlalchemy import Select, and_, exists, func, literal, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import SocialAccount
from socialhood.models.contacts import (
    ConsentChannel,
    ConsentPurpose,
    ConsentSource,
    ConsentStatus,
    ContactConsent,
    ContactFieldDefinition,
    ContactTag,
    FieldType,
    Tag,
)
from socialhood.models.inbox import Contact, Conversation
from socialhood.repositories.base import scoped_delete, scoped_update
from socialhood.schemas.contacts import (
    Consent,
    ContactList,
    ContactListItem,
    ContactPatch,
    ContactRecord,
    FieldDefinition,
    FieldDefinitionCreate,
    FieldDefinitionList,
    FieldDefinitionPatch,
    TagList,
    TagRef,
)
from socialhood.schemas.contacts import Tag as TagOut

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
DIGITS = re.compile(r"\D")
TEXT_MAX = 500
DEFAULT_LIMIT = 50
EXPORT_BATCH = 500


# ---------------------------------------------------------------- normalising values


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL.match(email):
        raise ValueError("Enter an email address like name@example.com.")
    return email


def normalize_phone(value: str) -> str:
    """E.164. A ten-digit Indian mobile number (6 to 9 first) is taken as +91."""
    raw = value.strip()
    digits = DIGITS.sub("", raw)
    if raw.startswith("+"):
        number = digits
    elif len(digits) == 10 and digits[0] in "6789":
        number = "91" + digits
    elif len(digits) == 12 and digits.startswith("91"):
        number = digits
    else:
        raise ValueError("Enter a phone number with its country code, like +91 98765 43210.")
    if not 8 <= len(number) <= 15:
        raise ValueError("Enter a phone number with its country code, like +91 98765 43210.")
    return "+" + number


class FieldSpec(Protocol):
    """A custom field's type and choice options (a ContactFieldDefinition, or a flow's copy)."""

    @property
    def type(self) -> str: ...

    @property
    def options(self) -> list[str]: ...


def field_value(definition: FieldSpec, value: Any) -> Any:
    """A custom field's value as stored, or ValueError with what to fix."""
    kind = definition.type
    if kind == FieldType.TEXT:
        if not isinstance(value, str) or len(value) > TEXT_MAX:
            raise ValueError(f"Up to {TEXT_MAX} characters of text.")
        return value.strip()
    if kind == FieldType.EMAIL:
        if not isinstance(value, str):
            raise ValueError("Enter an email address.")
        return normalize_email(value)
    if kind == FieldType.PHONE:
        if not isinstance(value, str):
            raise ValueError("Enter a phone number.")
        return normalize_phone(value)
    if kind == FieldType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Enter a number.")
        return value
    if kind == FieldType.DATE:
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as error:
            raise ValueError("Enter a date as YYYY-MM-DD.") from error
    if kind == FieldType.CHOICE:
        if value not in definition.options:
            raise ValueError("Choose one of the field's options.")
        return value
    raise ValueError("Unknown field type.")


# ---------------------------------------------------------------- activity


def touch_activity(contact: Contact, at: datetime) -> None:
    """A comment (activity outside the conversation) moves the contact up the list."""
    if contact.last_activity_at is None or at > contact.last_activity_at:
        contact.last_activity_at = at


# ---------------------------------------------------------------- listing


@dataclass(frozen=True, kw_only=True)
class ContactFilter:
    q: str | None = None  # part of the name, @username, email or phone
    tag_ids: tuple[uuid.UUID, ...] = ()  # every one of them
    platform: str | None = None
    account_id: uuid.UUID | None = None
    has_email: bool | None = None
    has_phone: bool | None = None
    marketing_consent: str | None = None  # a channel with current consent granted
    min_lead_score: int | None = None
    active_after: datetime | None = None
    active_before: datetime | None = None
    # Custom fields by key: a value to equal, ignoring case, or None for any value.
    fields: tuple[tuple[str, str | None], ...] = ()


# Postgres's greatest() skips nulls, so this is never null.
_activity = func.greatest(
    Conversation.last_message_at, Contact.last_activity_at, Contact.created_at
)


def _encode(at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([at.isoformat(), str(row_id)], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, row_id = json.loads(raw)
        return datetime.fromisoformat(at), uuid.UUID(row_id)
    except (ValueError, TypeError) as error:
        raise ApiError("bad_request", "That page link isn't valid any more.") from error


def _current_consent(channel: str) -> Any:
    """True when the contact's latest marketing record for ``channel`` grants it."""
    latest = (
        select(ContactConsent.status)
        .where(
            ContactConsent.contact_id == Contact.id,
            ContactConsent.channel == channel,
            ContactConsent.purpose == ConsentPurpose.MARKETING,
        )
        .order_by(ContactConsent.occurred_at.desc(), ContactConsent.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    return latest == ConsentStatus.GRANTED


def _filtered(filt: ContactFilter) -> Select[Contact, Conversation, SocialAccount]:
    query = (
        select(Contact, Conversation, SocialAccount)
        .join(SocialAccount, SocialAccount.id == Contact.social_account_id)
        .outerjoin(
            Conversation,
            and_(
                Conversation.contact_id == Contact.id,
                Conversation.social_account_id == Contact.social_account_id,
            ),
        )
    )
    if filt.q:
        term = f"%{filt.q.strip().lstrip('@')}%"
        query = query.where(
            or_(
                Contact.display_name.ilike(term),
                Contact.username.ilike(term),
                Contact.email.ilike(term),
                Contact.phone.ilike(term),
            )
        )
    for tag_id in filt.tag_ids:
        query = query.where(
            exists().where(ContactTag.contact_id == Contact.id, ContactTag.tag_id == tag_id)
        )
    if filt.platform:
        query = query.where(SocialAccount.platform == filt.platform)
    if filt.account_id:
        query = query.where(Contact.social_account_id == filt.account_id)
    if filt.has_email is not None:
        query = query.where(
            Contact.email.is_not(None) if filt.has_email else Contact.email.is_(None)
        )
    if filt.has_phone is not None:
        query = query.where(
            Contact.phone.is_not(None) if filt.has_phone else Contact.phone.is_(None)
        )
    if filt.marketing_consent:
        query = query.where(_current_consent(filt.marketing_consent))
    if filt.min_lead_score is not None:
        query = query.where(Conversation.lead_score >= filt.min_lead_score)
    if filt.active_after:
        query = query.where(_activity >= filt.active_after)
    if filt.active_before:
        query = query.where(_activity < filt.active_before)
    for key, value in filt.fields:
        query = query.where(
            Contact.fields.has_key(key)
            if value is None
            else func.lower(Contact.fields[key].astext) == value.lower()
        )
    return query


async def check_filter(session: AsyncSession, filt: ContactFilter) -> None:
    """Refuses a filter on a custom field the workspace doesn't have."""
    if not filt.fields:
        return
    known = await _definitions(session)
    unknown = sorted({key for key, _ in filt.fields} - known.keys())
    if unknown:
        raise ApiError(
            "validation_error",
            errors=[
                FieldError(field="field", message=f"There's no field called “{key}”.")
                for key in unknown
            ],
        )


async def _tags_for(
    session: AsyncSession, contact_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[TagRef]]:
    if not contact_ids:
        return {}
    rows = await session.execute(
        select(ContactTag.contact_id, Tag)
        .join(Tag, Tag.id == ContactTag.tag_id)
        .where(ContactTag.contact_id.in_(contact_ids))
        .order_by(func.lower(Tag.name))
    )
    out: dict[uuid.UUID, list[TagRef]] = {}
    for contact_id, tag in rows.all():
        out.setdefault(contact_id, []).append(TagRef(id=tag.id, name=tag.name, color=tag.color))
    return out


def display_name(contact: Contact) -> str:
    if contact.display_name:
        return contact.display_name
    return f"@{contact.username}" if contact.username else "Customer"


def _item(
    contact: Contact,
    conv: Conversation | None,
    acct: SocialAccount,
    tags: list[TagRef],
    activity: datetime | None,
) -> dict[str, Any]:
    return {
        "id": contact.id,
        "social_account_id": contact.social_account_id,
        "platform": acct.platform,
        "name": display_name(contact),
        "username": contact.username,
        "profile_picture_url": contact.profile_picture_url,
        "email": contact.email,
        "phone": contact.phone,
        "tags": tags,
        "lead_score": conv.lead_score if conv else None,
        "conversation_id": conv.id if conv else None,
        "last_activity_at": activity,
        "first_seen_at": contact.first_seen_at or contact.created_at,
    }


async def list_contacts(
    session: AsyncSession, filt: ContactFilter, *, cursor: str | None, limit: int = DEFAULT_LIMIT
) -> ContactList:
    query = _filtered(filt)
    if cursor:
        at, row_id = _decode(cursor)
        query = query.where(or_(_activity < at, and_(_activity == at, Contact.id < row_id)))
    rows = (
        await session.execute(
            query.add_columns(_activity.label("activity"))
            .order_by(_activity.desc(), Contact.id.desc())
            .limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    tags = await _tags_for(session, [r[0].id for r in page])
    items = [
        ContactListItem.model_validate(_item(c, v, a, tags.get(c.id, []), at))
        for c, v, a, at in page
    ]
    next_cursor = _encode(page[-1][3], page[-1][0].id) if len(rows) > limit else None
    return ContactList(items=items, next_cursor=next_cursor)


# ---------------------------------------------------------------- one contact


async def _row(
    session: AsyncSession, contact_id: uuid.UUID
) -> tuple[Contact, Conversation | None, SocialAccount, datetime]:
    row = (
        await session.execute(
            _filtered(ContactFilter())
            .add_columns(_activity.label("activity"))
            .where(Contact.id == contact_id)
        )
    ).one_or_none()
    if row is None:
        raise ApiError("not_found", "That contact wasn't found.")
    return row[0], row[1], row[2], row[3]


async def current_consents(session: AsyncSession, contact_id: uuid.UUID) -> list[Consent]:
    rows = (
        await session.scalars(
            select(ContactConsent)
            .where(ContactConsent.contact_id == contact_id)
            .order_by(
                ContactConsent.channel,
                ContactConsent.occurred_at.desc(),
                ContactConsent.created_at.desc(),
            )
            .ext(distinct_on(ContactConsent.channel))
        )
    ).all()
    return [
        Consent.model_validate(
            {
                "channel": r.channel,
                "purpose": r.purpose,
                "status": r.status,
                "source": r.source,
                "occurred_at": r.occurred_at,
                "note": r.evidence.get("note") if r.source == ConsentSource.MEMBER else None,
            }
        )
        for r in rows
    ]


async def get_record(session: AsyncSession, contact_id: uuid.UUID) -> ContactRecord:
    contact, conv, acct, activity = await _row(session, contact_id)
    tags = await _tags_for(session, [contact.id])
    return ContactRecord.model_validate(
        {
            **_item(contact, conv, acct, tags.get(contact.id, []), activity),
            "fields": contact.fields or {},
            "email_source": contact.email_source,
            "email_verified": contact.email_verified,
            "phone_source": contact.phone_source,
            "phone_verified": contact.phone_verified,
            "first_entry_source": contact.first_entry_source,
            "consents": await current_consents(session, contact.id),
        }
    )


async def _definitions(session: AsyncSession) -> dict[str, ContactFieldDefinition]:
    rows = await session.scalars(select(ContactFieldDefinition))
    return {d.key: d for d in rows.all()}


async def update_contact(session: AsyncSession, contact_id: uuid.UUID, body: ContactPatch) -> None:
    from socialhood.services.webhooks import events

    contact, _, _, _ = await _row(session, contact_id)
    before = (contact.email, contact.phone, dict(contact.fields or {}))
    errors: list[FieldError] = []
    if body.clear_email:
        contact.email, contact.email_source, contact.email_verified = None, None, False
    elif body.email is not None:
        try:
            contact.email = normalize_email(body.email)
            contact.email_source, contact.email_verified = "member", False
        except ValueError as error:
            errors.append(FieldError(field="email", message=str(error)))
    if body.clear_phone:
        contact.phone, contact.phone_source, contact.phone_verified = None, None, False
    elif body.phone is not None:
        try:
            contact.phone = normalize_phone(body.phone)
            contact.phone_source, contact.phone_verified = "member", False
        except ValueError as error:
            errors.append(FieldError(field="phone", message=str(error)))
    if body.fields:
        definitions = await _definitions(session)
        merged = dict(contact.fields or {})
        for key, value in body.fields.items():
            definition = definitions.get(key)
            if definition is None:
                errors.append(FieldError(field=f"fields.{key}", message="There's no such field."))
            elif value is None:
                merged.pop(key, None)
            else:
                try:
                    merged[key] = field_value(definition, value)
                except ValueError as error:
                    errors.append(FieldError(field=f"fields.{key}", message=str(error)))
        contact.fields = merged
    if errors:
        raise ApiError("validation_error", errors=errors)
    await session.flush()
    await events.contact_updated(session, contact, changes(before, contact))


def changes(before: tuple[str | None, str | None, dict[str, Any]], contact: Contact) -> list[str]:
    """What changed on a contact since ``before`` (email, phone, fields): contact.updated."""
    email, phone, fields = before
    changed = [
        name
        for name, old, new in (("email", email, contact.email), ("phone", phone, contact.phone))
        if old != new
    ]
    now = contact.fields or {}
    changed += [
        f"fields.{key}" for key in sorted(set(fields) | set(now)) if fields.get(key) != now.get(key)
    ]
    return changed


# ---------------------------------------------------------------- tags


async def list_tags(session: AsyncSession) -> TagList:
    counts = (
        select(ContactTag.tag_id, func.count().label("n")).group_by(ContactTag.tag_id).subquery()
    )
    rows = (
        await session.execute(
            select(Tag, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.tag_id == Tag.id)
            .order_by(func.lower(Tag.name))
        )
    ).all()
    return TagList(
        items=[TagOut(id=t.id, name=t.name, color=t.color, contact_count=int(n)) for t, n in rows]
    )


async def _tag(session: AsyncSession, tag_id: uuid.UUID) -> Tag:
    tag = await session.scalar(select(Tag).where(Tag.id == tag_id))
    if tag is None:
        raise ApiError("not_found", "That tag wasn't found.")
    return tag


async def _unique_name(
    session: AsyncSession, name: str, *, except_id: uuid.UUID | None = None
) -> None:
    query = select(Tag.id).where(func.lower(Tag.name) == name.strip().lower())
    if except_id:
        query = query.where(Tag.id != except_id)
    if await session.scalar(query) is not None:
        raise ApiError("conflict", "A tag with that name already exists.")


async def create_tag(session: AsyncSession, name: str, color: int) -> TagOut:
    await _unique_name(session, name)
    tag = Tag(name=name.strip(), color=color)
    session.add(tag)
    try:
        await session.flush()
    except IntegrityError as error:  # a concurrent create with the same name
        raise ApiError("conflict", "A tag with that name already exists.") from error
    return TagOut(id=tag.id, name=tag.name, color=tag.color)


async def update_tag(
    session: AsyncSession, tag_id: uuid.UUID, *, name: str | None, color: int | None
) -> TagOut:
    tag = await _tag(session, tag_id)
    if name is not None:
        await _unique_name(session, name, except_id=tag.id)
        tag.name = name.strip()
    if color is not None:
        tag.color = color
    await session.flush()
    return TagOut(id=tag.id, name=tag.name, color=tag.color)


async def delete_tag(session: AsyncSession, tag_id: uuid.UUID) -> None:
    tag = await _tag(session, tag_id)
    await session.delete(tag)  # contact_tags rows go with it (ON DELETE CASCADE)
    await session.flush()


async def change_tags(
    session: AsyncSession,
    contact_ids: Sequence[uuid.UUID],
    *,
    add: Sequence[uuid.UUID],
    remove: Sequence[uuid.UUID],
    user_id: uuid.UUID | None,
) -> int:
    """Add and remove tags on contacts; returns how many contacts exist among those named. Each
    tag that's actually added or removed is a contact.tagged event (GR-04)."""
    from socialhood.services.webhooks import events

    wanted = set(add) | set(remove)
    if wanted:
        found = set((await session.scalars(select(Tag.id).where(Tag.id.in_(wanted)))).all())
        missing = wanted - found
        if missing:
            raise ApiError("not_found", "One of those tags wasn't found.")
    ids = list((await session.scalars(select(Contact.id).where(Contact.id.in_(contact_ids)))).all())
    changed: list[tuple[uuid.UUID, uuid.UUID, bool]] = []
    if remove and ids:
        changed += [
            (contact_id, tag_id, False)
            for contact_id, tag_id in (
                await session.execute(
                    select(ContactTag.contact_id, ContactTag.tag_id).where(
                        ContactTag.contact_id.in_(ids), ContactTag.tag_id.in_(remove)
                    )
                )
            ).all()
        ]
        await session.execute(
            scoped_delete(ContactTag).where(
                ContactTag.contact_id.in_(ids), ContactTag.tag_id.in_(remove)
            )
        )
    for contact_id in ids:
        for tag_id in add:
            exists_already = await session.scalar(
                select(ContactTag.tag_id).where(
                    ContactTag.contact_id == contact_id, ContactTag.tag_id == tag_id
                )
            )
            if exists_already is None:
                session.add(
                    ContactTag(contact_id=contact_id, tag_id=tag_id, added_by_user_id=user_id)
                )
                changed.append((contact_id, tag_id, True))
    await session.flush()
    if changed and await events.wanted(session, "contact.tagged"):
        people = {
            c.id: c
            for c in (
                await session.scalars(
                    select(Contact).where(Contact.id.in_({c for c, _, _ in changed}))
                )
            ).all()
        }
        names = dict(
            (await session.execute(select(Tag.id, Tag.name).where(Tag.id.in_(wanted)))).all()
        )
        await events.contacts_tagged(
            session,
            [
                events.TagChange(people[c], t, names.get(t, ""), added)
                for c, t, added in changed
                if c in people
            ],
        )
    return len(ids)


# ---------------------------------------------------------------- custom fields


def _definition_out(d: ContactFieldDefinition) -> FieldDefinition:
    return FieldDefinition.model_validate(
        {
            "id": d.id,
            "key": d.key,
            "label": d.label,
            "type": d.type,
            "options": d.options,
            "position": d.position,
        }
    )


async def list_fields(session: AsyncSession) -> FieldDefinitionList:
    rows = (
        await session.scalars(
            select(ContactFieldDefinition).order_by(
                ContactFieldDefinition.position, ContactFieldDefinition.created_at
            )
        )
    ).all()
    limit = entitlement(await current_plan(session), "contact_fields")
    return FieldDefinitionList(items=[_definition_out(d) for d in rows], limit=limit)


def _options(kind: str, options: Sequence[str]) -> list[str]:
    cleaned = [o.strip() for o in options if o.strip()]
    if kind == FieldType.CHOICE:
        if not cleaned:
            raise ApiError(
                "validation_error",
                errors=[FieldError(field="options", message="A choice field needs options.")],
            )
        if any(len(o) > 60 for o in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ApiError(
                "validation_error",
                errors=[
                    FieldError(field="options", message="Options are unique, up to 60 characters.")
                ],
            )
        return cleaned
    return []


async def create_field(session: AsyncSession, body: FieldDefinitionCreate) -> FieldDefinition:
    limit = entitlement(await current_plan(session), "contact_fields")
    count = await session.scalar(select(func.count()).select_from(ContactFieldDefinition))
    if limit is not None and int(count or 0) >= limit:
        raise quota_error("contact_fields", limit)
    if await session.scalar(
        select(ContactFieldDefinition.id).where(ContactFieldDefinition.key == body.key)
    ):
        raise ApiError("conflict", "A field with that key already exists.")
    definition = ContactFieldDefinition(
        key=body.key,
        label=body.label.strip(),
        type=body.type,
        options=_options(body.type, body.options),
        position=int(count or 0),
    )
    session.add(definition)
    await session.flush()
    return _definition_out(definition)


async def _field(session: AsyncSession, field_id: uuid.UUID) -> ContactFieldDefinition:
    definition = await session.scalar(
        select(ContactFieldDefinition).where(ContactFieldDefinition.id == field_id)
    )
    if definition is None:
        raise ApiError("not_found", "That field wasn't found.")
    return definition


async def update_field(
    session: AsyncSession, field_id: uuid.UUID, body: FieldDefinitionPatch
) -> FieldDefinition:
    definition = await _field(session, field_id)
    if body.label is not None:
        definition.label = body.label.strip()
    if body.options is not None:
        definition.options = _options(definition.type, body.options)
    if body.position is not None:
        definition.position = body.position
    await session.flush()
    return _definition_out(definition)


async def delete_field(session: AsyncSession, field_id: uuid.UUID) -> None:
    """The definition goes, and its values with it from every contact in the workspace."""
    definition = await _field(session, field_id)
    await session.execute(
        scoped_update(Contact)
        .where(Contact.fields.has_key(definition.key))
        .values(fields=Contact.fields.op("-")(literal(definition.key)))
        .execution_options(synchronize_session=False)
    )
    await session.delete(definition)
    await session.flush()


# ---------------------------------------------------------------- consent


async def record_consent(
    session: AsyncSession,
    contact_id: uuid.UUID,
    *,
    channel: str,
    status: str,
    source: str,
    evidence: dict[str, Any],
    at: datetime,
) -> ContactConsent:
    """Append one consent record; the latest per channel is current."""
    if channel not in set(ConsentChannel) or status not in set(ConsentStatus):
        raise ValueError(f"unknown consent {channel}/{status}")
    row = ContactConsent(
        contact_id=contact_id,
        channel=channel,
        purpose=ConsentPurpose.MARKETING,
        status=status,
        source=source,
        evidence=evidence,
        occurred_at=at,
    )
    session.add(row)
    await session.flush()
    return row


async def record_member_consent(
    session: AsyncSession,
    contact_id: uuid.UUID,
    *,
    channel: str,
    status: str,
    note: str,
    user_id: uuid.UUID,
    at: datetime,
) -> list[Consent]:
    await _row(session, contact_id)  # 404 for another workspace's or a missing contact
    await record_consent(
        session,
        contact_id,
        channel=channel,
        status=status,
        source=ConsentSource.MEMBER,
        evidence={"note": note.strip(), "user_id": str(user_id)},
        at=at,
    )
    return await current_consents(session, contact_id)


# ---------------------------------------------------------------- export


EXPORT_COLUMNS = (
    "Name",
    "Username",
    "Platform",
    "Email",
    "Phone",
    "Tags",
    "Lead score",
    "Last activity",
    "First seen",
    "Instagram marketing",
    "WhatsApp marketing",
)


async def export_rows(session: AsyncSession, filt: ContactFilter) -> AsyncIterator[list[str]]:
    """The CSV: a header, then one row per contact, newest activity first, in batches. Custom
    fields follow the fixed columns, in their order."""
    definitions = (
        await session.scalars(
            select(ContactFieldDefinition).order_by(
                ContactFieldDefinition.position, ContactFieldDefinition.created_at
            )
        )
    ).all()
    yield [*EXPORT_COLUMNS, *(d.label for d in definitions)]
    cursor: tuple[datetime, uuid.UUID] | None = None
    instagram = _current_consent(ConsentChannel.INSTAGRAM).label("ig")
    whatsapp = _current_consent(ConsentChannel.WHATSAPP).label("wa")
    while True:
        query = _filtered(filt).add_columns(_activity.label("activity"), instagram, whatsapp)
        if cursor:
            at, row_id = cursor
            query = query.where(or_(_activity < at, and_(_activity == at, Contact.id < row_id)))
        rows = (
            await session.execute(
                query.order_by(_activity.desc(), Contact.id.desc()).limit(EXPORT_BATCH)
            )
        ).all()
        if not rows:
            return
        tags = await _tags_for(session, [r[0].id for r in rows])
        for contact, conv, acct, activity, ig, wa in rows:
            fields = contact.fields or {}
            yield [
                display_name(contact),
                contact.username or "",
                acct.platform,
                contact.email or "",
                contact.phone or "",
                "; ".join(t.name for t in tags.get(contact.id, [])),
                "" if conv is None or conv.lead_score is None else str(conv.lead_score),
                activity.isoformat() if activity else "",
                (contact.first_seen_at or contact.created_at).isoformat(),
                "yes" if ig else "",
                "yes" if wa else "",
                *("" if fields.get(d.key) is None else str(fields[d.key]) for d in definitions),
            ]
        cursor = (rows[-1][3], rows[-1][0].id)
        if len(rows) < EXPORT_BATCH:
            return


def safe_cell(value: str) -> str:
    """CSV injection guard: a cell a spreadsheet would read as a formula gets a leading quote."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
