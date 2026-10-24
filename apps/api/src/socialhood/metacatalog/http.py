"""The real Meta catalogue client (GR-33): the Catalog Batch API over the shared httpx client.

- ``get_catalog``: ``GET /{catalog_id}?fields=id,name``.
- ``push``: ``POST /{catalog_id}/items_batch`` with ``item_type=PRODUCT_ITEM``, ``allow_upsert``
  true and ``requests`` as ``[{"method": "UPDATE" | "DELETE", "data": {...}}]``, then
  ``GET /{catalog_id}/check_batch_request_status?handle=...`` until Meta reports the batch done
  (a few tries, a second apart) and its errors by retailer id.
- A response is classified into a ``CatalogueError`` kind; no body is logged or kept.

**Unverified against a real catalogue** (C-121). Meta's reference says the batch takes up to 5,000
requests, that ``requests`` and ``item_type`` are required and that ``allow_upsert`` defaults to
true, and that the answer carries ``handles`` and ``validation_status``. Not confirmed: the exact
item fields a commerce catalogue requires (this sends ``id``, ``title``, ``description``,
``availability``, ``condition``, ``price`` as "799.00 INR", ``link``, ``image_link`` and
``brand``), the shape of ``check_batch_request_status``'s answer, and the permission the business
token needs (``catalog_management``, with ``business_management``).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from socialhood.metacatalog.client import BatchItem, BatchResult, CatalogInfo, CatalogueError
from socialhood.settings import Settings

GRAPH = "https://graph.facebook.com"
POLLS = 5
POLL_DELAY_S = 1.0


def _kind(status: int, body: Any) -> CatalogueError:
    code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
    if status in (401, 403) or code in (10, 190, 200, 299):
        return CatalogueError(
            "auth", "Meta doesn't let this account use the catalogue.", status=status
        )
    if status == 404 or code in (100, 803):
        return CatalogueError("not_found", "Meta can't find that catalogue.", status=status)
    if status == 429 or code in (4, 17, 32, 613, 80014):
        return CatalogueError("rate_limited", "Meta asked us to slow down.", status=status)
    if status >= 500:
        return CatalogueError("unavailable", "Meta isn't responding.", status=status)
    return CatalogueError("rejected", "Meta refused the request.", status=status)


class HttpCatalogueClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._version = settings.meta_graph_version

    async def _call(
        self,
        method: str,
        path: str,
        token: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(
                method,
                f"{GRAPH}/{self._version}/{path}",
                params=params,
                data=data,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as error:
            raise CatalogueError("unavailable", "Meta isn't responding.") from error
        try:
            body: Any = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400:
            raise _kind(response.status_code, body)
        if not isinstance(body, dict):
            raise CatalogueError("unavailable", "Meta sent an unreadable answer.")
        return body

    async def get_catalog(self, token: str, catalog_id: str) -> CatalogInfo:
        body = await self._call("GET", catalog_id, token, params={"fields": "id,name"})
        if not body.get("id"):
            raise CatalogueError("not_found", "Meta can't find that catalogue.")
        return CatalogInfo(str(body["id"]), body.get("name"))

    async def push(self, token: str, catalog_id: str, items: list[BatchItem]) -> BatchResult:
        if not items:
            return BatchResult()
        requests = [
            {
                "method": item.method,
                "data": item.data if item.method == "UPDATE" else {"id": item.retailer_id},
            }
            for item in items
        ]
        body = await self._call(
            "POST",
            f"{catalog_id}/items_batch",
            token,
            data={
                "item_type": "PRODUCT_ITEM",
                "allow_upsert": "true",
                "requests": json.dumps(requests),
            },
        )
        errors = self._errors(body.get("validation_status"))
        handles = body.get("handles")
        handle = handles[0] if isinstance(handles, list) and handles else None
        if handle:
            errors.update(await self._poll(token, catalog_id, str(handle)))
        return BatchResult(errors)

    @staticmethod
    def _errors(rows: Any) -> dict[str, str]:
        found: dict[str, str] = {}
        for row in rows if isinstance(rows, list) else []:
            problems = row.get("errors") if isinstance(row, dict) else None
            if problems and isinstance(problems, list) and row.get("retailer_id"):
                first = problems[0]
                found[str(row["retailer_id"])] = str(
                    first.get("message") if isinstance(first, dict) else first
                )[:300]
        return found

    async def _poll(self, token: str, catalog_id: str, handle: str) -> dict[str, str]:
        """Wait (briefly) for the batch to finish. A batch still running after a few tries is left
        to Meta: its items are marked sent, and a refusal would show on the next full pass."""
        for attempt in range(POLLS):
            body = await self._call(
                "GET",
                f"{catalog_id}/check_batch_request_status",
                token,
                params={"handle": handle, "load_ids_of_invalid_requests": "true"},
            )
            rows = body.get("data")
            status = (
                rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
            )
            if str(status.get("status", "")).casefold() in ("finished", "complete", "completed"):
                invalid = status.get("errors") or status.get("invalid_requests")
                return self._errors(invalid)
            if attempt < POLLS - 1:
                await asyncio.sleep(POLL_DELAY_S)
        return {}
