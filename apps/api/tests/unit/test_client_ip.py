"""The client IP behind Render: X-Forwarded-For's rightmost untrusted hop (C-060)."""

from __future__ import annotations

import pytest

from socialhood.security.client_ip import parse_address, rightmost_untrusted

CLIENT = "203.0.113.7"
CF_EDGE = "162.158.12.34"  # Cloudflare
RENDER_LB = "10.204.1.9"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (CLIENT, CLIENT),
        (f"{CLIENT}, {CF_EDGE}", CLIENT),
        (f"{CLIENT}, {CF_EDGE}, {RENDER_LB}", CLIENT),
        # Whatever the client wrote stays on the left and is never the answer.
        (f"198.51.100.1, {CLIENT}, {CF_EDGE}", CLIENT),
        (f"10.0.0.1, 162.158.0.1, {CLIENT}, {CF_EDGE}", CLIENT),
        (f"not-an-ip, {CLIENT}", CLIENT),
        # Ports, brackets and IPv4 inside IPv6.
        (f"{CLIENT}:51234, {CF_EDGE}", CLIENT),
        ("[2001:db8::7]:443, 2606:4700::1", "2001:db8::7"),
        (f"::ffff:{CLIENT}, {CF_EDGE}", CLIENT),
        # Every hop a proxy: the request began inside.
        (f"{RENDER_LB}, {CF_EDGE}", RENDER_LB),
        ("", None),
        (" , ", None),
    ],
)
def test_the_rightmost_untrusted_hop(header: str, expected: str | None) -> None:
    assert rightmost_untrusted(header) == expected


def test_an_entry_that_is_not_an_address_stops_the_walk() -> None:
    assert rightmost_untrusted(f"{CLIENT}, garbage, {CF_EDGE}") == "garbage"
    assert rightmost_untrusted("x" * 500) == "x" * 64


def test_parse_address() -> None:
    assert str(parse_address(" 192.0.2.1 ")) == "192.0.2.1"
    assert str(parse_address("[::1]")) == "::1"
    assert parse_address("unknown") is None
    assert parse_address("") is None
