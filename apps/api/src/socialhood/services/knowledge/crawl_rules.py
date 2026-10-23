"""The rules of a site crawl, as pure functions (GR-35; SEC-09): no database and no network.

- ``Robots``: robots.txt for our bot. The group that names SocialHoodBot wins over ``*``; the
  longest matching rule decides, Allow beating Disallow at equal length; ``*`` and a closing ``$``
  work in paths; ``Crawl-delay`` and ``Sitemap`` lines are read. An empty or missing file allows
  everything; a file that can't be read (an error other than "not found") is handled by the caller.
- ``sitemap_urls``: the addresses of a sitemap or of a sitemap index, read without an XML parser
  (a sitemap is a list of ``<loc>`` elements, so there is no entity or DTD to attack).
- ``normalise``: the one spelling a page is stored and compared under. Fragments, query strings
  (sort orders, filters, tracking parameters: the usual crawl traps), default ports and a trailing
  slash are dropped, and the host is lowercased.
- ``same_site``: same host, ignoring a leading ``www.``; other hosts and sub-domains are other
  sites.
- ``page_links``: the links of an HTML page that a crawl may follow, and whether it asks not to be
  indexed or followed.
- ``excluded``: a path the owner excluded, as a prefix of a page's path.
- ``content_hash``: what change detection compares.
"""

from __future__ import annotations

import contextlib
import hashlib
import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

BOT_NAME = "socialhoodbot"
MAX_URL_CHARS = 1000
# Pages that aren't web pages: a link to one is never fetched.
SKIPPED_EXTENSIONS = frozenset(
    [
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "zip",
        "rar",
        "gz",
        "tar",
        "7z",
        "dmg",
        "exe",
        "apk",
        "jpg",
        "jpeg",
        "png",
        "gif",
        "webp",
        "svg",
        "ico",
        "bmp",
        "avif",
        "mp3",
        "wav",
        "ogg",
        "mp4",
        "mov",
        "avi",
        "webm",
        "mkv",
        "css",
        "js",
        "json",
        "xml",
        "rss",
        "atom",
        "txt",
        "csv",
        "woff",
        "woff2",
        "ttf",
        "eot",
    ]
)


# ---------------------------------------------------------------- addresses


def normalise(raw: str, base: str | None = None) -> str | None:
    """The canonical http(s) address of ``raw`` (resolved against ``base``), or None when it is
    not a page address: another scheme, no host, user:password, too long."""
    raw = raw.strip()
    if not raw or raw.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
        return None
    try:
        parts = urlsplit(urljoin(base, raw) if base else raw)
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
        return None
    if ":" in host:
        host = f"[{host}]"
    default = 443 if parts.scheme == "https" else 80
    netloc = host if port in (None, default) else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    url = urlunsplit((parts.scheme, netloc, path, "", ""))
    return url if len(url) <= MAX_URL_CHARS else None


def bare_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def same_site(url: str, site_url: str) -> bool:
    return bare_host(url) == bare_host(site_url)


def is_page_address(url: str) -> bool:
    """False for an address that ends in a file type we never read as a page."""
    name = urlsplit(url).path.rsplit("/", 1)[-1]
    if "." not in name:
        return True
    return name.rsplit(".", 1)[-1].lower() not in SKIPPED_EXTENSIONS


def path_of(url: str) -> str:
    return urlsplit(url).path or "/"


def clean_prefix(raw: str) -> str | None:
    """An excluded path as stored: starts with "/", no query, no trailing slash. A full address
    is cut down to its path. None when nothing is left to exclude."""
    value = raw.strip()
    if "://" in value:
        value = urlsplit(value).path
    value = value.split("?", 1)[0].split("#", 1)[0]
    value = "/" + value.strip("/")
    return None if value == "/" else value[:200]


