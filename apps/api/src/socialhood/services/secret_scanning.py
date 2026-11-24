"""Leaked-key reports from GitHub's secret scanning partner programme (C-167).

GitHub scans public repositories, gists, issues and the like for our keys' pattern and POSTs
each match to /v1/security/secret-scanning (api/v1/security.py). Owner steps:
docs/security/github-secret-scanning.md.

- **Signature.** The body is signed by GitHub: ``Github-Public-Key-Identifier`` names one of the
  keys at ``KEYS_URL`` and ``Github-Public-Key-Signature`` is the base64 of a DER ECDSA signature
  (P-256, SHA-256) over the raw body. The keys are fetched once and kept for a day; an unknown
  identifier refetches them (at most once a minute, so a forged identifier can't make us hammer
  GitHub). Anything that doesn't verify is 401 and nothing is looked up.
- **Each match** (``[{token, type, url, source}]``) whose token is an ``shk_`` key of ours is
  revoked if it is still on, with an audit row ("revoked: found in a public GitHub repository",
  the URL and where GitHub saw it), and the workspace's owners and admins are told in the app.
  A token that is no key of ours changes nothing.
- **The answer** is GitHub's optional feedback array, ``[{token_hash, token_type, label}]``:
  ``true_positive`` for one of our keys (on or already off), ``false_positive`` otherwise, with
  the token's SHA-256 in hex. Only a verified request gets it, so nobody but GitHub learns
  whether a token is a key.
"""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.api_key import find_key
from socialhood.db.tenancy import workspace_scope
from socialhood.models.api_keys import ApiKey
from socialhood.models.notifications import NotificationType, Severity
from socialhood.observability.logging import get_logger
from socialhood.services import api_keys, notifications

log = get_logger(__name__)

KEYS_URL = "https://api.github.com/meta/public_keys/secret_scanning"
KEYS_KEPT_S = 24 * 3600
REFETCH_EVERY_S = 60
MAX_ALERTS = 1000
AUDIT_LABEL = "GitHub secret scanning"


class Unverified(Exception):
    """The request isn't signed by GitHub (or GitHub's keys can't be had to check it)."""


class SecretAlert(BaseModel):
    """One match in GitHub's payload. Lengths are capped; unknown fields are ignored."""

    token: str = Field(max_length=500)
    type: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=100)


ALERTS = TypeAdapter(list[SecretAlert])


class Feedback(BaseModel):
    token_hash: str
    token_type: str
    label: Literal["true_positive", "false_positive"]


@dataclass
class PublicKeys:
    """GitHub's signing keys, by identifier; refreshed per ``KEYS_KEPT_S`` or on a miss."""

    keys: dict[str, ec.EllipticCurvePublicKey] = field(default_factory=dict)
    fetched_at: float = 0.0

    async def get(self, http: httpx.AsyncClient, key_id: str) -> ec.EllipticCurvePublicKey | None:
        now = time.monotonic()
        stale = now - self.fetched_at > KEYS_KEPT_S
        missing = key_id not in self.keys and now - self.fetched_at > REFETCH_EVERY_S
        if not self.keys or stale or missing:
            await self.refresh(http)
        return self.keys.get(key_id)

    async def refresh(self, http: httpx.AsyncClient) -> None:
        try:
            response = await http.get(
                KEYS_URL, headers={"Accept": "application/vnd.github+json"}, timeout=10.0
            )
            response.raise_for_status()
            listed = response.json().get("public_keys") or []
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            log.warning("secret_scanning_keys_unavailable", error=type(error).__name__)
            if not self.keys:
                raise Unverified("GitHub's keys can't be fetched") from error
            return  # keep the keys we have
        keys: dict[str, ec.EllipticCurvePublicKey] = {}
        for entry in listed:
            try:
                loaded = serialization.load_pem_public_key(str(entry["key"]).encode())
            except (KeyError, TypeError, ValueError):
                continue
            if isinstance(loaded, ec.EllipticCurvePublicKey):
                keys[str(entry["key_identifier"])] = loaded
        self.keys = keys
        self.fetched_at = time.monotonic()


PUBLIC_KEYS = PublicKeys()


async def verify(
    http: httpx.AsyncClient,
    body: bytes,
    key_id: str | None,
    signature: str | None,
    *,
    keys: PublicKeys = PUBLIC_KEYS,
) -> None:
    """Raise ``Unverified`` unless ``signature`` is GitHub's over exactly ``body``."""
    if not key_id or not signature or len(key_id) > 200 or len(signature) > 500:
        raise Unverified("missing signature headers")
    try:
        der = base64.b64decode(signature, validate=True)
    except (binascii.Error, ValueError) as error:
        raise Unverified("the signature isn't base64") from error
    public_key = await keys.get(http, key_id)
    if public_key is None:
        raise Unverified("unknown key identifier")
    try:
        public_key.verify(der, body, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError) as error:
        raise Unverified("the signature doesn't verify") from error


def parse(body: bytes) -> list[SecretAlert]:
    """The verified payload; an empty list for a body that isn't GitHub's shape."""
    try:
        alerts = ALERTS.validate_json(body)
    except ValidationError:
        log.warning("secret_scanning_bad_payload")
        return []
    return alerts[:MAX_ALERTS]


async def handle(
    session: AsyncSession, alerts: list[SecretAlert], *, now: datetime
) -> list[Feedback]:
    """Revoke every key of ours in ``alerts`` and tell its workspace. The caller commits."""
    feedback: list[Feedback] = []
    ours: dict[str, bool] = {}  # a token GitHub lists twice is looked up once
    for alert in alerts:
        token_hash = api_keys.hash_key(alert.token)
        if token_hash not in ours:
            key = await find_key(session, alert.token)
            ours[token_hash] = key is not None
            if key is not None:
                with workspace_scope(key.workspace_id):
                    if key.revoked_at is None:
                        await _revoke_leaked(session, key, alert, now=now)
        feedback.append(
            Feedback(
                token_hash=token_hash,
                token_type=alert.type[:200],
                label="true_positive" if ours[token_hash] else "false_positive",
            )
        )
    found = sum(1 for f in feedback if f.label == "true_positive")
    log.info("secret_scanning_alerts", alerts=len(alerts), ours=found)
    return feedback


async def _revoke_leaked(
    session: AsyncSession, key: ApiKey, alert: SecretAlert, *, now: datetime
) -> None:
    out = await api_keys.revoke(session, key.id, now=now)
    api_keys.audit_revoked(
        session,
        key,
        reason=api_keys.REASON_LEAKED,
        label=AUDIT_LABEL,
        url=alert.url,
        source=alert.source,
    )
    where = f" ({alert.url})" if alert.url else ""
    await notifications.notify_admins(
        session,
        type=NotificationType.API_KEY_LEAKED.value,
        severity=Severity.CRITICAL.value,
        title=f"API key “{out.name}” was found on GitHub"[:200],
        body=(
            f"GitHub found the key {out.key_prefix}… in public{where}, so we revoked it. Make a "
            "new key, put it wherever this one was used, and remove the old one from the "
            "repository's history."
        ),
        link="/settings/ai-apps#api-keys",
        dedupe_key=f"api-key-leaked:{key.id}",
    )
    await session.flush()  # in the key's workspace scope, where its audit row belongs
    log.warning("api_key_leaked_revoked", api_key_id=str(key.id), source=alert.source)
