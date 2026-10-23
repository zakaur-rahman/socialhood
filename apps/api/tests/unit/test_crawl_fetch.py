"""GR-35: what a site crawl fetches, and that every address goes through the SEC-09 rules.

``fetch_document`` (robots.txt, sitemaps, conditional page requests) and the crawl's single-page
read, with DNS answered by a fake resolver and HTTP by respx: nothing leaves the machine.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from socialhood.security import ssrf
from socialhood.security.ssrf import FetchError, fetch_document
from socialhood.services.knowledge import crawl, crawl_rules
from socialhood.services.knowledge.crawl import _Read, _read_page, _Site, _Todo
from tests.support.knowledge import HOSTS, PUBLIC_IP, fake_dns

TEXT = {"content-type": "text/plain"}
XML = {"content-type": "application/xml"}
HTML = {"content-type": "text/html; charset=utf-8"}
START = "https://maple.example/"
SITE = _Site(start_url=START, excluded=[], seeded=False, cap=25, created_by=None)
LINKED = (
    b"<html><head><title>Cakes</title></head><body><article><h1>Cakes</h1><p>"
    + b"We bake fresh eggless cakes every morning in Pune and deliver them by noon. " * 4
    + b'</p></article><a href="/about">About</a><a href="https://other.example/x">Other</a>'
    + b"</body></html>"
)


@pytest.fixture(autouse=True)
def dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    table = {
        **HOSTS,
        "other.example": [PUBLIC_IP],
        "cloud.example": ["169.254.169.254"],
    }
    monkeypatch.setattr(ssrf, "resolve_host", fake_dns(table))
    return table


async def no_sleep(seconds: float) -> None:
    return None


def todo(url: str, **values: object) -> _Todo:
    fields: dict[str, object] = {
        "page_id": None,
        "url": url,
        "depth": 0,
        "etag": None,
        "last_modified": None,
        "has_text": False,
    }
    return _Todo(**{**fields, **values})  # type: ignore[arg-type]


async def read(
    url: str, robots: crawl_rules.Robots = crawl_rules.ALLOW_ALL, **values: object
) -> _Read:
    return await _read_page(todo(url, **values), SITE, robots, 0.0, no_sleep)


# ---------------------------------------------------------------- fetch_document


@respx.mock
async def test_a_document_of_the_asked_type_is_returned_with_its_validators() -> None:
    route = respx.get(f"https://{PUBLIC_IP}/robots.txt").respond(
        200,
        headers={**TEXT, "etag": '"v1"', "last-modified": "Mon, 01 Jan 2026 00:00:00 GMT"},
        content=b"User-agent: *\nDisallow: /x\n",
    )
    page = await fetch_document(
        "https://maple.example/robots.txt", types=frozenset({"text/plain"}), accept="text/plain"
    )
    assert page.content.startswith(b"User-agent")
    assert page.etag == '"v1"'
    assert page.last_modified == "Mon, 01 Jan 2026 00:00:00 GMT"
    request = route.calls.last.request
    assert request.headers["host"] == "maple.example"
    assert request.headers["accept"] == "text/plain"
    assert request.headers["user-agent"] == ssrf.USER_AGENT


@respx.mock
async def test_a_type_that_was_not_asked_for_is_refused() -> None:
    respx.get(f"https://{PUBLIC_IP}/robots.txt").respond(200, headers=HTML, content=b"<html>")
    with pytest.raises(FetchError) as caught:
        await fetch_document("https://maple.example/robots.txt", types=frozenset({"text/plain"}))
    assert caught.value.code == "not_html"


@respx.mock
async def test_a_conditional_request_sends_validators_and_reads_a_304() -> None:
    route = respx.get(f"https://{PUBLIC_IP}/shipping").respond(304)
    page = await fetch_document(
        "https://maple.example/shipping",
        headers={"If-None-Match": '"v1"', "If-Modified-Since": "Mon, 01 Jan 2026 00:00:00 GMT"},
        not_modified=True,
    )
    assert page.status == 304
    assert page.content == b""
    headers = route.calls.last.request.headers
    assert headers["if-none-match"] == '"v1"'
    assert headers["if-modified-since"] == "Mon, 01 Jan 2026 00:00:00 GMT"


@respx.mock
async def test_the_error_status_is_kept_on_the_error() -> None:
    respx.get(f"https://{PUBLIC_IP}/gone").respond(410)
    with pytest.raises(FetchError) as caught:
        await fetch_document("https://maple.example/gone")
    assert (caught.value.code, caught.value.status, caught.value.retryable) == (
        "http_error",
        410,
        False,
    )


@respx.mock
async def test_the_size_limit_is_the_callers() -> None:
    respx.get(f"https://{PUBLIC_IP}/big.xml").respond(200, headers=XML, content=b"x" * 5000)
    with pytest.raises(FetchError) as caught:
        await fetch_document(
            "https://maple.example/big.xml", types=frozenset({"application/xml"}), max_bytes=1024
        )
    assert caught.value.code == "too_large"
    assert "1 KB" in caught.value.message


# ---------------------------------------------------------------- SSRF: sitemaps and robots


@respx.mock
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/sitemap.xml",
        "http://127.0.0.1/robots.txt",
        "http://[::1]/sitemap.xml",
        "http://10.0.0.7/sitemap.xml",
        "https://intranet.maple.example/sitemap.xml",  # resolves to 10.0.0.7
        "https://cloud.example/robots.txt",  # resolves to the metadata address
    ],
)
async def test_sitemap_and_robots_addresses_on_private_networks_are_refused(url: str) -> None:
    with pytest.raises(FetchError) as caught:
        await fetch_document(url, types=frozenset({"application/xml", "text/plain"}))
    assert caught.value.code == "blocked"
    assert not respx.calls


@respx.mock
async def test_a_sitemap_that_redirects_to_a_private_address_is_refused() -> None:
    respx.get(f"https://{PUBLIC_IP}/sitemap.xml").respond(
        302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
    )
    with pytest.raises(FetchError) as caught:
        await fetch_document(
            "https://maple.example/sitemap.xml", types=frozenset({"application/xml"})
        )
    assert caught.value.code == "blocked"
    assert len(respx.calls) == 1  # the redirect target was never requested


@respx.mock
async def test_the_robots_fetch_of_a_private_site_fails_the_crawl() -> None:
    with pytest.raises(crawl._Abort) as caught:
        await crawl._robots("https://intranet.maple.example/")
    assert caught.value.reason == ssrf.BLOCKED
    assert not respx.calls


@respx.mock
async def test_sitemap_files_on_private_hosts_are_ignored_not_fetched() -> None:
    robots = crawl_rules.parse_robots(
        "Sitemap: http://169.254.169.254/sitemap.xml\nSitemap: https://intranet.maple.example/s.xml\n"
    )
    respx.get(f"https://{PUBLIC_IP}/sitemap.xml").respond(
        200,
        headers=XML,
        content=b"<urlset><url><loc>https://maple.example/a</loc></url>"
        b"<url><loc>https://other.example/b</loc></url>"
        b"<url><loc>http://169.254.169.254/c</loc></url></urlset>",
    )
    found = await crawl._sitemap_pages(SITE, robots, 0.0, no_sleep)
    assert found == ["https://maple.example/a"]  # other sites and private addresses are dropped
    assert len(respx.calls) == 1  # only the public sitemap was requested


@respx.mock
async def test_sitemap_indexes_are_followed_up_to_twenty_files() -> None:
    index = (
        b"<sitemapindex>"
        + b"".join(
            f"<sitemap><loc>https://maple.example/s{n}.xml</loc></sitemap>".encode()
            for n in range(40)
        )
        + b"</sitemapindex>"
    )
    respx.get(f"https://{PUBLIC_IP}/sitemap.xml").respond(200, headers=XML, content=index)
    respx.get(url__regex=rf"https://{PUBLIC_IP}/s\d+\.xml").respond(
        200, headers=XML, content=b"<urlset><url><loc>https://maple.example/p</loc></url></urlset>"
    )
    await crawl._sitemap_pages(SITE, crawl_rules.ALLOW_ALL, 0.0, no_sleep)
    assert len(respx.calls) == crawl.MAX_SITEMAP_FILES


@respx.mock
async def test_sitemap_addresses_stop_at_the_plan_cap() -> None:
    urls = b"".join(f"<url><loc>https://maple.example/p{n}</loc></url>".encode() for n in range(80))
    respx.get(f"https://{PUBLIC_IP}/sitemap.xml").respond(
        200, headers=XML, content=b"<urlset>" + urls + b"</urlset>"
    )
    small = _Site(START, [], False, 10, None)
    found = await crawl._sitemap_pages(small, crawl_rules.ALLOW_ALL, 0.0, no_sleep)
    assert len(found) == 80  # one file is read whole; the caller adds up to the cap
    assert found[0] == "https://maple.example/p0"


@respx.mock
async def test_robots_rules_apply_to_sitemap_addresses() -> None:
    robots = crawl_rules.parse_robots("User-agent: *\nDisallow: /private\n")
    respx.get(f"https://{PUBLIC_IP}/sitemap.xml").respond(
        200,
        headers=XML,
        content=b"<urlset><url><loc>https://maple.example/private/a</loc></url>"
        b"<url><loc>https://maple.example/open</loc></url>"
        b"<url><loc>https://maple.example/menu.pdf</loc></url></urlset>",
    )
    assert await crawl._sitemap_pages(SITE, robots, 0.0, no_sleep) == ["https://maple.example/open"]


# ---------------------------------------------------------------- robots.txt answers


@respx.mock
async def test_a_missing_robots_file_allows_everything() -> None:
    respx.get(f"https://{PUBLIC_IP}/robots.txt").respond(404)
    assert await crawl._robots(START) is crawl_rules.ALLOW_ALL


@respx.mock
async def test_a_robots_file_that_errors_fails_the_crawl_for_now() -> None:
    respx.get(f"https://{PUBLIC_IP}/robots.txt").respond(503)
    with pytest.raises(crawl._Abort) as caught:
        await crawl._robots(START)
    assert caught.value.reason == crawl.ROBOTS_FAILED


# ---------------------------------------------------------------- one page


@respx.mock
async def test_a_page_gives_its_text_title_and_same_site_links() -> None:
    respx.get(f"https://{PUBLIC_IP}/cakes").respond(
        200, headers={**HTML, "etag": '"c1"'}, content=LINKED
    )
    result = await read("https://maple.example/cakes")
    assert result.kind == "read"
    assert result.title == "Cakes"
    assert "eggless cakes" in result.text
    assert result.etag == '"c1"'
    assert result.text_hash == crawl_rules.content_hash(result.text)
    assert "https://maple.example/about" in result.links
    assert "https://other.example/x" in result.links  # filtered when added, not when read


@respx.mock
async def test_a_page_the_robots_file_disallows_is_never_requested() -> None:
    robots = crawl_rules.parse_robots("User-agent: *\nDisallow: /cakes\n")
    result = await read("https://maple.example/cakes", robots)
    assert result.kind == "skipped"
    assert not respx.calls


@respx.mock
async def test_a_page_under_an_excluded_path_is_never_requested() -> None:
    site = _Site(START, ["/cakes"], True, 25, None)
    result = await _read_page(
        todo("https://maple.example/cakes/one"), site, crawl_rules.ALLOW_ALL, 0.0, no_sleep
    )
    assert result.kind == "skipped"
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize("status", [404, 410])
async def test_a_page_that_is_gone_is_marked_gone(status: int) -> None:
    respx.get(f"https://{PUBLIC_IP}/old").respond(status)
    result = await read("https://maple.example/old")
    assert result.kind == "gone"


@respx.mock
async def test_a_server_error_is_tried_twice_then_failed() -> None:
    route = respx.get(f"https://{PUBLIC_IP}/flaky").respond(503)
    result = await read("https://maple.example/flaky")
    assert result.kind == "failed"
    assert route.call_count == 2


@respx.mock
async def test_a_flaky_page_that_recovers_on_the_second_try_is_read() -> None:
    respx.get(f"https://{PUBLIC_IP}/flaky").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, headers=HTML, content=LINKED)]
    )
    assert (await read("https://maple.example/flaky")).kind == "read"


@respx.mock
async def test_a_page_that_is_not_html_is_skipped() -> None:
    respx.get(f"https://{PUBLIC_IP}/menu").respond(
        200, headers={"content-type": "application/pdf"}, content=b"%PDF"
    )
    assert (await read("https://maple.example/menu")).kind == "skipped"


@respx.mock
async def test_a_noindex_page_is_skipped() -> None:
    respx.get(f"https://{PUBLIC_IP}/hidden").respond(
        200, headers=HTML, content=b'<meta name="robots" content="noindex"><p>secret</p>'
    )
    result = await read("https://maple.example/hidden")
    assert result.kind == "skipped"
    assert "indexed" in (result.message or "")


@respx.mock
async def test_a_nofollow_page_is_read_but_its_links_are_not_followed() -> None:
    page = b'<meta name="robots" content="nofollow">' + LINKED
    respx.get(f"https://{PUBLIC_IP}/cakes").respond(200, headers=HTML, content=page)
    result = await read("https://maple.example/cakes")
    assert result.kind == "read"
    assert result.links == []


@respx.mock
async def test_the_depth_limit_stops_following_links() -> None:
    respx.get(f"https://{PUBLIC_IP}/cakes").respond(200, headers=HTML, content=LINKED)
    result = await read("https://maple.example/cakes", depth=crawl.MAX_DEPTH)
    assert result.kind == "read"
    assert result.links == []


@respx.mock
async def test_a_redirect_to_another_site_is_skipped() -> None:
    respx.get(f"https://{PUBLIC_IP}/away").respond(
        302, headers={"location": "https://other.example/landing"}
    )
    respx.get(f"https://{PUBLIC_IP}/landing").respond(200, headers=HTML, content=LINKED)
    result = await read("https://maple.example/away")
    assert result.kind == "skipped"
    assert result.final_url == "https://other.example/landing"


@respx.mock
async def test_a_redirect_within_the_site_reports_the_final_address() -> None:
    respx.get(f"https://{PUBLIC_IP}/old-cakes").respond(
        301, headers={"location": "https://www.maple.example/cakes"}
    )
    respx.get(f"https://{PUBLIC_IP}/cakes").respond(200, headers=HTML, content=LINKED)
    result = await read("https://maple.example/old-cakes")
    assert result.kind == "read"
    assert result.final_url == "https://www.maple.example/cakes"


@respx.mock
async def test_a_redirect_to_a_private_address_fails_without_following_it() -> None:
    respx.get(f"https://{PUBLIC_IP}/moved").respond(
        302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
    )
    result = await read("https://maple.example/moved")
    assert result.kind == "failed"
    assert result.message == "The page redirects to an address that can't be used."
    assert len(respx.calls) == 1


@respx.mock
async def test_a_page_on_a_private_host_fails_without_a_request() -> None:
    result = await read("https://intranet.maple.example/prices")
    assert result.kind == "failed"
    assert result.message == ssrf.BLOCKED
    assert not respx.calls


@respx.mock
async def test_a_page_we_hold_is_asked_for_only_if_it_changed() -> None:
    route = respx.get(f"https://{PUBLIC_IP}/cakes").respond(304)
    result = await read(
        "https://maple.example/cakes",
        etag='"c1"',
        last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
        has_text=True,
    )
    assert result.kind == "unchanged"
    assert result.etag == '"c1"'
    headers = route.calls.last.request.headers
    assert headers["if-none-match"] == '"c1"'
    assert headers["if-modified-since"] == "Mon, 01 Jan 2026 00:00:00 GMT"


@respx.mock
async def test_a_page_we_do_not_hold_is_fetched_unconditionally() -> None:
    route = respx.get(f"https://{PUBLIC_IP}/cakes").respond(200, headers=HTML, content=LINKED)
    await read("https://maple.example/cakes", etag='"c1"', has_text=False)
    assert "if-none-match" not in route.calls.last.request.headers


@respx.mock
async def test_a_page_without_text_fails_and_still_gives_its_links() -> None:
    respx.get(f"https://{PUBLIC_IP}/empty").respond(
        200, headers=HTML, content=b'<html><body><a href="/about"></a></body></html>'
    )
    result = await read("https://maple.example/empty")
    assert result.kind == "failed"
    assert result.links == ["https://maple.example/about"]


@respx.mock
async def test_page_text_is_capped_at_twenty_thousand_characters() -> None:
    paragraphs = b"".join(
        f"<p>Item {n}: the bakery sells fresh cakes and bread every day.</p>".encode()
        for n in range(1200)
    )
    body = b"<article>" + paragraphs + b"</article>"
    respx.get(f"https://{PUBLIC_IP}/long").respond(200, headers=HTML, content=body)
    result = await read("https://maple.example/long")
    assert result.kind == "read"
    assert len(result.text) == crawl.PAGE_TEXT_CHARS


def test_the_pace_is_polite() -> None:
    # The run pauses max(POLITE_DELAY_S, min(Crawl-delay, MAX_DELAY_S)) between two requests.
    assert crawl.POLITE_DELAY_S >= 1.0
    assert crawl.MAX_DELAY_S == 10.0


# ---------------------------------------------------------------- local fixture sites (dev and e2e)


@respx.mock
async def test_local_addresses_are_read_only_where_allow_private_is_on() -> None:
    route = respx.get("http://127.0.0.1:4010/robots.txt").respond(
        200, headers=TEXT, content=b"User-agent: *\n"
    )
    with pytest.raises(FetchError) as caught:
        await fetch_document("http://127.0.0.1:4010/robots.txt", types=frozenset({"text/plain"}))
    assert caught.value.code == "blocked"
    assert not route.called

    page = await fetch_document(
        "http://127.0.0.1:4010/robots.txt", types=frozenset({"text/plain"}), allow_private=True
    )
    assert page.content == b"User-agent: *\n"
    assert route.call_count == 1


@respx.mock
async def test_allow_private_also_lets_a_redirect_stay_local() -> None:
    respx.get("http://localhost:4010/a").respond(
        302, headers={"location": "http://127.0.0.1:4010/b"}
    )
    respx.get("http://127.0.0.1:4010/b").respond(200, headers=HTML, content=LINKED)
    page = await fetch_document("http://localhost:4010/a", allow_private=True)
    assert page.url == "http://127.0.0.1:4010/b"


def test_the_start_address_check_passes_a_local_one_only_when_allowed() -> None:
    with pytest.raises(FetchError):
        ssrf.check_url_or_local("http://127.0.0.1:4010/", False)
    assert str(ssrf.check_url_or_local("http://127.0.0.1:4010/", True)) == "http://127.0.0.1:4010/"
    with pytest.raises(FetchError) as caught:  # other refusals still apply
        ssrf.check_url_or_local("ftp://127.0.0.1/", True)
    assert caught.value.code == "invalid_url"
