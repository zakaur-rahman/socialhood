"""Which sites may show a workspace's widget (GR-28). Pure functions.

Allowed domains are host names: ``example.com``, ``shop.example.com`` or ``*.example.com`` (the
domain and any subdomain, so one entry covers a business's whole site, C-189). A wildcard on a
shared address (``*.myshopify.com``, ``*.co.uk``) is refused: it would cover everyone's sites, and
the plan counts it as one (C-185). Entries are stored lower case without scheme, port, path or a
trailing dot, so a pasted address (``https://Example.com/contact``) is cleaned, not refused. A
bare domain also covers its ``www.`` form, because the two are the same site to everyone who
types them. ``localhost`` and IP addresses are accepted for testing.

The check is made twice: the frame is served only for an allowed host and carries a
``frame-ancestors`` header naming the allowed sites, which the browser enforces, so a page on
another site cannot show the widget however it is written (services/widget/chat.py repeats the
host check on every call, from the host the visitor token was issued for).
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

MAX_DOMAINS = 20
_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
_HOST = re.compile(rf"^(\*\.)?({_LABEL}\.)*{_LABEL}$")
_PORT = re.compile(r":\d{1,5}$")
BAD_DOMAIN = "Enter a domain like example.com."

# Addresses many unrelated sites share: hosting platforms' and shops' subdomains, and country
# endings people register under. shortcut: a hand-kept list, not the Public Suffix List; move to
# the PSL if someone gets round it with a host that isn't here.
SHARED_HOSTS = frozenset(
    {
        # Shops, site builders and hosting that give every customer a subdomain.
        "myshopify.com",
        "wixsite.com",
        "squarespace.com",
        "webflow.io",
        "framer.website",
        "framer.app",
        "carrd.co",
        "godaddysites.com",
        "square.site",
        "weebly.com",
        "mystrikingly.com",
        "wordpress.com",
        "blogspot.com",
        "tumblr.com",
        "substack.com",
        "notion.site",
        "bigcartel.com",
        "myinstamojo.com",
        "mydukaan.io",
        "vercel.app",
        "netlify.app",
        "github.io",
        "gitlab.io",
        "pages.dev",
        "workers.dev",
        "web.app",
        "firebaseapp.com",
        "herokuapp.com",
        "onrender.com",
        "fly.dev",
        "azurewebsites.net",
        "cloudfront.net",
        "appspot.com",
        "replit.app",
        "glitch.me",
        # Country endings with a second level that anyone registers under.
        "co.uk",
        "org.uk",
        "me.uk",
        "ac.uk",
        "gov.uk",
        "com.au",
        "net.au",
        "org.au",
        "co.in",
        "net.in",
        "org.in",
        "firm.in",
        "gen.in",
        "ind.in",
        "co.nz",
        "co.za",
        "com.br",
        "com.mx",
        "com.sg",
        "com.my",
        "co.jp",
        "co.kr",
        "com.tr",
        "com.ar",
        "com.cn",
        "com.hk",
        "com.tw",
        "com.pk",
        "com.bd",
        "com.ng",
        "co.ke",
        "com.ph",
        "co.id",
        "com.vn",
        "com.eg",
        "com.sa",
        "co.th",
        "com.co",
    }
)


def normalize_domain(value: str) -> str:
    """One allowed-domain entry in its stored form, or ValueError with a sentence to show."""
    raw = value.strip().lower()
    if not raw:
        raise ValueError(BAD_DOMAIN)
    if "://" in raw:
        raw = urlsplit(raw).netloc or ""
    raw = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in raw:
        raw = raw.rsplit("@", 1)[1]
    if raw.startswith("[") and "]" in raw:  # an IPv6 literal, with or without a port
        host = raw[1 : raw.index("]")]
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise ValueError(BAD_DOMAIN) from None
        return host
    host = raw.rsplit(":", 1)[0] if _PORT.search(raw) else raw
    host = host.rstrip(".")
    if len(host) > 253 or not _HOST.fullmatch(host):
        raise ValueError(BAD_DOMAIN)
    if host.startswith("*.") and "." not in host[2:]:
        raise ValueError("A wildcard needs a full domain, like *.example.com.")
    if host.startswith("*.") and host[2:] in SHARED_HOSTS:
        raise ValueError(
            f"{host} covers everyone's sites on {host[2:]}, not just yours. "
            f"Add your own address instead, like yourshop.{host[2:]}."
        )
    return host


def normalize_domains(values: list[str]) -> list[str]:
    """Every entry cleaned, duplicates dropped, order kept."""
    out: list[str] = []
    for value in values:
        domain = normalize_domain(value)
        if domain not in out:
            out.append(domain)
    return out


def host_of(origin_or_url: str | None) -> str | None:
    """The host name of an Origin header or a URL; None for anything that is not http(s)."""
    if not origin_or_url:
        return None
    try:
        parts = urlsplit(origin_or_url.strip())
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host:
        return None
    return host.lower().rstrip(".")


def clean_host(value: str | None) -> str | None:
    """A bare host name as sent by the loader (``location.hostname``), validated."""
    if not value:
        return None
    candidate = value.strip().lower().rstrip(".")
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        pass
    if len(candidate) <= 253 and _HOST.fullmatch(candidate) and not candidate.startswith("*"):
        return candidate
    return None


def host_allowed(host: str | None, domains: list[str]) -> bool:
    """Whether a page on ``host`` may show the widget. An empty list allows nothing."""
    if not host:
        return False
    host = host.lower()
    for entry in domains:
        if entry.startswith("*."):
            if host == entry[2:] or (host.endswith(entry[1:]) and len(host) > len(entry) - 1):
                return True
        elif host == entry or host == f"www.{entry}":
            return True
    return False


def frame_ancestors(domains: list[str]) -> str:
    """The CSP ``frame-ancestors`` value for these domains: https for every site, and http too
    for hosts that cannot have a certificate (localhost, IP addresses). 'none' with no domains."""
    sources: list[str] = []
    for entry in domains:
        if entry.startswith("*."):
            sources.extend((f"https://{entry[2:]}", f"https://{entry}"))
        elif _is_local(entry):
            sources.extend((f"http://{entry}:*", f"https://{entry}:*"))
        else:
            sources.extend((f"https://{entry}", f"https://www.{entry}"))
    return " ".join(sources) if sources else "'none'"


def _is_local(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True
