"""GR-35: the pure rules of a site crawl: robots.txt, sitemaps, address normalisation, the
same-site and excluded-path rules, page links and change detection. No database, no network."""

from __future__ import annotations

import pytest

from socialhood.services.knowledge import crawl_rules as rules

# ---------------------------------------------------------------- robots.txt

ROBOTS = """
# a comment
User-agent: *
Disallow: /private
Disallow: /search?
Allow: /private/open
Crawl-delay: 2

User-agent: SocialHoodBot
Disallow: /drafts
Allow: /drafts/public$
Disallow: /*.pdf$

Sitemap: https://maple.example/sitemap_index.xml
sitemap: https://maple.example/news.xml
"""


def test_our_group_wins_over_the_star_group() -> None:
    robots = rules.parse_robots(ROBOTS)
    assert robots.allows("https://maple.example/private")  # the * group doesn't apply to us
    assert not robots.allows("https://maple.example/drafts/one")
    assert robots.allows("https://maple.example/shop")


def test_the_longest_rule_decides_and_allow_wins_a_tie() -> None:
    robots = rules.parse_robots("User-agent: *\nDisallow: /a\nAllow: /a/b\nDisallow: /a/b/c\n")
    assert not robots.allows("https://x.example/a")
    assert robots.allows("https://x.example/a/b")
    assert not robots.allows("https://x.example/a/b/c/d")
    tie = rules.parse_robots("User-agent: *\nDisallow: /same\nAllow: /same\n")
    assert tie.allows("https://x.example/same")


def test_wildcards_and_the_end_anchor() -> None:
    robots = rules.parse_robots(ROBOTS)
    assert not robots.allows("https://maple.example/files/menu.pdf")
    assert robots.allows("https://maple.example/files/menu.pdf.html")
    assert robots.allows("https://maple.example/drafts/public")  # Allow: /drafts/public$ is longer
    assert not robots.allows("https://maple.example/drafts/public/more")


def test_the_star_group_applies_when_ours_is_missing() -> None:
    robots = rules.parse_robots("User-agent: *\nDisallow: /private\nCrawl-delay: 2\n")
    assert not robots.allows("https://x.example/private/page")
    assert robots.allows("https://x.example/public")
    assert robots.crawl_delay_s == 2.0


def test_sitemap_lines_belong_to_the_file_not_a_group() -> None:
    robots = rules.parse_robots(ROBOTS)
    assert robots.sitemaps == (
        "https://maple.example/sitemap_index.xml",
        "https://maple.example/news.xml",
    )


def test_an_empty_disallow_and_an_empty_file_allow_everything() -> None:
    assert rules.parse_robots("User-agent: *\nDisallow:\n").allows("https://x.example/anything")
    assert rules.parse_robots("").allows("https://x.example/anything")
    assert rules.ALLOW_ALL.allows("https://x.example/anything")


def test_a_disallow_all_blocks_every_page() -> None:
    robots = rules.parse_robots("User-agent: *\nDisallow: /\n")
    assert not robots.allows("https://x.example/")
    assert not robots.allows("https://x.example/a/b")


def test_several_user_agent_lines_share_one_group() -> None:
    robots = rules.parse_robots(
        "User-agent: otherbot\nUser-agent: socialhoodbot\nDisallow: /shared\n"
    )
    assert not robots.allows("https://x.example/shared")


def test_a_bad_crawl_delay_is_ignored() -> None:
    assert rules.parse_robots("User-agent: *\nCrawl-delay: soon\n").crawl_delay_s is None


# ---------------------------------------------------------------- sitemaps


