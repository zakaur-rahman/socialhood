"""Razorpay test support (GR-32): every test runs with a FakeRazorpay (never Razorpay); request
``fake_razorpay`` to see the calls or queue a failure."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from socialhood.razorpay.fake import FakeRazorpay
from socialhood.razorpay.registry import use_razorpay


@pytest.fixture(autouse=True)
def fake_razorpay() -> Iterator[FakeRazorpay]:
    fake = FakeRazorpay()
    with use_razorpay(fake):
        yield fake
