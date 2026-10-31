"""Who may ask to connect: OAuth clients (C-165 phase C; 01-design.md §3.2 "Registration",
"Redirect URIs allowed"; MCP 2026-07-28 authorization, client registration).

Two ways a client is known:

- **Client ID Metadata Documents (CIMD)**, which Claude and ChatGPT prefer. The ``client_id`` is
  an https URL; we fetch the JSON document it names and check it: its ``client_id`` equals the
  URL exactly, it has a ``client_name`` and ``redirect_uris``, and it authenticates with
  ``none`` (a public client with PKCE). The fetch goes through security/ssrf.py (public
  addresses only, the checked address dialled, no redirects), with a 5 second limit and 5 KB at
  most. A document is re-read when our copy is older than a day; if that fails we keep a copy
  up to a week old, so a client's brief outage doesn't break every connection.
- **Dynamic Client Registration (RFC 7591)**, deprecated by the 2026-07-28 spec and kept for
  clients that don't do CIMD yet (the MCP Inspector, older SDKs, some Codex builds). Its input
  is checked field by field; a client that asks for a secret gets one (only its hash is kept).

Redirect URIs, for both: https (no fragment, no user info), or http on a loopback host
(``localhost``, ``127.0.0.1``, ``[::1]``) for apps on the member's own computer. Matching is
exact, except that a loopback redirect matches on any port (RFC 8252 §7.3), which Claude Code
and Codex need.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.oauth import ClientAuth, ClientKind, OAuthClient
from socialhood.security import ssrf

CIMD_TIMEOUT_S = 5.0
CIMD_MAX_BYTES = 5 * 1024
CIMD_FRESH = timedelta(hours=24)
CIMD_STALE_OK = timedelta(days=7)
DCR_MAX_BYTES = 10 * 1024
MAX_REDIRECT_URIS = 10
MAX_URI_CHARS = 2000
MAX_NAME_CHARS = 100
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]", "::1"})
GRANT_TYPES = frozenset({"authorization_code", "refresh_token"})
SECRET_PREFIX = "shs_"  # noqa: S105  (the start of a generated secret)

Fetcher = Callable[..., Awaitable[ssrf.Page]]


class ClientError(Exception):
    """A client we can't work with. ``code`` is the OAuth error (``invalid_client``,
    ``invalid_request``, ``invalid_redirect_uri``, ``invalid_client_metadata``)."""

    def __init__(self, code: str, description: str) -> None:
        super().__init__(description)
        self.code = code
        self.description = description


# ---------------------------------------------------------------- redirect URIs


def _split(uri: str) -> Any:
    try:
        return urlsplit(uri)
    except ValueError:
        return None


def is_loopback(uri: str) -> bool:
    parts = _split(uri)
    return bool(parts) and parts.scheme == "http" and (parts.hostname or "") in _loopback_names()


def _loopback_names() -> frozenset[str]:
    return frozenset(h.strip("[]") for h in LOOPBACK_HOSTS)


def valid_redirect_uri(uri: object) -> bool:
    """An https URI, or http on a loopback host; no fragment, no user info, at most 2,000
    characters."""
    if not isinstance(uri, str) or not uri or len(uri) > MAX_URI_CHARS or uri != uri.strip():
        return False
    parts = _split(uri)
    if parts is None or not parts.netloc or parts.fragment or "#" in uri:
        return False
    if parts.username is not None or parts.password is not None:
        return False
    try:
        parts.port  # noqa: B018  (raises for a bad port)
    except ValueError:
        return False
    if parts.scheme == "https":
        return bool(parts.hostname)
    return parts.scheme == "http" and (parts.hostname or "") in _loopback_names()


def redirect_matches(registered: list[str], asked: str) -> bool:
    """Exact match, or the same loopback URI on another port (RFC 8252 §7.3)."""
    if asked in registered:
        return True
    if not is_loopback(asked):
        return False
    want = _split(asked)
    for uri in registered:
        if not is_loopback(uri):
            continue
        have = _split(uri)
        if (have.hostname, have.path or "/", have.query) == (
            want.hostname,
            want.path or "/",
            want.query,
        ):
            return True
    return False


def redirect_host(uri: str) -> str:
    parts = _split(uri)
    return (parts.hostname or uri) if parts else uri


def _https_or_none(uri: object) -> str | None:
    """A display URI (logo, home page) we keep only when it's a plain https URL."""
    if not isinstance(uri, str) or len(uri) > MAX_URI_CHARS:
        return None
    parts = _split(uri)
    if parts is None or parts.scheme != "https" or not parts.hostname or parts.username:
        return None
    return uri


