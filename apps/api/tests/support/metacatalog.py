"""Meta catalogue test support (GR-33): every test runs with a FakeCatalogue (never Meta); request
``fake_catalogue`` to see what it holds, or queue a failure."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from socialhood.metacatalog.fake import FakeCatalogue
from socialhood.metacatalog.registry import use_catalogue


@pytest.fixture(autouse=True)
def fake_catalogue() -> Iterator[FakeCatalogue]:
    fake = FakeCatalogue()
    with use_catalogue(fake):
        yield fake
