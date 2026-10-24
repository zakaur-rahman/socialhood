"""Saved segments and bulk tagging by filter (GR-17). Nothing here commits.

Rules:
- A segment is a name and a contact filter, stored as the filter's own JSON, not a list of
  people: it is always whoever matches now. Names are unique in any case, per workspace.
- A saved filter on a tag or a custom field that is later deleted keeps working: a deleted tag
  matches nobody, and the list refuses a field the workspace no longer has (the page then shows
  the message), so a stale segment never silently widens.
- Bulk tagging names its contacts (up to 500) or gives a filter for everyone it matches, up to
  ``BULK_FILTER_CAP``. A bigger match is refused with the count, so nobody tags ten thousand people
  by accident; the member narrows the filter. Every change goes through ``contacts.change_tags``
  (one ``contact.tagged`` event per real change) and one log line says who, how many and which tags.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.contacts import ContactSegment, Tag
from socialhood.observability.logging import get_logger
from socialhood.repositories.base import scoped_delete
from socialhood.schemas.contacts import (
    BulkTagsUpdate,
    ContactFilterOut,
    ContactFilterSpec,
    Segment,
    SegmentCreate,
    SegmentList,
    SegmentPatch,
)
from socialhood.services import contacts

log = get_logger(__name__)

BULK_FILTER_CAP = 5000
MAX_SEGMENTS = 50


def segment_out(row: ContactSegment) -> Segment:
    return Segment(
        id=row.id,
        name=row.name,
        filter=ContactFilterOut.model_validate(row.filter or {}),
        created_at=row.created_at,
    )


def stored(spec: ContactFilterSpec) -> dict[str, object]:
    """The filter as saved: only what is set, in JSON types."""
    return spec.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


async def list_segments(session: AsyncSession) -> SegmentList:
    rows = await session.scalars(select(ContactSegment).order_by(func.lower(ContactSegment.name)))
    return SegmentList(items=[segment_out(row) for row in rows.all()])


async def _segment(session: AsyncSession, segment_id: uuid.UUID) -> ContactSegment:
    row = await session.scalar(select(ContactSegment).where(ContactSegment.id == segment_id))
    if row is None:
        raise ApiError("not_found", "That segment wasn't found.")
    return row


async def _unique_name(
    session: AsyncSession, name: str, *, except_id: uuid.UUID | None = None
) -> None:
    query = select(ContactSegment.id).where(func.lower(ContactSegment.name) == name.strip().lower())
    if except_id:
        query = query.where(ContactSegment.id != except_id)
    if await session.scalar(query) is not None:
        raise ApiError("conflict", "A segment with that name already exists.")


async def _check_spec(session: AsyncSession, spec: ContactFilterSpec) -> None:
    """A segment can't be saved on a field that doesn't exist, or a tag that isn't there."""
    await contacts.check_filter(session, contacts.filter_from_spec(spec))
    if spec.tag_ids:
        found = set((await session.scalars(select(Tag.id).where(Tag.id.in_(spec.tag_ids)))).all())
        if found != set(spec.tag_ids):
            raise ApiError("not_found", "One of those tags wasn't found.")


async def validate_new(session: AsyncSession, body: SegmentCreate) -> None:
    """Every refusal ``create_segment`` makes, without saving (the agent checks a proposal with it,
    GR-36): a name in use (409), too many segments (422), a field or tag that isn't there."""
    await _unique_name(session, body.name)
    total = await session.scalar(select(func.count()).select_from(ContactSegment))
    if (total or 0) >= MAX_SEGMENTS:
        raise ApiError(
            "validation_error",
            errors=[
                FieldError(
                    field="name",
                    message=f"A workspace can keep {MAX_SEGMENTS} segments. Delete one first.",
                )
            ],
        )
    await _check_spec(session, body.filter)


async def create_segment(
    session: AsyncSession, body: SegmentCreate, *, user_id: uuid.UUID | None
) -> Segment:
    await validate_new(session, body)
    row = ContactSegment(
        name=body.name.strip(), filter=stored(body.filter), created_by_user_id=user_id
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as error:  # a concurrent create with the same name
        raise ApiError("conflict", "A segment with that name already exists.") from error
    return segment_out(row)


async def update_segment(
    session: AsyncSession, segment_id: uuid.UUID, body: SegmentPatch
) -> Segment:
    row = await _segment(session, segment_id)
    if body.name is not None:
        await _unique_name(session, body.name, except_id=row.id)
        row.name = body.name.strip()
    if body.filter is not None:
        await _check_spec(session, body.filter)
        row.filter = stored(body.filter)
    await session.flush()
    return segment_out(row)


async def delete_segment(session: AsyncSession, segment_id: uuid.UUID) -> None:
    row = await _segment(session, segment_id)
    await session.execute(scoped_delete(ContactSegment, id=row.id))
    await session.flush()


async def bulk_tag(
    session: AsyncSession, body: BulkTagsUpdate, *, user_id: uuid.UUID | None
) -> int:
    """Add and remove tags on the named contacts, or on everyone a filter matches. Returns how
    many contacts the change was applied to."""
    if body.contact_ids is not None:
        ids = body.contact_ids
    else:
        assert body.filter is not None  # BulkTagsUpdate allows one of the two
        filt = contacts.filter_from_spec(body.filter)
        await contacts.check_filter(session, filt)
        ids = await contacts.matching_ids(session, filt, limit=BULK_FILTER_CAP + 1)
        if len(ids) > BULK_FILTER_CAP:
            total = await contacts.count_contacts(session, filt)
            raise ApiError(
                "validation_error",
                errors=[
                    FieldError(
                        field="filter",
                        message=(
                            f"That filter matches {total:,} contacts. "
                            f"Narrow it to {BULK_FILTER_CAP:,} or fewer to tag them at once."
                        ),
                    )
                ],
            )
    updated = await contacts.change_tags(
        session, ids, add=body.add, remove=body.remove, user_id=user_id
    )
    log.info(
        "contacts_bulk_tagged",
        user_id=str(user_id) if user_id else None,
        contacts=updated,
        added=len(body.add),
        removed=len(body.remove),
        by_filter=body.filter is not None,
    )
    return updated