def excluded(url: str, prefixes: list[str]) -> bool:
    """True when the page's path is one of the excluded paths or below one."""
    path = path_of(url)
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def content_hash(text: str) -> str:
    """The hash of a page's extracted text: whitespace differences don't count as a change."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- robots.txt


@dataclass(frozen=True)
class _Rule:
    allow: bool
    pattern: re.Pattern[str]
    length: int


@dataclass(frozen=True)
class Robots:
    rules: tuple[_Rule, ...] = ()
    crawl_delay_s: float | None = None
    sitemaps: tuple[str, ...] = ()

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best: _Rule | None = None
        for rule in self.rules:
            if not rule.pattern.match(target):
                continue
            if (
                best is None
                or rule.length > best.length
                or (rule.length == best.length and rule.allow and not best.allow)
            ):
                best = rule
        return best is None or best.allow


ALLOW_ALL = Robots()


def parse_robots(text: str) -> Robots:
    """robots.txt for SocialHoodBot (our group when present, else ``*``)."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    lines: list[tuple[str, str]] = []
    in_rules = False
    sitemaps: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name, value = field_name.strip().lower(), value.strip()
        if field_name == "user-agent":
            if in_rules:
                groups.append((agents, lines))
                agents, lines, in_rules = [], [], False
            agents.append(value.lower())
        elif field_name in ("allow", "disallow", "crawl-delay"):
            in_rules = True
            lines.append((field_name, value))
        elif field_name == "sitemap" and value:
            sitemaps.append(value)
    if agents or lines:
        groups.append((agents, lines))
    chosen = _group_for(groups, BOT_NAME) or _group_for(groups, "*")
    if chosen is None:
        return Robots(sitemaps=tuple(sitemaps))
    rules: list[_Rule] = []
    delay: float | None = None
    for name, value in chosen:
        if name == "crawl-delay":
            with contextlib.suppress(ValueError):
                delay = max(float(value), 0.0)
        elif value:  # an empty Disallow allows everything: no rule
            rules.append(_Rule(name == "allow", _pattern(value), len(value)))
    return Robots(tuple(rules), delay, tuple(sitemaps))


def _group_for(
    groups: list[tuple[list[str], list[tuple[str, str]]]], agent: str
) -> list[tuple[str, str]] | None:
    found: list[tuple[str, str]] | None = None
    for agents, lines in groups:
        if any((a == "*") if agent == "*" else (a != "*" and a in agent) for a in agents):
            found = (found or []) + lines
    return found


def _pattern(value: str) -> re.Pattern[str]:
    anchored = value.endswith("$")
    body = value[:-1] if anchored else value
    expression = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(expression + ("$" if anchored else ""))


# ---------------------------------------------------------------- sitemaps

_LOC = re.compile(r"<(?:\w+:)?loc\s*>(.*?)</(?:\w+:)?loc\s*>", re.IGNORECASE | re.DOTALL)
_CDATA = re.compile(r"^<!\[CDATA\[(.*)\]\]>$", re.DOTALL)


@dataclass(frozen=True)
class Sitemap:
    urls: list[str]
    is_index: bool  # the addresses are other sitemaps


def sitemap_urls(content: bytes) -> Sitemap:
    """The ``<loc>`` addresses of a sitemap (pages) or a sitemap index (other sitemaps)."""
    text = content.decode("utf-8-sig", errors="replace")
    found: list[str] = []
    for match in _LOC.finditer(text):
        value = match.group(1).strip()
        cdata = _CDATA.match(value)
        found.append(html.unescape(cdata.group(1).strip() if cdata else value))
    return Sitemap(found, "<sitemapindex" in text[:2000].lower())


# ---------------------------------------------------------------- page links


@dataclass
class PageLinks:
    urls: list[str] = field(default_factory=list)
    noindex: bool = False  # <meta name="robots" content="noindex">
    nofollow: bool = False


class _LinkParser(HTMLParser):
    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = page_url
        self.out = PageLinks()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: (value or "") for name, value in attrs}
        if tag == "base" and values.get("href"):
            self.base = urljoin(self.base, values["href"])
        elif tag == "a" and values.get("href"):
            if "nofollow" in values.get("rel", "").lower().split():
                return
            url = normalise(values["href"], self.base)
            if url is not None:
                self.out.urls.append(url)
        elif tag == "meta" and values.get("name", "").lower() in ("robots", BOT_NAME):
            content = values.get("content", "").lower()
            self.out.noindex = self.out.noindex or "noindex" in content or "none" in content
            self.out.nofollow = self.out.nofollow or "nofollow" in content or "none" in content


def page_links(html_bytes: bytes, page_url: str) -> PageLinks:
    """The addresses linked from a page, normalised and in page order without repeats."""
    parser = _LinkParser(page_url)
    try:
        parser.feed(html_bytes.decode("utf-8", errors="replace"))
        parser.close()
    except (ValueError, AssertionError):  # a malformed page: keep what was found
        pass
    parser.out.urls = list(dict.fromkeys(parser.out.urls))
    return parser.out
