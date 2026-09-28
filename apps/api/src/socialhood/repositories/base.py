"""The only sanctioned way to update or delete tenant rows (TR-TEN-02, TR-TEN-04)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Delete, Update, delete, update

from socialhood.db.tenancy import TenantScoped, require_workspace


def _eq(model: type[TenantScoped], where: dict[str, Any]) -> list[ColumnElement[bool]]:
    return [getattr(model, name) == value for name, value in where.items()]


def scoped_update(model: type[TenantScoped], **where: Any) -> Update:
    """UPDATE limited to the current workspace; add ``.values(...)`` before executing."""
    return update(model).where(model.workspace_id == require_workspace(), *_eq(model, where))


def scoped_delete(model: type[TenantScoped], **where: Any) -> Delete:
    return delete(model).where(model.workspace_id == require_workspace(), *_eq(model, where))
