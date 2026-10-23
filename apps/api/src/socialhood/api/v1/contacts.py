"""Contacts routes (GR-02): the contact list and record, tags, custom fields, consent and the CSV
export. The rules are in services/contacts.py.

Who may do what: any member reads contacts, edits a contact's email, phone and fields, and tags
contacts (agents work leads too); admins manage the workspace's tags and fields, record consent
and export.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.schemas.contacts import (
    BulkTagsResult,
    BulkTagsUpdate,
    ConsentCreate,
    ContactList,
    ContactPatch,
    ContactRecord,
    ContactTagsUpdate,
    FieldDefinition,
    FieldDefinitionCreate,
    FieldDefinitionList,
    FieldDefinitionPatch,
    Tag,
    TagCreate,
    TagList,
    TagPatch,
)
from socialhood.services import contacts as service
from socialhood.services.contacts import ContactFilter

router = APIRouter(prefix="/v1/w/{wid}", tags=["contacts"])


def _filter(
    q: Annotated[str | None, Query(max_length=100)] = None,
    tag_id: Annotated[list[uuid.UUID] | None, Query(max_length=10)] = None,
    platform: Annotated[Literal["instagram", "whatsapp"] | None, Query()] = None,
    account_id: uuid.UUID | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    marketing_consent: Annotated[Literal["instagram", "whatsapp", "email"] | None, Query()] = None,
    min_lead_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    active_after: datetime | None = None,
    active_before: datetime | None = None,
) -> ContactFilter:
    return ContactFilter(
        q=q,
        tag_ids=tuple(tag_id or ()),
        platform=platform,
        account_id=account_id,
        has_email=has_email,
        has_phone=has_phone,
        marketing_consent=marketing_consent,
        min_lead_score=min_lead_score,
        active_after=active_after,
        active_before=active_before,
    )


@router.get("/contacts", operation_id="list_contacts")
async def list_contacts(
    ctx: AnyMember,
    session: Session,
    q: Annotated[str | None, Query(max_length=100)] = None,
    tag_id: Annotated[list[uuid.UUID] | None, Query(max_length=10)] = None,
    platform: Annotated[Literal["instagram", "whatsapp"] | None, Query()] = None,
    account_id: uuid.UUID | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    marketing_consent: Annotated[Literal["instagram", "whatsapp", "email"] | None, Query()] = None,
    min_lead_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    active_after: datetime | None = None,
    active_before: datetime | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ContactList:
    """Newest activity first. ``tag_id`` repeats: a contact must carry every one. ``q`` matches
    part of the name, @username, email or phone; ``marketing_consent`` keeps contacts whose
    current consent for that channel is granted."""
    filt = _filter(
        q, tag_id, platform, account_id, has_email, has_phone, marketing_consent,
        min_lead_score, active_after, active_before,
    )  # fmt: skip
    return await service.list_contacts(session, filt, cursor=cursor, limit=limit)


@router.get(
    "/contacts/export.csv",
    operation_id="export_contacts",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_contacts(
    ctx: Admin,
    session: Session,
    q: Annotated[str | None, Query(max_length=100)] = None,
    tag_id: Annotated[list[uuid.UUID] | None, Query(max_length=10)] = None,
    platform: Annotated[Literal["instagram", "whatsapp"] | None, Query()] = None,
    account_id: uuid.UUID | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    marketing_consent: Annotated[Literal["instagram", "whatsapp", "email"] | None, Query()] = None,
    min_lead_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    active_after: datetime | None = None,
    active_before: datetime | None = None,
) -> StreamingResponse:
    """The filtered contacts as CSV (the R2 data export), streamed: nothing is stored. A cell a
    spreadsheet would read as a formula starts with a quote."""
    filt = _filter(
        q, tag_id, platform, account_id, has_email, has_phone, marketing_consent,
        min_lead_score, active_after, active_before,
    )  # fmt: skip

    async def body() -> AsyncIterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        async for row in service.export_rows(session, filt):
            writer.writerow([service.safe_cell(cell) for cell in row])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    return StreamingResponse(
        body(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="contacts-{stamp}.csv"'},
    )


@router.post("/contacts/bulk-tags", operation_id="bulk_tag_contacts")
async def bulk_tag_contacts(
    body: BulkTagsUpdate, ctx: AnyMember, session: Session
) -> BulkTagsResult:
    """Add and remove tags on up to 500 contacts at once; 404 for an unknown tag."""
    updated = await service.change_tags(
        session, body.contact_ids, add=body.add, remove=body.remove, user_id=ctx.user.id
    )
    await session.commit()
    return BulkTagsResult(updated=updated)


@router.get("/contacts/{contact_id}", operation_id="get_contact")
async def get_contact(contact_id: uuid.UUID, ctx: AnyMember, session: Session) -> ContactRecord:
    return await service.get_record(session, contact_id)


@router.patch("/contacts/{contact_id}", operation_id="update_contact")
async def update_contact(
    contact_id: uuid.UUID, body: ContactPatch, ctx: AnyMember, session: Session
) -> ContactRecord:
    """422 lists each value that doesn't fit (an email's shape, a phone without a country code, a
    field's type or an unknown field)."""
    await service.update_contact(session, contact_id, body)
    out = await service.get_record(session, contact_id)
    await session.commit()
    return out


