"""Saved replies (GR-21): reusable messages a member inserts from the composer with ``/`` and a
flow can send. Admins and owners manage them; any member reads and uses them. Nothing here
commits.

Rules:
- A shortcut is lower case letters, digits, ``-`` and ``_`` (up to 30), unique per workspace. A
  typed ``/Price`` is stored and found as ``price``.
- A body (up to 1,000 characters, the length of an Instagram DM) may use ``{first_name}``,
  ``{username}``, ``{name}``, ``{email}``, ``{phone}`` and the key of any custom field
  (``{city}``). ``{first_name|there}`` names its own fallback. ``{first_name}`` with no name falls
  back to "there", as in automations (services/automations/render). Any other field with no value
  is empty, and a field that doesn't exist is empty too: ``fill`` never leaves a ``{name}`` in
  the text a customer reads.
- Filling is done here, once, for the composer (``fill_for_conversation``), a flow's send step
  (``flow_text``) and the away message (services/business_hours), so all three read the same.
- A workspace keeps up to ``MAX_REPLIES`` replies.
- A flow step names a reply by id and reads its body when it runs; a deleted reply fails that
  step with a plain reason (``MISSING``) and the run stops there.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.inbox import Contact, Conversation
from socialhood.models.replies import SavedReply
from socialhood.schemas.saved_replies import (
    SHORTCUT_PATTERN,
    SavedReplyCreate,
    SavedReplyList,
    SavedReplyUpdate,
)
from socialhood.schemas.saved_replies import SavedReply as SavedReplyOut
from socialhood.services.automations import render

MAX_REPLIES = 200
VARIABLE = re.compile(r"\{([a-z][a-z0-9_]{0,39})(?:\|([^{}]{0,40}))?\}")
SHORTCUT = re.compile(SHORTCUT_PATTERN)
COPY = {
    "shortcut": "Use lower case letters, numbers, - and _, up to 30 characters.",
    "taken": "Another saved reply already uses this shortcut.",
    "limit": f"A workspace can keep up to {MAX_REPLIES} saved replies.",
}
MISSING = ("saved_reply_missing", "The saved reply this step sends was deleted. Choose another.")


def fill(body: str, values: Mapping[str, str | None]) -> str:
    """The body with each ``{key}`` replaced by its value, else its fallback, else nothing
    (``{first_name}`` falls back to "there")."""

    def replace(match: re.Match[str]) -> str:
        key, fallback = match.group(1), match.group(2)
        value = (values.get(key) or "").strip()
        if value:
            return value
        if fallback is not None:
            return fallback
        return render.DEFAULT_FALLBACK["first_name"] if key == "first_name" else ""

    return VARIABLE.sub(replace, body)


def contact_values(contact: Contact | None) -> dict[str, str | None]:
    """What a body can use about a contact: custom fields first, then the built-in ones, so a
    custom field can't change what ``{first_name}`` means."""
    if contact is None:
        return {}
    values: dict[str, str | None] = {
        key: _text(value) for key, value in (contact.fields or {}).items()
    }
    values.update(
        first_name=render.first_name_of(contact.display_name),
        name=contact.display_name,
        username=contact.username,
        email=contact.email,
        phone=contact.phone,
    )
    return values


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, bool | dict | list):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _out(row: SavedReply) -> SavedReplyOut:
    return SavedReplyOut.model_validate(row)


async def list_replies(session: AsyncSession) -> SavedReplyList:
    rows = await session.scalars(select(SavedReply).order_by(SavedReply.shortcut))
    return SavedReplyList(items=[_out(r) for r in rows.all()], max_items=MAX_REPLIES)


async def get_or_404(session: AsyncSession, reply_id: uuid.UUID) -> SavedReply:
    row = await session.scalar(select(SavedReply).where(SavedReply.id == reply_id))
    if row is None:
        raise ApiError("not_found", "That saved reply wasn't found.")
    return row


def normalize_shortcut(value: str) -> str:
    """The shortcut as stored: typed with or without the slash, in any case."""
    cleaned = value.strip().removeprefix("/").lower()
    if not SHORTCUT.fullmatch(cleaned):
        raise ApiError("validation_error", errors=[FieldError("shortcut", COPY["shortcut"])])
    return cleaned


async def _check_free(
    session: AsyncSession, shortcut: str, *, except_id: uuid.UUID | None = None
) -> None:
    query = select(SavedReply.id).where(SavedReply.shortcut == shortcut)
    if except_id is not None:
        query = query.where(SavedReply.id != except_id)
    if await session.scalar(query) is not None:
        raise ApiError("conflict", COPY["taken"])


async def create(
    session: AsyncSession, body: SavedReplyCreate, *, user_id: uuid.UUID | None
) -> SavedReplyOut:
    shortcut = normalize_shortcut(body.shortcut)
    count = await session.scalar(select(func.count()).select_from(SavedReply))
    if (count or 0) >= MAX_REPLIES:
        raise ApiError("validation_error", errors=[FieldError("title", COPY["limit"])])
    await _check_free(session, shortcut)
    row = SavedReply(
        title=body.title.strip(),
        shortcut=shortcut,
        body=body.body.strip(),
        created_by_user_id=user_id,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as error:  # a concurrent create with the same shortcut
        raise ApiError("conflict", COPY["taken"]) from error
    await session.refresh(row)
    return _out(row)


async def update(
    session: AsyncSession, reply_id: uuid.UUID, body: SavedReplyUpdate
) -> SavedReplyOut:
    row = await get_or_404(session, reply_id)
    if body.shortcut is not None:
        shortcut = normalize_shortcut(body.shortcut)
        await _check_free(session, shortcut, except_id=row.id)
        row.shortcut = shortcut
    if body.title is not None:
        row.title = body.title.strip()
    if body.body is not None:
        row.body = body.body.strip()
    try:
        await session.flush()
    except IntegrityError as error:
        raise ApiError("conflict", COPY["taken"]) from error
    await session.refresh(row)
    return _out(row)


async def delete(session: AsyncSession, reply_id: uuid.UUID) -> None:
    await session.delete(await get_or_404(session, reply_id))
    await session.flush()


async def fill_for_conversation(
    session: AsyncSession, reply_id: uuid.UUID, conversation_id: uuid.UUID
) -> str:
    """The reply filled for the conversation's contact. 404 for a reply or conversation that isn't
    this workspace's."""
    row = await get_or_404(session, reply_id)
    conv = await session.scalar(select(Conversation).where(Conversation.id == conversation_id))
    if conv is None:
        raise ApiError("not_found", "That conversation wasn't found.")
    contact = await session.scalar(select(Contact).where(Contact.id == conv.contact_id))
    return fill(row.body, contact_values(contact))


async def flow_text(
    session: AsyncSession, reply_id: uuid.UUID, contact: Contact | None
) -> str | None:
    """A flow step's text at run time: the reply's current body filled for the contact, or None
    when it was deleted."""
    row = await session.scalar(select(SavedReply).where(SavedReply.id == reply_id))
    return None if row is None else fill(row.body, contact_values(contact))
