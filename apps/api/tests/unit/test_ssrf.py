"""T5.3: SSRF protection for web-page knowledge (SEC-09). Done when: a URL to 169.254.169.254 is
rejected. Plus loopback and private addresses (literal or by DNS), a redirect to a private
address, too many redirects, non-HTML, oversize pages, and the pinned connection.

DNS is answered by a fake resolver and HTTP by respx: nothing leaves the machine.
"""

from __future__ import annotations

import ipaddress
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest
import respx

from socialhood.security import ssrf
from socialhood.security.ssrf import FetchError, check_url, fetch_html, is_blocked

PUBLIC = "93.184.216.34"
HTML = {"content-type": "text/html; charset=utf-8"}
PAGE = b"<html><head><title>Shipping</title></head><body><p>We ship to the UAE.</p></body></html>"


def resolver(table: dict[str, list[str]]) -> Callable[[str, int], Awaitable[list[str]]]:
    async def resolve(host: str, port: int) -> list[str]:
        if host not in table:
            raise OSError(f"no such host {host}")
        return table[host]

    return resolve


DNS = resolver(
    {
        "maple.example": [PUBLIC],
        "internal.maple.example": ["10.0.0.7"],
        "sneaky.example": [PUBLIC, "127.0.0.1"],
        "localhost": ["127.0.0.1", "::1"],
        "metadata.google.internal": ["169.254.169.254"],
        "mapped.example": ["::ffff:169.254.169.254"],
    }
)


@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",  # cloud metadata (link-local)
        "169.254.170.2",
        "127.0.0.1",
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.1",
        "100.64.0.1",  # shared address space; 100.100.100.200 is a metadata address
        "0.0.0.0",  # noqa: S104
        "224.0.0.1",
        "240.0.0.1",
        "192.0.2.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "fd00:ec2::254",
        "ff02::1",
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "2002:7f00:1::",  # 6to4 wrapping 127.0.0.1
        "::",
    ],
)
def test_private_and_special_addresses_are_blocked(address: str) -> None:
    assert is_blocked(ipaddress.ip_address(address))


@pytest.mark.parametrize("address", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(address: str) -> None:
    assert not is_blocked(ipaddress.ip_address(address))


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("ftp://maple.example/file", "invalid_url"),
        ("file:///etc/passwd", "invalid_url"),
        ("javascript:alert(1)", "invalid_url"),
        ("maple.example/shipping", "invalid_url"),
        ("http://user:secret@maple.example/", "invalid_url"),
        ("http://169.254.169.254/latest/meta-data/", "blocked"),
        ("http://127.0.0.1:8080/admin", "blocked"),
        ("http://[::1]/", "blocked"),
        ("http://10.1.2.3/", "blocked"),
    ],
)
def test_addresses_that_are_refused_before_any_lookup(url: str, code: str) -> None:
    with pytest.raises(FetchError) as caught:
        check_url(url)
    assert caught.value.code == code


def test_a_public_address_passes_the_form_check() -> None:
    assert str(check_url(" https://maple.example/shipping ")) == "https://maple.example/shipping"


async def rejected(url: str) -> FetchError:
    with pytest.raises(FetchError) as caught:
        await fetch_html(url, resolve=DNS)
    return caught.value


@respx.mock
async def test_the_metadata_address_is_rejected_without_a_request() -> None:
    for url in (
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://mapped.example/",
    ):
        error = await rejected(url)
        assert error.code == "blocked"
        assert not error.retryable
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost:8000/",
        "http://10.0.0.7/",
        "http://internal.maple.example/",
        "https://sneaky.example/",  # one public and one loopback answer: refused
    ],
)
async def test_loopback_and_private_addresses_are_rejected(url: str) -> None:
    assert (await rejected(url)).code == "blocked"
    assert not respx.calls


@respx.mock
async def test_a_redirect_to_a_private_address_is_rejected() -> None:
    respx.get(f"https://{PUBLIC}/go").respond(
        302, headers={"location": "http://internal.maple.example/admin"}
    )
    respx.get(f"https://{PUBLIC}/meta").respond(
        301, headers={"location": "http://169.254.169.254/latest/meta-data/"}
    )

    assert (await rejected("https://maple.example/go")).code == "blocked"
    assert (await rejected("https://maple.example/meta")).code == "blocked"
    assert len(respx.calls) == 2  # only the public hops were requested


