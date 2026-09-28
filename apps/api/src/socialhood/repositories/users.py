"""User rows. Users are not tenant-scoped, but every write still lives here (TR-TEN-04)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.identity import User


async def get_by_clerk_id(session: AsyncSession, clerk_user_id: str) -> User | None:
    result = await session.scalars(select(User).where(User.clerk_user_id == clerk_user_id))
    return result.one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.scalars(
        select(User).where(func.lower(User.email) == email.lower()).order_by(User.created_at)
    )
    return result.first()


async def insert_if_absent(
    session: AsyncSession,
    *,
    clerk_user_id: str,
    email: str,
    name: str | None,
    avatar_url: str | None,
) -> uuid.UUID | None:
    """Insert the user; return its id, or None if another request inserted it first."""
    statement = (
        insert(User)
        .values(clerk_user_id=clerk_user_id, email=email, name=name, avatar_url=avatar_url)
        .on_conflict_do_nothing(index_elements=[User.clerk_user_id])
        .returning(User.id)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def relink_clerk_id(session: AsyncSession, user_id: uuid.UUID, clerk_user_id: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(clerk_user_id=clerk_user_id)
    )


async def update_profile(
    session: AsyncSession,
    clerk_user_id: str,
    *,
    email: str | None,
    name: str | None,
    avatar_url: str | None,
) -> None:
    values: dict[str, object] = {"name": name, "avatar_url": avatar_url}
    if email:
        values["email"] = email
    await session.execute(update(User).where(User.clerk_user_id == clerk_user_id).values(**values))


async def set_last_workspace(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id, User.last_workspace_id.is_distinct_from(workspace_id))
        .values(last_workspace_id=workspace_id)
    )


async def touch_last_seen(session: AsyncSession, user_id: uuid.UUID, at: datetime) -> None:
    await session.execute(update(User).where(User.id == user_id).values(last_seen_at=at))


async def delete(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Remove a user; memberships and push subscriptions cascade."""
    await session.execute(sa_delete(User).where(User.id == user_id))
