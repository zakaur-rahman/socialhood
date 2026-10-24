"""The Google interface Sheets sync uses (GR-27).

Only the narrow ``drive.file`` scope is asked for (plus ``openid email``, to show which Google
account is connected). With ``drive.file`` the app can touch only files it created or that the
person opened with it, so a sheet Social Hood makes always works; an existing sheet works only
if Google has granted the app that file (see docs/CONFLICTS.md, C-100).

Errors are ``GoogleError`` with a ``kind`` that decides what the sync does:

- ``auth``: the refresh credential no longer works (access removed, password changed, the grant
  expired): the connection needs reconnecting;
- ``not_found``: the sheet is gone (deleted, or the app can no longer see it);
- ``forbidden``: Google refuses the app that sheet;
- ``rate_limited`` and ``unavailable``: try again later;
- ``rejected``: Google refused what was sent and sending it again won't help.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

ErrorKind = Literal["auth", "not_found", "forbidden", "rate_limited", "unavailable", "rejected"]
RETRYABLE: frozenset[ErrorKind] = frozenset({"rate_limited", "unavailable"})

SCOPES = (
    "https://www.googleapis.com/auth/drive.file",
    "openid",
    "email",
)


class GoogleError(Exception):
    def __init__(self, kind: ErrorKind, message: str = "", *, status: int | None = None) -> None:
        super().__init__(message or kind)
        self.kind: ErrorKind = kind
        self.status = status

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


@dataclass(frozen=True)
class Grant:
    """What a finished authorisation gives: the long-lived credential and who it is for."""

    refresh_token: str
    email: str | None
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class SheetInfo:
    spreadsheet_id: str
    title: str
    url: str
    tab: str  # the tab rows are added to


class GoogleClient(Protocol):
    def authorize_url(self, state: str) -> str: ...

    async def exchange_code(self, code: str) -> Grant: ...

    async def access_token(self, refresh_token: str) -> str: ...

    async def revoke(self, refresh_token: str) -> None: ...

    async def create_spreadsheet(
        self, access_token: str, title: str, headers: list[str]
    ) -> SheetInfo: ...

    async def get_spreadsheet(self, access_token: str, spreadsheet_id: str) -> SheetInfo: ...

    async def write_header(
        self, access_token: str, spreadsheet_id: str, tab: str, headers: list[str]
    ) -> None: ...

    async def append_row(
        self, access_token: str, spreadsheet_id: str, tab: str, values: list[str]
    ) -> None: ...
