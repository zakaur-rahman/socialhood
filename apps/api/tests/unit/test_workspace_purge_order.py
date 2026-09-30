"""T9.6: the workspace purge covers every tenant table (the TenantScoped registry) and deletes
children before parents, so no foreign key refuses a delete (FR-ACC-05)."""

from __future__ import annotations

from socialhood.db.tenancy import _tenant_tables
from socialhood.repositories.workspace_deletion import BILLING_TABLES, workspace_tables


def test_every_tenant_table_is_purged() -> None:
    purged = {table.name for table in workspace_tables()}
    registry = {table.name for table in _tenant_tables()}
    assert purged >= registry | BILLING_TABLES


def test_children_are_purged_before_their_parents() -> None:
    tables = workspace_tables()
    position = {table.name: i for i, table in enumerate(tables)}
    for table in tables:
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            if parent in position and parent != table.name and not fk.use_alter:
                assert position[table.name] < position[parent], f"{table.name} -> {parent}"


def test_the_workspace_row_itself_is_not_in_the_batches() -> None:
    assert "workspaces" not in {table.name for table in workspace_tables()}
