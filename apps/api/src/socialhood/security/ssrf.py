"""Fetching a URL a user gave us without reaching our own network (SEC-09).

``fetch_html`` is the only way server code fetches a user-supplied web address:

- http and https only, no user:password in the address;
- the host name is resolved here and every address it resolves to must be public: private,
  loopback, link-local (which holds the cloud metadata address 169.254.169.254), shared
  (100.64/10), multicast, reserved and unspecified ranges are refused, and IPv4 addresses
  embedded in IPv6 ones are checked too;
- the connection goes to the address that was checked (the request names the host in its Host
  header and TLS server name), so a second DNS answer cannot swap in a private address;
- redirects are followed by hand, at most 3, each one checked like the first address;
- 15 seconds for the whole fetch, at most 2 MB of (decoded) body, and HTML pages only.

Every refusal is a ``FetchError`` with a plain-language message the Knowledge page can show.

``fetch_document`` is ``fetch_html`` for other readable files (a site's robots.txt and sitemaps,
GR-35) and for conditional requests: the same address rules, with the content types, the extra
request headers and the size limit chosen by the caller, and a 304 answer returned as such when
asked for. Every URL a site crawl touches, redirects and sitemap addresses included, goes through
it.

``post_json`` sends an outbound webhook (GR-04) under the same address rules: the checked address,
no redirects followed (a redirect is a failed delivery), a short timeout, and only the status read
back. ``allow_private`` lets development and e2e post to a local receiver; the same flag on
``fetch_document`` lets them crawl a local fixture site (settings: crawl_allow_private).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

MAX_REDIRECTS = 3
TIMEOUT_S = 15.0
MAX_BYTES = 2 * 1024 * 1024
HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
HTML_ACCEPT = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"
REDIRECTS = frozenset({301, 302, 303, 307, 308})
USER_AGENT = "SocialHoodBot/1.0 (+https://socialhood.com/bot)"

# Cloud metadata endpoints. Each already falls in a refused range; listed so the intent is plain.
METADATA = frozenset(
    ipaddress.ip_address(a)
    for a in ("169.254.169.254", "169.254.170.2", "100.100.100.200", "fd00:ec2::254")
)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Awaitable[list[str]]]

BAD_ADDRESS = "Enter a web address that starts with http:// or https://."
BLOCKED = "This address points to a private network. Use a public web page."


class FetchError(Exception):
    """The page could not be fetched; ``message`` is shown to the user. ``retryable`` failures
    (timeouts, connection errors, 5xx) may succeed on a later attempt."""

    def __init__(
        self, code: str, message: str, *, retryable: bool = False, status: int | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status = status  # the HTTP status of an error answer


@dataclass(frozen=True)
class Page:
    url: str  # the final address, after redirects
    content: bytes
    content_type: str
    status: int = 200  # 304 only for a conditional request (``fetch_document(not_modified=True)``)
    etag: str | None = None
    last_modified: str | None = None


def is_blocked(address: IPAddress) -> bool:
    """True for any address that is not a public unicast one (SEC-09)."""
    if isinstance(address, ipaddress.IPv6Address):
        embedded = address.ipv4_mapped or address.sixtofour
        if embedded is None and address.teredo is not None:
            embedded = address.teredo[1]
        if embedded is not None and is_blocked(embedded):
            return True
    return (
        address in METADATA
        or not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def check_url(raw: str) -> httpx.URL:
    """The address parsed, when its form is acceptable: http(s), a host, no credentials, and not
    a literal private address. Name resolution happens when it is fetched."""
    try:
        url = httpx.URL(raw.strip())
    except (httpx.InvalidURL, ValueError) as error:
        raise FetchError("invalid_url", BAD_ADDRESS) from error
    if url.scheme not in ("http", "https") or not url.host:
        raise FetchError("invalid_url", BAD_ADDRESS)
    if url.userinfo:
        raise FetchError("invalid_url", "Remove the user name and password from the address.")
    literal = _literal_ip(url.host)
    if literal is not None and is_blocked(literal):
        raise FetchError("blocked", BLOCKED)
    return url


def check_url_or_local(raw: str, allow_private: bool) -> httpx.URL:
    """``check_url``, except that a private address passes where ``allow_private`` is on."""
    try:
        return check_url(raw)
    except FetchError as error:
        if not (allow_private and error.code == "blocked"):
            raise
        return httpx.URL(raw.strip())


async def system_resolve(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


# Tests replace this to answer DNS without the network.
resolve_host: Resolver = system_resolve


async def public_addresses(url: httpx.URL, resolve: Resolver | None = None) -> list[str]:
    """Every address the host resolves to, all of them public, else FetchError."""
    host = url.raw_host.decode("ascii")
    literal = _literal_ip(url.host)
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            addresses = await (resolve or resolve_host)(host, url.port or _default_port(url))
        except (OSError, UnicodeError) as error:
            raise FetchError("dns", "Couldn't find this website. Check the address.") from error
    if not addresses:
        raise FetchError("dns", "Couldn't find this website. Check the address.")
    for address in addresses:
        parsed = _literal_ip(address)
        if parsed is None or is_blocked(parsed):
            raise FetchError("blocked", BLOCKED)
    return addresses


async def fetch_html(
    raw_url: str,
    *,
    resolve: Resolver | None = None,
    timeout_s: float = TIMEOUT_S,
    max_bytes: int = MAX_BYTES,
    max_redirects: int = MAX_REDIRECTS,
) -> Page:
    """Fetch one HTML page under the SEC-09 rules above."""
    return await fetch_document(
        raw_url,
        resolve=resolve,
        timeout_s=timeout_s,
        max_bytes=max_bytes,
        max_redirects=max_redirects,
    )


@dataclass(frozen=True)
class _Request:
    types: frozenset[str]
    accept: str
    headers: dict[str, str]
    not_modified: bool
    max_bytes: int
    allow_private: bool = False


async def fetch_document(
    raw_url: str,
    *,
    types: frozenset[str] = HTML_TYPES,
    accept: str = HTML_ACCEPT,
    headers: dict[str, str] | None = None,
    not_modified: bool = False,
    allow_private: bool = False,
    resolve: Resolver | None = None,
    timeout_s: float = TIMEOUT_S,
    max_bytes: int = MAX_BYTES,
    max_redirects: int = MAX_REDIRECTS,
) -> Page:
    """Fetch one document whose content type is in ``types`` under the SEC-09 rules above.
    ``headers`` are added to the request (If-None-Match and If-Modified-Since); with
    ``not_modified`` a 304 answer comes back as a ``Page`` with status 304 and no content.
    ``allow_private`` (development and e2e only) skips the address checks."""
    url = check_url_or_local(raw_url, allow_private)
    request = _Request(types, accept, headers or {}, not_modified, max_bytes, allow_private)
    # A fresh client per fetch: no proxies from the environment (they would bypass the address
    # check), no redirects followed for us, and no connection reused across host names.
    async with httpx.AsyncClient(
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(timeout_s),
        limits=httpx.Limits(max_keepalive_connections=0),
    ) as client:
        try:
            async with asyncio.timeout(timeout_s):
                return await _fetch(client, url, resolve, request, max_redirects)
        except TimeoutError as error:
            raise FetchError(
                "timeout", "The page took too long to respond.", retryable=True
            ) from error


async def _fetch(
    client: httpx.AsyncClient,
    url: httpx.URL,
    resolve: Resolver | None,
    request: _Request,
    max_redirects: int,
) -> Page:
    for hop in range(max_redirects + 1):
        addresses = [url.host] if request.allow_private else await public_addresses(url, resolve)
        response = await _connect(client, url, addresses, request)
        try:
            if response.status_code in REDIRECTS:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("http_error", "The page redirects to nowhere.")
                if hop == max_redirects:
                    raise FetchError("redirects", "The page redirects too many times.")
                try:
                    url = check_url_or_local(str(url.join(location)), request.allow_private)
                except FetchError as error:
                    raise FetchError(
                        error.code, "The page redirects to an address that can't be used."
                    ) from error
                continue
            return await _read(response, url, request)
        finally:
            await response.aclose()
    raise FetchError("redirects", "The page redirects too many times.")  # pragma: no cover


async def _connect(
    client: httpx.AsyncClient, url: httpx.URL, addresses: list[str], fetch: _Request
) -> httpx.Response:
    """Send the request to a checked address, naming the real host in Host and TLS SNI."""
    host = url.raw_host.decode("ascii")
    headers = {
        **fetch.headers,
        "Host": url.netloc.decode("ascii"),
        "User-Agent": USER_AGENT,
        "Accept": fetch.accept,
    }
    extensions = {"sni_hostname": host} if url.scheme == "https" else {}
    last: httpx.TransportError | None = None
    for address in addresses:
        request = client.build_request(
            "GET", url.copy_with(host=address), headers=headers, extensions=extensions
        )
        try:
            return await client.send(request, stream=True)
        except httpx.ConnectError as error:
            last = error  # try the host's next address
        except httpx.TimeoutException as error:
            raise FetchError(
                "timeout", "The page took too long to respond.", retryable=True
            ) from error
        except httpx.TransportError as error:
            raise FetchError(
                "connect", "Couldn't connect to this website.", retryable=True
            ) from error
    raise FetchError("connect", "Couldn't connect to this website.", retryable=True) from last


async def _read(response: httpx.Response, url: httpx.URL, fetch: _Request) -> Page:
    status = response.status_code
    max_bytes = fetch.max_bytes
    if status == 304 and fetch.not_modified:
        return Page(url=str(url), content=b"", content_type="", status=304)
    if status >= 400:
        raise FetchError(
            "http_error",
            f"The page returned an error ({status}).",
            retryable=status >= 500 or status == 429,
            status=status,
        )
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in fetch.types:
        raise FetchError(
            "not_html",
            "This address isn't a web page. Add documents as a File source instead.",
        )
    too_large = FetchError("too_large", f"The page is larger than {_megabytes(max_bytes)}.")
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise too_large
    body = bytearray()
    try:
        async for part in response.aiter_bytes():
            body.extend(part)
            if len(body) > max_bytes:
                raise too_large
    except httpx.TimeoutException as error:
        raise FetchError("timeout", "The page took too long to respond.", retryable=True) from error
    except httpx.TransportError as error:
        raise FetchError("connect", "The page stopped loading.", retryable=True) from error
    return Page(
        url=str(url),
        content=bytes(body),
        content_type=content_type,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )


def _megabytes(size: int) -> str:
    return f"{size // (1024 * 1024)} MB" if size >= 1024 * 1024 else f"{max(size // 1024, 1)} KB"


@dataclass(frozen=True)
class Posted:
    status: int
    duration_ms: int


async def post_json(
    raw_url: str,
    body: bytes,
    headers: dict[str, str],
    *,
    timeout_s: float = 10.0,
    allow_private: bool = False,
    resolve: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Posted:
    """POST ``body`` to a user's endpoint; FetchError when it can't be reached. Any status comes
    back as ``Posted`` (the caller decides what counts as delivered). ``transport`` is for tests."""
    try:
        url = check_url(raw_url)
    except FetchError as error:
        if not (allow_private and error.code == "blocked"):
            raise
        url = httpx.URL(raw_url.strip())
    addresses = [url.host] if allow_private else await public_addresses(url, resolve)
    async with httpx.AsyncClient(
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(timeout_s),
        limits=httpx.Limits(max_keepalive_connections=0),
        transport=transport,
    ) as client:
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            async with asyncio.timeout(timeout_s):
                response = await _post(client, url, addresses, body, headers)
        except TimeoutError as error:
            raise FetchError("timeout", "The endpoint took too long to respond.") from error
        await response.aclose()
        return Posted(response.status_code, round((loop.time() - started) * 1000))


async def _post(
    client: httpx.AsyncClient,
    url: httpx.URL,
    addresses: list[str],
    body: bytes,
    headers: dict[str, str],
) -> httpx.Response:
    host = url.raw_host.decode("ascii")
    sent = {
        **headers,
        "Host": url.netloc.decode("ascii"),
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }
    extensions = {"sni_hostname": host} if url.scheme == "https" else {}
    last: httpx.TransportError | None = None
    for address in addresses:
        target = url if address == url.host else url.copy_with(host=address)
        request = client.build_request(
            "POST", target, headers=sent, content=body, extensions=extensions
        )
        try:
            return await client.send(request, stream=True)
        except httpx.ConnectError as error:
            last = error
        except httpx.TimeoutException as error:
            raise FetchError("timeout", "The endpoint took too long to respond.") from error
        except httpx.TransportError as error:
            raise FetchError("connect", "Couldn't connect to the endpoint.") from error
    raise FetchError("connect", "Couldn't connect to the endpoint.") from last


def _literal_ip(host: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def _default_port(url: httpx.URL) -> int:
    return 443 if url.scheme == "https" else 80
