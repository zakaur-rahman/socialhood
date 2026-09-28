"""Integration tests run against the migrated test database (fixtures in tests/support/)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _database(migrated_database: None) -> None:
    return None
