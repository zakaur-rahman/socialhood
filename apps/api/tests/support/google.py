"""Google test support (GR-27): every test runs with a FakeGoogle (never Google); request
``fake_google`` to read the sheets' rows, revoke access, delete a sheet or queue a failure."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from socialhood.google.fake import FakeGoogle
from socialhood.google.registry import use_google


@pytest.fixture(autouse=True)
def fake_google() -> Iterator[FakeGoogle]:
    fake = FakeGoogle()
    with use_google(fake):
        yield fake
