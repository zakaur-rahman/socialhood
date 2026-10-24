"""The Meta catalogue interface the sync uses (GR-33), and the shapes it speaks in.

Errors are ``CatalogueError`` with a ``kind`` that decides what a sync does:

- ``auth``: the token can't use the catalogue (missing ``catalog_management`` permission, the
  number's access removed, the catalogue not shared with the business): the connection needs
  attention;
- ``not_found``: the catalogue id doesn't exist or isn't visible to this token;
- ``rate_limited`` and ``unavailable``: try again later;
- ``rejected``: Meta refused what was sent and sending it again won't help.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ErrorKind = Literal["auth", "not_found", "rate_limited", "unavailable", "rejected"]
RETRYABLE: frozenset[ErrorKind] = frozenset({"rate_limited", "unavailable"})
BATCH_SIZE = 200  # items per items_batch call (Meta takes up to 5,000)


class CatalogueError(Exception):
    def __init__(self, kind: ErrorKind, message: str = "", *, status: int | None = None) -> None:
        super().__init__(message or kind)
        self.kind: ErrorKind = kind
        self.status = status

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


@dataclass(frozen=True)
class CatalogInfo:
    id: str
    name: str | None


@dataclass(frozen=True)
class BatchItem:
    """One request in an items_batch call: an upsert (``UPDATE`` with ``allow_upsert``) of ``data``
    or a ``DELETE`` of ``data["id"]``."""

    method: Literal["UPDATE", "DELETE"]
    retailer_id: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BatchResult:
    """Items Meta refused, by retailer id and in Meta's words; the rest were accepted."""

    errors: dict[str, str] = field(default_factory=dict)


class CatalogueClient(Protocol):
    async def get_catalog(self, token: str, catalog_id: str) -> CatalogInfo:
        """The catalogue, when the token can see it. Raises ``CatalogueError``."""
        ...

    async def push(self, token: str, catalog_id: str, items: list[BatchItem]) -> BatchResult:
        """Send up to ``BATCH_SIZE`` items and wait for Meta to report on them."""
        ...
