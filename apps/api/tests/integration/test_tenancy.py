"""TR-TEN-02: tenant tables are filtered by the current workspace, or the query fails.

The models here live in their own schema and metadata, created inside the test transaction and
rolled back, so they never collide with the application's tables.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import ForeignKey, MetaData, String, exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from socialhood.db.base import IdMixin
from socialhood.db.tenancy import (
    TenancyError,
    TenantScoped,
    current_workspace_id,
    tenant_bypass,
    tenant_bypass_scope,
    workspace_scope,
)
from socialhood.repositories.base import scoped_delete, scoped_update

SCHEMA = "tenancy_test"


class TenancyTestBase(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class Workspace(IdMixin, TenancyTestBase):
    __tablename__ = "workspaces"


class Note(IdMixin, TenantScoped, TenancyTestBase):
    __tablename__ = "notes"
    body: Mapped[str] = mapped_column(String(100))


class Comment(IdMixin, TenantScoped, TenancyTestBase):
    __tablename__ = "comments"
    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.notes.id"))


class Plain(IdMixin, TenancyTestBase):
    """A non-tenant table: never filtered."""

    __tablename__ = "plain"


A = uuid.uuid4()
B = uuid.uuid4()


@pytest.fixture
async def seeded(connection: AsyncConnection, session: AsyncSession) -> AsyncSession:
    await connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    await connection.run_sync(TenancyTestBase.metadata.create_all)
    session.add_all([Workspace(id=A), Workspace(id=B)])
    await session.flush()
    session.add_all(
        [
            Note(workspace_id=A, body="a1"),
            Note(workspace_id=A, body="a2"),
            Note(workspace_id=B, body="b1"),
            Plain(),
        ]
    )
    await session.flush()
    session.expunge_all()
    return session


async def test_tenant_query_without_context_raises(seeded: AsyncSession) -> None:
    assert current_workspace_id.get() is None
    with pytest.raises(TenancyError):
        await seeded.execute(select(Note))


async def test_query_with_context_sees_only_its_workspace(seeded: AsyncSession) -> None:
    with workspace_scope(A):
        bodies = sorted((await seeded.scalars(select(Note.body))).all())
        count = await seeded.scalar(select(func.count()).select_from(Note))
        by_id = await seeded.scalars(select(Note).where(Note.body == "b1"))
    assert bodies == ["a1", "a2"]
    assert count == 2
    assert by_id.all() == []  # B's row is invisible even when asked for directly


async def test_counts_subqueries_exists_and_joins_are_filtered(seeded: AsyncSession) -> None:
    with tenant_bypass_scope():
        b_note = (await seeded.scalars(select(Note.id).where(Note.body == "b1"))).one()
    seeded.add(Comment(workspace_id=B, note_id=b_note))
    await seeded.flush()

    with workspace_scope(A):
        assert await seeded.scalar(select(func.count()).select_from(Note)) == 2
        sub = select(Note.id).where(Note.body.like("%1")).subquery()
        assert await seeded.scalar(select(func.count()).select_from(sub)) == 1
        assert await seeded.scalar(select(exists().where(Note.body == "b1"))) is False
        joined = await seeded.scalar(
            select(func.count()).select_from(Comment).join(Note, Comment.note_id == Note.id)
        )
        assert joined == 0


async def test_count_without_context_raises(seeded: AsyncSession) -> None:
    with pytest.raises(TenancyError):
        await seeded.scalar(select(func.count()).select_from(Note))


async def test_non_tenant_tables_are_not_filtered(seeded: AsyncSession) -> None:
    rows = (await seeded.scalars(select(Plain))).all()
    assert len(rows) == 1


async def test_bypass_works_only_inside_its_scope(seeded: AsyncSession) -> None:
    with tenant_bypass_scope():
        assert tenant_bypass.get() is True
        everything = (await seeded.scalars(select(Note.body))).all()
    assert sorted(everything) == ["a1", "a2", "b1"]
    assert tenant_bypass.get() is False
    with pytest.raises(TenancyError):
        await seeded.execute(select(Note))


async def test_bypass_scope_resets_after_an_error(seeded: AsyncSession) -> None:
    with pytest.raises(RuntimeError), tenant_bypass_scope():
        raise RuntimeError("lookup failed")
    assert tenant_bypass.get() is False


async def test_scoped_update_and_delete_touch_only_the_current_workspace(
    seeded: AsyncSession,
) -> None:
    with workspace_scope(A):
        await seeded.execute(scoped_update(Note, body="a1").values(body="changed"))
        await seeded.execute(scoped_update(Note).values(body="all-of-a"))
        deleted = await seeded.execute(scoped_delete(Note, body="b1"))
    assert deleted.rowcount == 0  # type: ignore[attr-defined]
    with tenant_bypass_scope():
        rows = sorted((await seeded.scalars(select(Note.body))).all())
    assert rows == ["all-of-a", "all-of-a", "b1"]


def test_scoped_writes_need_a_workspace() -> None:
    with pytest.raises(TenancyError):
        scoped_update(Note)
    with pytest.raises(TenancyError):
        scoped_delete(Note)