def _name(value: object, *, fallback: str | None = None) -> str:
    if isinstance(value, str):
        cleaned = " ".join(value.split())[:MAX_NAME_CHARS]
        if cleaned:
            return cleaned
    if fallback is not None:
        return fallback
    raise ClientError("invalid_client_metadata", "client_name is required.")


def _redirects(value: object, code: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ClientError(code, "redirect_uris must be a list of one or more URIs.")
    if len(value) > MAX_REDIRECT_URIS:
        raise ClientError(code, f"At most {MAX_REDIRECT_URIS} redirect_uris.")
    bad = [str(u)[:100] for u in value if not valid_redirect_uri(u)]
    if bad:
        raise ClientError(
            "invalid_redirect_uri",
            "Redirect URIs must be https, or http on localhost or 127.0.0.1: " + ", ".join(bad),
        )
    return list(dict.fromkeys(value))


# ---------------------------------------------------------------- CIMD


def is_cimd_client_id(client_id: str) -> bool:
    return client_id.startswith("https://")


def check_cimd_url(client_id: str) -> None:
    """The client_id must be an https URL with a path, naming a public host (the document is
    fetched with the SSRF rules too; this refuses the obvious cases without any network)."""
    if len(client_id) > MAX_URI_CHARS:
        raise ClientError("invalid_client", "The client_id is too long.")
    parts = _split(client_id)
    if parts is None or parts.scheme != "https" or not parts.hostname:
        raise ClientError("invalid_client", "A URL client_id must be an https URL.")
    if parts.username is not None or parts.password is not None or parts.fragment:
        raise ClientError("invalid_client", "The client_id URL can't have user info or a fragment.")
    if parts.path in ("", "/") or any(seg in (".", "..") for seg in parts.path.split("/")):
        raise ClientError("invalid_client", "The client_id URL must have a path.")
    host = parts.hostname
    if host in _loopback_names() or host.endswith(".localhost") or "." not in host:
        raise ClientError("invalid_client", "The client_id URL must be on a public host.")
    try:
        ssrf.check_url(client_id)
    except ssrf.FetchError as error:
        raise ClientError(
            "invalid_client", "The client_id URL must be on a public host."
        ) from error


def parse_cimd(client_id: str, content: bytes) -> dict[str, Any]:
    """The metadata a client's document gives, checked (the spec's MUSTs and our rules)."""
    try:
        doc = json.loads(content)
    except (ValueError, UnicodeDecodeError) as error:
        raise ClientError("invalid_client", "The client metadata document isn't JSON.") from error
    if not isinstance(doc, dict):
        raise ClientError("invalid_client", "The client metadata document isn't a JSON object.")
    if doc.get("client_id") != client_id:
        raise ClientError(
            "invalid_client", "The client metadata document's client_id doesn't match its URL."
        )
    method = doc.get("token_endpoint_auth_method", ClientAuth.NONE.value)
    if method != ClientAuth.NONE.value:
        raise ClientError(
            "invalid_client", "Clients identified by a metadata document must use 'none'."
        )
    grants = doc.get("grant_types", ["authorization_code"])
    if not isinstance(grants, list) or "authorization_code" not in grants:
        raise ClientError("invalid_client", "The client must use the authorization_code grant.")
    return {
        "client_name": _name(doc.get("client_name")),
        "redirect_uris": _redirects(doc.get("redirect_uris"), "invalid_client"),
        "client_uri": _https_or_none(doc.get("client_uri")),
        "logo_uri": _https_or_none(doc.get("logo_uri")),
        "software_id": _short(doc.get("software_id")),
        "software_version": _short(doc.get("software_version")),
    }


def _short(value: object) -> str | None:
    return value[:100] if isinstance(value, str) and value else None


async def fetch_cimd(client_id: str, *, fetch: Fetcher | None = None) -> dict[str, Any]:
    check_cimd_url(client_id)
    try:
        page = await (fetch or ssrf.fetch_document)(
            client_id,
            types=frozenset({"application/json"}),
            accept="application/json",
            timeout_s=CIMD_TIMEOUT_S,
            max_bytes=CIMD_MAX_BYTES,
            max_redirects=0,
        )
    except ssrf.FetchError as error:
        raise ClientError(
            "invalid_client", f"Couldn't read the client metadata document ({error.code})."
        ) from error
    return parse_cimd(client_id, page.content)


async def cimd_client(
    session: AsyncSession, client_id: str, now: datetime, *, fetch: Fetcher | None = None
) -> OAuthClient:
    """The client a metadata document describes, from our copy while it's fresh."""
    client = (
        await session.scalars(select(OAuthClient).where(OAuthClient.client_id == client_id))
    ).one_or_none()
    fresh = (
        client is not None
        and client.metadata_fetched_at is not None
        and now - client.metadata_fetched_at < CIMD_FRESH
    )
    if client is not None and fresh:
        return client
    try:
        meta = await fetch_cimd(client_id, fetch=fetch)
    except ClientError:
        if (
            client is not None
            and client.metadata_fetched_at is not None
            and now - client.metadata_fetched_at < CIMD_STALE_OK
        ):
            return client
        raise
    if client is None:
        client = OAuthClient(
            client_id=client_id,
            kind=ClientKind.CIMD.value,
            token_endpoint_auth_method=ClientAuth.NONE.value,
            **meta,
        )
        session.add(client)
    else:
        for name, value in meta.items():
            setattr(client, name, value)
    client.metadata_fetched_at = now
    await session.flush()
    return client


# ---------------------------------------------------------------- DCR


@dataclass(frozen=True)
class Registered:
    client: OAuthClient
    secret: str | None  # shown once, in the registration response


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def register_dcr(session: AsyncSession, body: Mapping[str, Any]) -> Registered:
    """Check an RFC 7591 registration request and add the client (not flushed)."""
    redirect_uris = _redirects(body.get("redirect_uris"), "invalid_redirect_uri")
    method = body.get("token_endpoint_auth_method", ClientAuth.SECRET_BASIC.value)
    if method not in {m.value for m in ClientAuth}:
        raise ClientError(
            "invalid_client_metadata",
            "token_endpoint_auth_method must be none, client_secret_post or client_secret_basic.",
        )
    grants = body.get("grant_types", ["authorization_code"])
    if (
        not isinstance(grants, list)
        or not grants
        or not all(isinstance(g, str) for g in grants)
        or not set(grants) <= GRANT_TYPES
        or "authorization_code" not in grants
    ):
        raise ClientError(
            "invalid_client_metadata",
            "grant_types may be authorization_code and refresh_token only.",
        )
    responses = body.get("response_types", ["code"])
    if not isinstance(responses, list) or responses != ["code"]:
        raise ClientError("invalid_client_metadata", "response_types must be ['code'].")
    raw_name = body.get("client_name")
    if raw_name is not None and not isinstance(raw_name, str):
        raise ClientError("invalid_client_metadata", "client_name must be a string.")
    secret = None if method == ClientAuth.NONE.value else SECRET_PREFIX + secrets.token_urlsafe(32)
    client = OAuthClient(
        client_id="dcr_" + secrets.token_urlsafe(18),
        kind=ClientKind.DCR.value,
        client_name=_name(raw_name, fallback="An unnamed app"),
        redirect_uris=redirect_uris,
        token_endpoint_auth_method=method,
        client_secret_hash=hash_secret(secret) if secret else None,
        client_uri=_https_or_none(body.get("client_uri")),
        # A registered client's logo isn't shown: anyone can register any picture.
        logo_uri=None,
        software_id=_short(body.get("software_id")),
        software_version=_short(body.get("software_version")),
    )
    session.add(client)
    return Registered(client=client, secret=secret)


def registration_response(registered: Registered, issued_at: datetime) -> dict[str, Any]:
    client = registered.client
    out: dict[str, Any] = {
        "client_id": client.client_id,
        "client_id_issued_at": int(issued_at.timestamp()),
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris,
        "token_endpoint_auth_method": client.token_endpoint_auth_method,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    if client.client_uri:
        out["client_uri"] = client.client_uri
    if registered.secret is not None:
        out["client_secret"] = registered.secret
        out["client_secret_expires_at"] = 0
    return out


async def find_client(session: AsyncSession, client_id: str) -> OAuthClient | None:
    return (
        await session.scalars(select(OAuthClient).where(OAuthClient.client_id == client_id))
    ).one_or_none()


def logo_is_shown(client: OAuthClient) -> str | None:
    """The logo the consent page may show: a metadata document's, and only when it's served
    from the document's own host (the host proved it speaks for the client by serving the
    document). Registered clients never get one."""
    if client.kind != ClientKind.CIMD.value or not client.logo_uri:
        return None
    if redirect_host(client.logo_uri) != redirect_host(client.client_id):
        return None
    return client.logo_uri
