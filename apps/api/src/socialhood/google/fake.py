"""An in-memory Google for tests and for running without Google (``GOOGLE_PROVIDER=fake``).

- ``authorize_url`` points straight back at the redirect address with ``code=fake-code:<email>``,
  so a browser "signs in" without leaving the app; ``exchange_code`` accepts that code.
- Sheets made through ``create_spreadsheet`` (or ``add_sheet``) hold ``header`` and ``rows``;
  ``rows(id)`` lists what was appended. Like ``drive.file``, the app sees only those: any other
  id is ``not_found``.
- ``revoke_access`` makes every call with that refresh token fail as ``auth``;
  ``delete_sheet`` makes a sheet ``not_found``; ``fail_next(error)`` raises ``error`` on the next
  call (memory mode only). Every call is recorded in ``calls`` (memory mode only).
- With a Redis client the sheets, rows and revoked tokens live there, so the API and the worker
  processes of the end-to-end stack share one Google (and the e2e seed route can read the rows).
  Without one, everything is in this object.
"""

from __future__ import annotations

import itertools
import json
import secrets
from collections import deque
from typing import Any
from urllib.parse import urlencode

from redis.asyncio import Redis

from socialhood.google.client import SCOPES, GoogleError, Grant, SheetInfo

FAKE_EMAIL = "owner@example.com"
CODE_PREFIX = "fake-code:"
REFRESH_PREFIX = "fake-refresh:"
ACCESS_PREFIX = "fake-access:"
SHEET_URL = "https://docs.google.test/spreadsheets/d/"
DEFAULT_TAB = "Leads"
_PREFIX = "fakegoogle"


