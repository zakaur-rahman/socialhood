"""The caller's IP address behind Render's proxies, for per-IP rate limits (TR-API-07, C-060).

Render documents one source for the client address: X-Forwarded-For ("read the client IP from
x-forwarded-for, not from the socket connection"; render.com/articles/how-render-handles-ddos-
attacks, checked 2026-09-30). A request passes Cloudflare and then Render's load balancer. Each
proxy appends the address it received the request from, but a client may send an X-Forwarded-For
of its own, which stays on the left; Render has said it only appends. So the leftmost entry is
whatever the client wrote. The real client is the **rightmost untrusted hop**: reading from the
right, skip every entry that is one of the proxies (Cloudflare's published ranges, and the
private, shared and loopback ranges Render's internal network uses) and take the first that
isn't. A client can add entries only to the left of that, so it can't choose its own key.

True-Client-IP and CF-Connecting-IP are Cloudflare headers Render doesn't document, so they are
not relied on. CLIENT_IP_HEADER can still name such a single-value header on another host; any
header but X-Forwarded-For is used as it is.

Cloudflare's ranges change rarely (https://www.cloudflare.com/ips/); an address missing here
makes a Cloudflare edge look like the client, which merges limits but never lets a client pick
its key.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

FORWARDED_FOR = "x-forwarded-for"
MAX_KEY_CHARS = 64

# https://www.cloudflare.com/ips-v4 and /ips-v6, 2026-09-30.
CLOUDFLARE_RANGES = (
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
)
# Render's load balancers and internal network, and a local proxy.
INTERNAL_RANGES = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
)
TRUSTED_PROXIES: tuple[IPNetwork, ...] = tuple(
    ipaddress.ip_network(cidr) for cidr in CLOUDFLARE_RANGES + INTERNAL_RANGES
)


def parse_address(entry: str) -> IPAddress | None:
    """An address from one X-Forwarded-For entry: ``1.2.3.4``, ``1.2.3.4:5678``, ``::1`` or
    ``[::1]:80``. An IPv4 address inside IPv6 reads as the IPv4 one. None when it isn't one."""
    value = entry.strip()
    if value.startswith("["):
        value = value[1 : value.find("]")] if "]" in value else value
    elif value.count(":") == 1:
        value = value.split(":", 1)[0]
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _trusted(address: IPAddress, proxies: Iterable[IPNetwork]) -> bool:
    return any(address.version == net.version and address in net for net in proxies)


def rightmost_untrusted(
    forwarded_for: str, proxies: Iterable[IPNetwork] = TRUSTED_PROXIES
) -> str | None:
    """The rightmost X-Forwarded-For entry that isn't a trusted proxy. When every entry is a
    proxy's, the leftmost (the request began inside); None for an empty header. An entry that
    isn't an address stops the walk: nothing to its left can be trusted either."""
    entries = [entry.strip() for entry in forwarded_for.split(",") if entry.strip()]
    networks = tuple(proxies)
    for entry in reversed(entries):
        address = parse_address(entry)
        if address is None:
            return entry[:MAX_KEY_CHARS]
        if not _trusted(address, networks):
            return str(address)
    if not entries:
        return None
    first = parse_address(entries[0])
    return str(first) if first is not None else entries[0][:MAX_KEY_CHARS]
