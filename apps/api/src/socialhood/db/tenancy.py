"""Tenant isolation in the ORM (TR-TEN-02).

Every tenant table inherits ``TenantScoped``. A session event adds ``workspace_id = current`` to
every ORM SELECT that touches such a table and raises when no workspace is set. Code that must
look across workspaces (for example, finding the account that owns a webhook) wraps that single
lookup in ``tenant_bypass_scope()``.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import ClauseElement, ForeignKey, Table, event
from sqlalchemy.orm import (
    Mapped,
    ORMExecuteState,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)
from sqlalchemy.sql.util import find_tables

current_workspace_id: ContextVar[uuid.UUID | None] = ContextVar(
    "current_workspace_id", default=None
)
tenant_bypass: ContextVar[bool] = ContextVar("tenant_bypass", default=False)


class TenancyError(RuntimeError):
    """A tenant table was queried without a workspace in context."""


class TenantScoped:
    @declared_attr
    @classmethod
    def workspace_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
        )


def _tenant_tables() -> set[Table]:
    """Tables of every mapped TenantScoped class, however deep the inheritance."""
    tables: set[Table] = set()
    pending = list(TenantScoped.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        table = getattr(cls, "__table__", None)
        if isinstance(table, Table):
            tables.add(table)
    return tables


def _touches_tenant_table(state: ORMExecuteState) -> bool:
    if any(issubclass(m.class_, TenantScoped) for m in state.all_mappers):
        return True
    # all_mappers misses entities that only appear in FROM, such as
    # select(func.count()).select_from(Note), so scan every table the statement uses.
    statement = state.statement
    assert isinstance(statement, ClauseElement)
    used = find_tables(statement, check_columns=True, include_aliases=True)
    return not _tenant_tables().isdisjoint(used)


@event.listens_for(Session, "do_orm_execute")
def _tenant_filter(state: ORMExecuteState) -> None:
    if (
        not state.is_select
        or state.is_column_load
        or state.is_relationship_load
        or tenant_bypass.get()
    ):
        return
    if not _touches_tenant_table(state):
        return
    ws = current_workspace_id.get()
    if ws is None:
        raise TenancyError("tenant query without workspace context")
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantScoped,
            lambda cls: cls.workspace_id == ws,
            include_aliases=True,
        )
    )


def require_workspace() -> uuid.UUID:
    ws = current_workspace_id.get()
    if ws is None:
        raise TenancyError("tenant write without workspace context")
    return ws


@contextmanager
def workspace_scope(workspace_id: uuid.UUID) -> Iterator[None]:
    """Run a block with ``workspace_id`` as the current tenant (jobs, tests)."""
    token = current_workspace_id.set(workspace_id)
    try:
        yield
    finally:
        current_workspace_id.reset(token)


@contextmanager
def tenant_bypass_scope() -> Iterator[None]:
    """Allow one cross-workspace lookup.

    Only webhooks/, jobs/ and auth/ may use this (TR-TEN-04).
    """
    token = tenant_bypass.set(True)
    try:
        yield
    finally:
        tenant_bypass.reset(token)