class FakeGoogle:
    def __init__(
        self,
        redirect_uri: str = "http://localhost:8000/v1/oauth/google/callback",
        *,
        redis: Redis | None = None,
    ) -> None:
        self.redirect_uri = redirect_uri
        self._redis = redis
        self._sheets: dict[str, dict[str, Any]] = {}
        self._rows: dict[str, list[list[str]]] = {}
        self._revoked: set[str] = set()
        self._failures: deque[GoogleError] = deque()
        self._ids = itertools.count(1)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    # ---------------------------------------------------------------- test setup and reads

    def fail_next(self, error: GoogleError) -> None:
        self._failures.append(error)

    async def add_sheet(self, spreadsheet_id: str, title: str = "Existing sheet") -> SheetInfo:
        """A sheet the app can see (as if the person had opened it with the app)."""
        return await self._make(spreadsheet_id, title, [])

    async def rows(self, spreadsheet_id: str) -> list[list[str]]:
        if self._redis is not None:
            raw = await self._redis.lrange(f"{_PREFIX}:rows:{spreadsheet_id}", 0, -1)
            return [json.loads(item) for item in raw]
        return [list(row) for row in self._rows.get(spreadsheet_id, [])]

    async def header(self, spreadsheet_id: str) -> list[str]:
        meta = await self._meta(spreadsheet_id)
        return list(meta["header"]) if meta else []

    async def revoke_access(self, refresh_token: str) -> None:
        if self._redis is not None:
            await self._redis.sadd(f"{_PREFIX}:revoked", refresh_token)
        else:
            self._revoked.add(refresh_token)

    async def delete_sheet(self, spreadsheet_id: str) -> None:
        meta = await self._meta(spreadsheet_id)
        if meta is not None:
            await self._save({**meta, "deleted": True}, spreadsheet_id)

    # ---------------------------------------------------------------- storage

    async def _meta(self, spreadsheet_id: str) -> dict[str, Any] | None:
        if self._redis is not None:
            raw = await self._redis.get(f"{_PREFIX}:sheet:{spreadsheet_id}")
            return json.loads(raw) if raw else None
        return self._sheets.get(spreadsheet_id)

    async def _save(self, meta: dict[str, Any], spreadsheet_id: str) -> None:
        if self._redis is not None:
            await self._redis.set(f"{_PREFIX}:sheet:{spreadsheet_id}", json.dumps(meta))
        else:
            self._sheets[spreadsheet_id] = meta

    async def _is_revoked(self, refresh_token: str) -> bool:
        if self._redis is not None:
            return bool(await self._redis.sismember(f"{_PREFIX}:revoked", refresh_token))
        return refresh_token in self._revoked

    async def _make(self, spreadsheet_id: str, title: str, header: list[str]) -> SheetInfo:
        await self._save(
            {"title": title, "tab": DEFAULT_TAB, "header": header, "deleted": False},
            spreadsheet_id,
        )
        return SheetInfo(spreadsheet_id, title, SHEET_URL + spreadsheet_id, DEFAULT_TAB)

    async def _enter(self, name: str, **args: Any) -> None:
        self.calls.append((name, args))
        if self._failures:
            raise self._failures.popleft()

    async def _checked(self, access_token: str) -> None:
        if not access_token.startswith(ACCESS_PREFIX):
            raise GoogleError("auth", "Google no longer accepts the access.", status=401)
        refresh = access_token.removeprefix(ACCESS_PREFIX)
        if await self._is_revoked(refresh):
            raise GoogleError("auth", "Google no longer accepts the access.", status=401)

    async def _visible(self, spreadsheet_id: str) -> dict[str, Any]:
        meta = await self._meta(spreadsheet_id)
        if meta is None or meta.get("deleted"):
            raise GoogleError("not_found", "Google can't find that sheet.", status=404)
        return meta

    # ---------------------------------------------------------------- the interface

    def authorize_url(self, state: str) -> str:
        code = f"{CODE_PREFIX}{FAKE_EMAIL}"
        return f"{self.redirect_uri}?{urlencode({'code': code, 'state': state})}"

    async def exchange_code(self, code: str) -> Grant:
        await self._enter("exchange_code", code=code)
        if not code.startswith(CODE_PREFIX):
            raise GoogleError("auth", "Google no longer accepts the access.", status=400)
        email = code.removeprefix(CODE_PREFIX)
        return Grant(
            refresh_token=f"{REFRESH_PREFIX}{email}:{secrets.token_hex(4)}",
            email=email,
            scopes=SCOPES,
        )

    async def access_token(self, refresh_token: str) -> str:
        await self._enter("access_token")
        if not refresh_token.startswith(REFRESH_PREFIX) or await self._is_revoked(refresh_token):
            raise GoogleError("auth", "Google no longer accepts the access.", status=400)
        return ACCESS_PREFIX + refresh_token

    async def revoke(self, refresh_token: str) -> None:
        await self._enter("revoke")
        await self.revoke_access(refresh_token)

    async def create_spreadsheet(
        self, access_token: str, title: str, headers: list[str]
    ) -> SheetInfo:
        await self._enter("create_spreadsheet", title=title)
        await self._checked(access_token)
        return await self._make(f"fake-sheet-{secrets.token_hex(6)}", title, list(headers))

    async def get_spreadsheet(self, access_token: str, spreadsheet_id: str) -> SheetInfo:
        await self._enter("get_spreadsheet", spreadsheet_id=spreadsheet_id)
        await self._checked(access_token)
        meta = await self._visible(spreadsheet_id)
        return SheetInfo(spreadsheet_id, meta["title"], SHEET_URL + spreadsheet_id, meta["tab"])

    async def write_header(
        self, access_token: str, spreadsheet_id: str, tab: str, headers: list[str]
    ) -> None:
        await self._enter("write_header", spreadsheet_id=spreadsheet_id)
        await self._checked(access_token)
        meta = await self._visible(spreadsheet_id)
        await self._save({**meta, "header": list(headers)}, spreadsheet_id)

    async def append_row(
        self, access_token: str, spreadsheet_id: str, tab: str, values: list[str]
    ) -> None:
        await self._enter("append_row", spreadsheet_id=spreadsheet_id, values=values)
        await self._checked(access_token)
        await self._visible(spreadsheet_id)
        if self._redis is not None:
            await self._redis.rpush(f"{_PREFIX}:rows:{spreadsheet_id}", json.dumps(values))
        else:
            self._rows.setdefault(spreadsheet_id, []).append(list(values))
