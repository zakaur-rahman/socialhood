"""Idempotency-Key for POSTs that send or schedule something (TR-API-05).

Per (workspace, user, key) we keep a fingerprint of the request (method, path and body) and, once
it succeeded, the response, for 24 hours. The same key with the same request returns the stored
response without doing the work again; the same key with a different request is 409
idempotency_conflict. Only successful responses are stored: a request refused by a rule
(window closed, validation) can be sent again with the same key once the problem is fixed.

The record lives in Valkey rather than the idempotency_keys table (there is no migration for it in
P3). Valkey being down never blocks a send: the caller's own dedupe (a message's client_id is
unique per conversation) still stops a double send.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from socialhood.errors import ApiError
from socialhood.observability.logging import get_logger

log = get_logger(__name__)

TTL_S = 24 * 3600
PENDING_TTL_S = 60


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


def fingerprint(method: str, path: str, body: Any) -> str:
    canonical = json.dumps(
        {"method": method.upper(), "path": path, "body": body},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class IdempotencyKey:
    def __init__(
        self,
        redis: Redis,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        key: str,
        fingerprint: str,
    ) -> None:
        self.redis = redis
        self.name = f"idem:{workspace_id}:{user_id}:{key}"
        self.fingerprint = fingerprint

    async def begin(self) -> StoredResponse | None:
        """Claim the key. Returns the stored response of an earlier identical request, or None
        when the caller should do the work. Raises idempotency_conflict for a different request."""
        claim = json.dumps({"fingerprint": self.fingerprint, "state": "pending"})
        try:
            if await self.redis.set(self.name, claim, nx=True, ex=PENDING_TTL_S):
                return None
            raw = await self.redis.get(self.name)
        except Exception:
            log.warning("idempotency_unavailable")
            return None
        if raw is None:  # expired between the two calls
            return None
        record = json.loads(raw)
        if record.get("fingerprint") != self.fingerprint:
            raise ApiError(
                "idempotency_conflict",
                "This Idempotency-Key was already used for a different request.",
            )
        if record.get("state") == "done":
            return StoredResponse(int(record["status_code"]), dict(record["body"]))
        # The same request is still in flight (a double click): doing the work again is safe,
        # because the work itself is deduplicated (for sends, by client_id).
        return None

    async def complete(self, status_code: int, body: dict[str, Any]) -> None:
        record = {
            "fingerprint": self.fingerprint,
            "state": "done",
            "status_code": status_code,
            "body": body,
        }
        try:
            await self.redis.set(self.name, json.dumps(record, default=str), ex=TTL_S)
        except Exception:
            log.warning("idempotency_unavailable")

    async def release(self) -> None:
        """Forget a claim whose request failed, unless another request completed it meanwhile."""
        try:
            raw = await self.redis.get(self.name)
            if raw is not None and json.loads(raw).get("state") == "pending":
                await self.redis.delete(self.name)
        except Exception:
            log.warning("idempotency_unavailable")