@router.post("/contacts/{contact_id}/tags", operation_id="tag_contact")
async def tag_contact(
    contact_id: uuid.UUID, body: ContactTagsUpdate, ctx: AnyMember, session: Session
) -> ContactRecord:
    if not await service.change_tags(
        session, [contact_id], add=body.add, remove=body.remove, user_id=ctx.user.id
    ):
        await service.get_record(session, contact_id)  # 404
    out = await service.get_record(session, contact_id)
    await session.commit()
    return out


@router.post("/contacts/{contact_id}/consents", operation_id="record_contact_consent")
async def record_contact_consent(
    contact_id: uuid.UUID, body: ConsentCreate, ctx: Admin, session: Session
) -> ContactRecord:
    """A member records consent given elsewhere, or its withdrawal; the note is the evidence."""
    await service.record_member_consent(
        session,
        contact_id,
        channel=body.channel,
        status=body.status,
        note=body.note,
        user_id=ctx.user.id,
        at=datetime.now(UTC),
    )
    out = await service.get_record(session, contact_id)
    await session.commit()
    return out


# ---- tags


@router.get("/tags", operation_id="list_tags")
async def list_tags(ctx: AnyMember, session: Session) -> TagList:
    """Every tag, by name, with how many contacts carry it."""
    return await service.list_tags(session)


@router.post("/tags", status_code=201, operation_id="create_tag")
async def create_tag(body: TagCreate, ctx: Admin, session: Session) -> Tag:
    """409 when a tag with that name (any case) exists."""
    out = await service.create_tag(session, body.name, body.color)
    await session.commit()
    return out


@router.patch("/tags/{tag_id}", operation_id="update_tag")
async def update_tag(tag_id: uuid.UUID, body: TagPatch, ctx: Admin, session: Session) -> Tag:
    out = await service.update_tag(session, tag_id, name=body.name, color=body.color)
    await session.commit()
    return out


@router.delete("/tags/{tag_id}", status_code=204, operation_id="delete_tag")
async def delete_tag(tag_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    """The tag goes from every contact too."""
    await service.delete_tag(session, tag_id)
    await session.commit()
    return Response(status_code=204)


# ---- custom fields


@router.get("/contact-fields", operation_id="list_contact_fields")
async def list_contact_fields(ctx: AnyMember, session: Session) -> FieldDefinitionList:
    """In order, with the plan's contact_fields limit."""
    return await service.list_fields(session)


@router.post("/contact-fields", status_code=201, operation_id="create_contact_field")
async def create_contact_field(
    body: FieldDefinitionCreate, ctx: Admin, session: Session
) -> FieldDefinition:
    """402 quota_exceeded over the plan's contact_fields; 409 for a key in use."""
    out = await service.create_field(session, body)
    await session.commit()
    return out


@router.patch("/contact-fields/{field_id}", operation_id="update_contact_field")
async def update_contact_field(
    field_id: uuid.UUID, body: FieldDefinitionPatch, ctx: Admin, session: Session
) -> FieldDefinition:
    out = await service.update_field(session, field_id, body)
    await session.commit()
    return out


@router.delete("/contact-fields/{field_id}", status_code=204, operation_id="delete_contact_field")
async def delete_contact_field(field_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    """The field goes, and its values from every contact."""
    await service.delete_field(session, field_id)
    await session.commit()
    return Response(status_code=204)
