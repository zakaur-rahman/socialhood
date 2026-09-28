"""TR-TEN-04: the CI lint rule catches unsafe writes and bypasses."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_tenancy.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_tenancy", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = load()


def test_update_outside_repositories_fails() -> None:
    source = "from sqlalchemy import update\n\nstmt = update(Note).values(body='x')\n"
    problems = lint.check_source("services/inbox.py", source)
    assert problems
    assert "update() imported outside repositories/" in problems[0]


def test_module_attribute_delete_outside_repositories_fails() -> None:
    source = "import sqlalchemy as sa\n\nstmt = sa.delete(Note)\n"
    assert lint.check_source("services/inbox.py", source)


def test_writes_inside_repositories_pass() -> None:
    source = "from sqlalchemy import delete, update\n"
    assert lint.check_source("repositories/base.py", source) == []


def test_select_is_fine_anywhere() -> None:
    source = "from sqlalchemy import select\n\nstmt = select(Note)\n"
    assert lint.check_source("services/inbox.py", source) == []


def test_bypass_outside_allowed_packages_fails() -> None:
    source = (
        "from socialhood.db.tenancy import tenant_bypass_scope\n\n"
        "with tenant_bypass_scope():\n    pass\n"
    )
    assert lint.check_source("services/inbox.py", source)
    assert lint.check_source("webhooks/instagram.py", source) == []
    assert lint.check_source("jobs/tasks/x.py", source) == []


def test_the_real_source_tree_passes() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "socialhood"
    assert lint.check_tree(root) == []