def test_a_sitemap_lists_its_addresses_unescaped() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://maple.example/shipping</loc><lastmod>2026-01-01</lastmod></url>
  <url><loc> https://maple.example/a?x=1&amp;y=2 </loc></url>
  <url><loc><![CDATA[https://maple.example/cdata]]></loc></url>
</urlset>"""
    sitemap = rules.sitemap_urls(xml)
    assert not sitemap.is_index
    assert sitemap.urls == [
        "https://maple.example/shipping",
        "https://maple.example/a?x=1&y=2",
        "https://maple.example/cdata",
    ]


def test_a_sitemap_index_lists_other_sitemaps() -> None:
    xml = b"""<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://maple.example/s1.xml</loc></sitemap>
  <sitemap><loc>https://maple.example/s2.xml</loc></sitemap>
</sitemapindex>"""
    sitemap = rules.sitemap_urls(xml)
    assert sitemap.is_index
    assert sitemap.urls == ["https://maple.example/s1.xml", "https://maple.example/s2.xml"]


def test_an_entity_bomb_is_just_text() -> None:
    xml = b"""<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "aaaaaaaaaa">
<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><urlset><url><loc>&b;</loc></url></urlset>"""
    assert rules.sitemap_urls(xml).urls == ["&b;"]  # never expanded; normalise() then refuses it
    assert rules.normalise("&b;") is None


def test_garbage_gives_no_addresses() -> None:
    assert rules.sitemap_urls(b"\x00\x01 not xml").urls == []


# ---------------------------------------------------------------- addresses


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://Maple.Example/Shop/", "https://maple.example/Shop"),
        ("https://maple.example", "https://maple.example/"),
        ("https://maple.example/a#top", "https://maple.example/a"),
        ("https://maple.example/a?utm_source=x&b=2", "https://maple.example/a"),
        ("https://maple.example:443/a", "https://maple.example/a"),
        ("http://maple.example:80/a", "http://maple.example/a"),
        ("https://maple.example:8443/a", "https://maple.example:8443/a"),
        ("https://maple.example//a///b", "https://maple.example/a/b"),
        ("https://maple.example./a", "https://maple.example/a"),
    ],
)
def test_addresses_have_one_spelling(raw: str, expected: str) -> None:
    assert rules.normalise(raw) == expected


def test_relative_links_resolve_against_the_page() -> None:
    base = "https://maple.example/shop/cakes"
    assert rules.normalise("../about", base) == "https://maple.example/about"
    assert rules.normalise("/contact#form", base) == "https://maple.example/contact"
    assert rules.normalise("//cdn.maple.example/x", base) == "https://cdn.maple.example/x"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "#top",
        "mailto:hello@maple.example",
        "tel:+911234567890",
        "javascript:void(0)",
        "ftp://maple.example/file",
        "https://user:pass@maple.example/",
        "data:text/html,hi",
        "https://maple.example/" + "a" * 1100,
    ],
)
def test_addresses_that_are_not_pages_are_refused(raw: str) -> None:
    assert rules.normalise(raw) is None


def test_the_same_site_ignores_www_but_not_other_hosts() -> None:
    start = "https://maple.example/"
    assert rules.same_site("https://www.maple.example/a", start)
    assert rules.same_site("http://maple.example/a", start)
    assert not rules.same_site("https://blog.maple.example/a", start)
    assert not rules.same_site("https://maple.example.evil.test/a", start)
    assert not rules.same_site("https://evil.test/maple.example", start)
    assert rules.same_site("https://maple.example/a", "https://www.maple.example/")


@pytest.mark.parametrize(
    ("url", "page"),
    [
        ("https://maple.example/menu", True),
        ("https://maple.example/menu.html", True),
        ("https://maple.example/menu.pdf", False),
        ("https://maple.example/photo.JPG", False),
        ("https://maple.example/app.js", False),
        ("https://maple.example/v1.2/notes", True),
    ],
)
def test_files_that_are_not_pages_are_skipped(url: str, page: bool) -> None:
    assert rules.is_page_address(url) is page


def test_excluded_paths_match_a_path_and_what_is_below_it() -> None:
    prefixes = ["/blog", "/shop/old"]
    assert rules.excluded("https://maple.example/blog", prefixes)
    assert rules.excluded("https://maple.example/blog/2026/post", prefixes)
    assert rules.excluded("https://maple.example/shop/old/cake", prefixes)
    assert not rules.excluded("https://maple.example/blogger", prefixes)
    assert not rules.excluded("https://maple.example/shop", prefixes)
    assert not rules.excluded("https://maple.example/blog", [])


@pytest.mark.parametrize(
    ("raw", "prefix"),
    [
        ("/blog", "/blog"),
        ("blog/", "/blog"),
        ("https://maple.example/blog/2026/?page=2#x", "/blog/2026"),
        ("  /a/b/  ", "/a/b"),
        ("/", None),
        ("", None),
        ("https://maple.example/", None),
    ],
)
def test_an_excluded_path_is_cleaned(raw: str, prefix: str | None) -> None:
    assert rules.clean_prefix(raw) == prefix


# ---------------------------------------------------------------- page links


def test_links_are_normalised_deduplicated_and_in_page_order() -> None:
    html = b"""<html><head><base href="https://maple.example/shop/"></head><body>
    <a href="cakes">Cakes</a> <a href="/about#team">About</a> <a href="cakes?utm_source=x">Again</a>
    <a href="mailto:hi@maple.example">Mail</a> <a href="https://other.example/x">Other</a>
    <a href="/old" rel="nofollow">No</a> <a>no href</a></body></html>"""
    links = rules.page_links(html, "https://maple.example/")
    assert links.urls == [
        "https://maple.example/shop/cakes",
        "https://maple.example/about",
        "https://other.example/x",
    ]
    assert not links.noindex
    assert not links.nofollow


def test_robots_meta_is_read() -> None:
    noindex = rules.page_links(
        b'<meta name="robots" content="NoIndex, follow"><a href="/a">a</a>', "https://x.example/"
    )
    assert noindex.noindex
    assert not noindex.nofollow
    nofollow = rules.page_links(
        b'<meta name="robots" content="noindex,nofollow">', "https://x.example/"
    )
    assert nofollow.noindex
    assert nofollow.nofollow
    ours = rules.page_links(b'<meta name="socialhoodbot" content="none">', "https://x.example/")
    assert ours.noindex
    assert ours.nofollow


def test_a_broken_page_keeps_what_was_found() -> None:
    links = rules.page_links(b'<a href="/ok">ok</a><a href="/broken', "https://x.example/")
    assert "https://x.example/ok" in links.urls


# ---------------------------------------------------------------- change detection


def test_the_content_hash_ignores_whitespace_but_not_words() -> None:
    assert rules.content_hash("We ship  to\nthe UAE.") == rules.content_hash("We ship to the UAE. ")
    assert rules.content_hash("We ship to the UAE.") != rules.content_hash("We ship to Qatar.")
