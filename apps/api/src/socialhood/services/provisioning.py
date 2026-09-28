"""First sign-in (TR-AUTH-03, FR-ACC-02): one user, one personal workspace, however many
requests arrive at once.

The user insert uses ON CONFLICT DO NOTHING on the Clerk id. A second concurrent request blocks
on that unique key until the first commits, gets no row back, and re-reads the user the first
request created, so only one workspace is ever made.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.clerk import ClerkUser
from socialhood.repositories import users, workspaces

SLUG_MIN, SLUG_MAX = 3, 48
_SLUG_ATTEMPTS = 6


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    ascii_text = re.sub(r"['\u2019]", "", ascii_text)  # "Priya's" -> "priyas", not "priya-s"
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:SLUG_MAX].strip("-")
    return slug if len(slug) >= SLUG_MIN else "workspace"


def workspace_name(first_name: str | None) -> str:
    return f"{first_name}'s workspace"[:80] if first_name else "My workspace"


def _with_suffix(base: str) -> str:
    suffix = secrets.token_hex(2)  # 4 hex characters
    return f"{base[: SLUG_MAX - len(suffix) - 1].strip('-')}-{suffix}"


async def provision_user(session: AsyncSession, clerk: ClerkUser) -> uuid.UUID:
    """Return the id of the user for ``clerk``, creating it and its workspace if needed."""
    # Link to an existing account by email only when Clerk has verified that email.
    if clerk.email and clerk.email_verified:
        existing = await users.get_by_email(session, clerk.email)
        if existing is not None and existing.clerk_user_id != clerk.id:
            await users.relink_clerk_id(session, existing.id, clerk.id)
            await session.commit()
            return existing.id

    user_id = await users.insert_if_absent(
        session,
        clerk_user_id=clerk.id,
        email=clerk.email or "",
        name=clerk.name,
        avatar_url=clerk.image_url,
    )
    if user_id is None:
        # Another request created this user (and its workspace) first.
        await session.rollback()
        user = await users.get_by_clerk_id(session, clerk.id)
        if user is None:  # pragma: no cover - the conflicting row committed before we got here
            raise RuntimeError("user vanished after insert conflict")
        return user.id

    workspace_id = await _create_personal_workspace(session, user_id, clerk.first_name)
    await users.set_last_workspace(session, user_id, workspace_id)
    await session.commit()
    return user_id


async def _create_personal_workspace(
    session: AsyncSession, owner_id: uuid.UUID, first_name: str | None
) -> uuid.UUID:
    name = workspace_name(first_name)
    base = slugify(name)
    today = datetime.now(UTC).date()
    for attempt in range(_SLUG_ATTEMPTS):
        slug = base if attempt == 0 else _with_suffix(base)
        workspace, children = workspaces.new_workspace_rows(
            name=name, slug=slug, owner_id=owner_id, today=today
        )
        try:
            async with session.begin_nested():
                session.add(workspace)
                await session.flush()
                session.add_all(children)
                await session.flush()
        except IntegrityError as error:
            if "uq_workspaces_slug" not in str(error.orig):
                raise
            continue
        return workspace.id
    raise RuntimeError("could not find a free workspace slug")
