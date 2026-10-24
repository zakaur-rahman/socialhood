"""A sandbox Meta catalogue for tests, development and the end-to-end stack.

It serves the sandbox WhatsApp numbers (``platform_account_id`` starting ``sandbox_``, which only
exist where the sandbox platform is on) and tests. Any catalogue id works, except ``missing``
(refused as ``not_found``) and ``denied`` (refused as ``auth``). Items live in memory per
catalogue: ``items[catalog_id][retailer_id]`` holds what was last sent, so a test can see exactly
what Meta would hold. An item whose ``title`` contains ``[fail]`` is refused by retailer id.
``fail_next(error)`` raises on the next call; every call is recorded in ``calls``.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from socialhood.metacatalog.client import BatchItem, BatchResult, CatalogInfo, CatalogueError


class FakeCatalogue:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, dict[str, Any]]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._failures: deque[CatalogueError] = deque()

    def fail_next(self, error: CatalogueError) -> None:
        self._failures.append(error)

    def _enter(self, name: str, **detail: Any) -> None:
        self.calls.append((name, detail))
        if self._failures:
            raise self._failures.popleft()

    async def get_catalog(self, token: str, catalog_id: str) -> CatalogInfo:
        self._enter("get_catalog", catalog_id=catalog_id)
        if catalog_id == "missing":
            raise CatalogueError("not_found", "Meta can't find that catalogue.")
        if catalog_id == "denied":
            raise CatalogueError("auth", "Meta doesn't let this account use the catalogue.")
        return CatalogInfo(catalog_id, f"Sandbox catalogue {catalog_id}")

    async def push(self, token: str, catalog_id: str, items: list[BatchItem]) -> BatchResult:
        self._enter("push", catalog_id=catalog_id, count=len(items))
        held = self.items.setdefault(catalog_id, {})
        errors: dict[str, str] = {}
        for item in items:
            if item.method == "DELETE":
                held.pop(item.retailer_id, None)
            elif "[fail]" in str(item.data.get("title", "")):
                errors[item.retailer_id] = "Sandbox refused this item."
            else:
                held[item.retailer_id] = dict(item.data)
        return BatchResult(errors)
