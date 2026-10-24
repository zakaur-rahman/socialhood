"""GR-28: which sites may show the website chat widget, and the cleaning of the domains list."""

from __future__ import annotations

import pytest

from socialhood.services.widget import origin


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("example.com", "example.com"),
        ("  Example.COM  ", "example.com"),
        ("https://www.Example.com/contact?x=1#top", "www.example.com"),
        ("http://example.com:8080/", "example.com"),
        ("example.com:3000", "example.com"),
        ("user@shop.example.com", "shop.example.com"),
        ("*.example.com", "*.example.com"),
        ("example.com.", "example.com"),
        ("localhost", "localhost"),
        ("localhost:3000", "localhost"),
        ("http://127.0.0.1:3000", "127.0.0.1"),
        ("[::1]:8080", "::1"),
    ],
)
def test_a_pasted_address_is_cleaned(typed: str, stored: str) -> None:
    assert origin.normalize_domain(typed) == stored


@pytest.mark.parametrize(
    "typed",
    ["", "   ", "not a domain", "-bad.com", "bad-.com", "a..b", "*.com", "exa mple.com", "//"],
)
def test_a_bad_entry_is_refused_with_a_sentence(typed: str) -> None:
    with pytest.raises(ValueError, match=r"domain|wildcard"):
        origin.normalize_domain(typed)


def test_duplicates_are_dropped_and_order_is_kept() -> None:
    assert origin.normalize_domains(["B.com", "https://a.com/x", "b.com"]) == ["b.com", "a.com"]


@pytest.mark.parametrize(
    ("host", "domains", "allowed"),
    [
        ("example.com", ["example.com"], True),
        ("www.example.com", ["example.com"], True),  # a bare domain covers its www form
        ("shop.example.com", ["example.com"], False),
        ("shop.example.com", ["*.example.com"], True),
        ("a.b.example.com", ["*.example.com"], True),
        ("example.com", ["*.example.com"], False),  # a wildcard is for subdomains only
        ("evilexample.com", ["*.example.com"], False),
        ("example.com.evil.net", ["example.com"], False),
        ("EXAMPLE.com", ["example.com"], True),
        ("example.com", [], False),
        (None, ["example.com"], False),
        ("", ["example.com"], False),
        ("localhost", ["localhost"], True),
    ],
)
def test_which_hosts_are_allowed(host: str | None, domains: list[str], allowed: bool) -> None:
    assert origin.host_allowed(host, domains) is allowed


def test_host_of_reads_origins_and_refuses_other_schemes() -> None:
    assert origin.host_of("https://Shop.Example.com:8443") == "shop.example.com"
    assert origin.host_of("http://localhost:3000/page") == "localhost"
    assert origin.host_of("null") is None
    assert origin.host_of("file:///etc/passwd") is None
    assert origin.host_of(None) is None


def test_the_loaders_host_is_validated() -> None:
    assert origin.clean_host(" Example.com ") == "example.com"
    assert origin.clean_host("127.0.0.1") == "127.0.0.1"
    assert origin.clean_host("[::1]") == "::1"
    assert origin.clean_host("exa mple.com") is None
    assert origin.clean_host("*.example.com") is None
    assert origin.clean_host("a" * 300) is None
    assert origin.clean_host(None) is None


def test_frame_ancestors_names_the_allowed_sites() -> None:
    assert origin.frame_ancestors([]) == "'none'"
    assert origin.frame_ancestors(["example.com"]) == "https://example.com https://www.example.com"
    assert origin.frame_ancestors(["*.example.com"]) == "https://*.example.com"
    local = origin.frame_ancestors(["localhost"])
    assert "http://localhost:*" in local
    assert "http://example.com" not in origin.frame_ancestors(["example.com"])  # https only