@respx.mock
async def test_up_to_three_redirects_are_followed_and_each_is_checked() -> None:
    for n in range(1, 4):
        respx.get(f"https://{PUBLIC}/r{n}").respond(302, headers={"location": f"/r{n + 1}"})
    respx.get(f"https://{PUBLIC}/r4").respond(200, headers=HTML, content=PAGE)
    respx.get(f"https://{PUBLIC}/r0").respond(302, headers={"location": "/r1"})

    page = await fetch_html("https://maple.example/r1", resolve=DNS)
    assert page.url == "https://maple.example/r4"
    assert page.content == PAGE

    error = await rejected("https://maple.example/r0")  # four redirects
    assert error.code == "redirects"


@respx.mock
async def test_only_html_is_accepted() -> None:
    respx.get(f"https://{PUBLIC}/menu.pdf").respond(
        200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.7"
    )
    respx.get(f"https://{PUBLIC}/data").respond(200, json={"a": 1})
    respx.get(f"https://{PUBLIC}/bare").respond(200, content=b"<html></html>")

    for path in ("menu.pdf", "data", "bare"):
        error = await rejected(f"https://maple.example/{path}")
        assert error.code == "not_html"
        assert "isn't a web page" in error.message


async def _chunks(total: int, size: int = 64 * 1024) -> AsyncIterator[bytes]:
    sent = 0
    while sent < total:
        yield b"a" * size
        sent += size


@respx.mock
async def test_pages_over_2_mb_are_rejected() -> None:
    respx.get(f"https://{PUBLIC}/declared").respond(
        200, headers=HTML, content=b"<p>" + b"a" * (2 * 1024 * 1024) + b"</p>"
    )
    respx.get(f"https://{PUBLIC}/streamed").mock(
        return_value=httpx.Response(200, headers=HTML, content=_chunks(3 * 1024 * 1024))
    )
    respx.get(f"https://{PUBLIC}/fits").respond(
        200, headers=HTML, content=b"<p>" + b"a" * (2 * 1024 * 1024 - 7) + b"</p>"
    )

    assert (await rejected("https://maple.example/declared")).code == "too_large"
    assert (await rejected("https://maple.example/streamed")).code == "too_large"
    assert len((await fetch_html("https://maple.example/fits", resolve=DNS)).content) == 2 * 1024**2


@respx.mock
async def test_the_connection_goes_to_the_checked_address_under_the_real_name() -> None:
    route = respx.get(f"https://{PUBLIC}:8443/shipping?x=1").respond(
        200, headers=HTML, content=PAGE
    )

    page = await fetch_html("https://maple.example:8443/shipping?x=1", resolve=DNS)

    assert page.content == PAGE
    assert page.content_type == "text/html"
    request = route.calls.last.request
    assert request.headers["host"] == "maple.example:8443"
    assert request.extensions["sni_hostname"] == "maple.example"
    assert "SocialHoodBot" in request.headers["user-agent"]


@respx.mock
async def test_errors_say_whether_a_retry_may_help() -> None:
    respx.get(f"https://{PUBLIC}/gone").respond(404, headers=HTML)
    respx.get(f"https://{PUBLIC}/down").respond(503, headers=HTML)
    respx.get(f"https://{PUBLIC}/slow").mock(side_effect=httpx.ConnectTimeout("slow"))
    respx.get(f"https://{PUBLIC}/refused").mock(side_effect=httpx.ConnectError("refused"))

    gone = await rejected("https://maple.example/gone")
    assert (gone.code, gone.retryable, gone.message) == (
        "http_error",
        False,
        "The page returned an error (404).",
    )
    down = await rejected("https://maple.example/down")
    assert (down.code, down.retryable) == ("http_error", True)
    slow = await rejected("https://maple.example/slow")
    assert (slow.code, slow.retryable) == ("timeout", True)
    refused = await rejected("https://maple.example/refused")
    assert (refused.code, refused.retryable) == ("connect", True)
    unknown = await rejected("https://no-such-host.example/")
    assert (unknown.code, unknown.retryable) == ("dns", False)


def test_the_default_resolver_is_the_system_one() -> None:
    assert ssrf.resolve_host is ssrf.system_resolve
