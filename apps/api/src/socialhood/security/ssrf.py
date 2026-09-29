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

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class Page:
    url: str  # the final address, after redirects
    content: bytes
    content_type: str


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
    url = check_url(raw_url)
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
                return await _fetch(client, url, resolve, max_bytes, max_redirects)
        except TimeoutError as error:
            raise FetchError(
                "timeout", "The page took too long to respond.", retryable=True
            ) from error


async def _fetch(
    client: httpx.AsyncClient,
    url: httpx.URL,
    resolve: Resolver | None,
    max_bytes: int,
    max_redirects: int,
) -> Page:
    for hop in range(max_redirects + 1):
        addresses = await public_addresses(url, resolve)
        response = await _connect(client, url, addresses)
        try:
            if response.status_code in REDIRECTS:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("http_error", "The page redirects to nowhere.")
                if hop == max_redirects:
                    raise FetchError("redirects", "The page redirects too many times.")
                try:
                    url = check_url(str(url.join(location)))
                except FetchError as error:
                    raise FetchError(
                        error.code, "The page redirects to an address that can't be used."
                    ) from error
                continue
            return await _read(response, url, max_bytes)
        finally:
            await response.aclose()
    raise FetchError("redirects", "The page redirects too many times.")  # pragma: no cover


async def _connect(
    client: httpx.AsyncClient, url: httpx.URL, addresses: list[str]
) -> httpx.Response:
    """Send the request to a checked address, naming the real host in Host and TLS SNI."""
    host = url.raw_host.decode("ascii")
    headers = {
        "Host": url.netloc.decode("ascii"),
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
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


async def _read(response: httpx.Response, url: httpx.URL, max_bytes: int) -> Page:
    status = response.status_code
    if status >= 400:
        raise FetchError(
            "http_error",
            f"The page returned an error ({status}).",
            retryable=status >= 500 or status == 429,
        )
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in HTML_TYPES:
        raise FetchError(
            "not_html",
            "This address isn't a web page. Add documents as a File source instead.",
        )
    too_large = FetchError("too_large", f"The page is larger than {max_bytes // (1024 * 1024)} MB.")
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
    return Page(url=str(url), content=bytes(body), content_type=content_type)


def _literal_ip(host: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def _default_port(url: httpx.URL) -> int:
    return 443 if url.scheme == "https" else 80
