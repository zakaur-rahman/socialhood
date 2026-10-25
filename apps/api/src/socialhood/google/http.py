"""The real Google client (GR-27): OAuth 2.0 (web server flow, offline access) and the Sheets API
over the shared httpx client.

- Authorise: ``access_type=offline`` and ``prompt=consent`` so Google always returns a refresh
  token; the scope is ``drive.file`` (+ ``openid email``) only.
- Rows are written with ``valueInputOption=RAW``: a customer's answer starting with ``=`` or ``+``
  is stored as text, never run as a formula.
- A response is classified into a ``GoogleError`` kind (client.py); no body is logged or kept,
  because it can carry the person's data.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import httpx

from socialhood.google.client import SCOPES, GoogleError, Grant, SheetInfo
from socialhood.settings import Settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (an address, not a secret)
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"
DEFAULT_TAB = "Leads"


def _kind(status: int) -> GoogleError:
    if status == 401:
        return GoogleError("auth", "Google no longer accepts the access.", status=status)
    if status == 403:
        return GoogleError("forbidden", "Google won't let Amplychat use that sheet.", status=status)
    if status == 404:
        return GoogleError("not_found", "Google can't find that sheet.", status=status)
    if status == 429:
        return GoogleError("rate_limited", "Google asked us to slow down.", status=status)
    if status >= 500:
        return GoogleError("unavailable", "Google isn't responding.", status=status)
    return GoogleError("rejected", "Google refused the request.", status=status)


def _range(tab: str, cells: str) -> str:
    quoted = "'" + tab.replace("'", "''") + "'!" + cells
    return quote(quoted, safe="")


class HttpGoogleClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    # ---------------------------------------------------------------- OAuth

    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._settings.google_client_id or "",
                "redirect_uri": self._settings.google_redirect_uri or "",
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    def _client_secret(self) -> str:
        secret = self._settings.google_client_secret
        return secret.get_secret_value() if secret else ""

    async def _token(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            response = await self._http.post(
                TOKEN_URL,
                data={
                    **data,
                    "client_id": self._settings.google_client_id or "",
                    "client_secret": self._client_secret(),
                },
            )
        except httpx.HTTPError as error:
            raise GoogleError("unavailable", "Google isn't responding.") from error
        if response.status_code == 400:  # invalid_grant: revoked, expired or already used
            raise GoogleError("auth", "Google no longer accepts the access.", status=400)
        if response.status_code >= 400:
            raise _kind(response.status_code)
        body: dict[str, Any] = response.json()
        return body

    async def exchange_code(self, code: str) -> Grant:
        body = await self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.google_redirect_uri or "",
            }
        )
        refresh = body.get("refresh_token")
        if not refresh:  # Google returns it only on a consented offline grant
            raise GoogleError("auth", "Google didn't give long-lived access.")
        email = None
        try:
            info = await self._http.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {body.get('access_token', '')}"}
            )
            if info.status_code == 200:
                email = info.json().get("email")
        except httpx.HTTPError:
            email = None  # the email is only shown; the connection works without it
        scopes = tuple(str(body.get("scope", "")).split())
        return Grant(refresh_token=str(refresh), email=email, scopes=scopes)

    async def access_token(self, refresh_token: str) -> str:
        body = await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        return str(body["access_token"])

    async def revoke(self, refresh_token: str) -> None:
        try:
            await self._http.post(REVOKE_URL, data={"token": refresh_token})
        except httpx.HTTPError:
            return  # best effort: the connection is removed here either way

    # ---------------------------------------------------------------- Sheets

    async def _call(
        self,
        method: str,
        url: str,
        access_token: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(
                method,
                url,
                json=json,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as error:
            raise GoogleError("unavailable", "Google isn't responding.") from error
        if response.status_code >= 400:
            raise _kind(response.status_code)
        body: dict[str, Any] = response.json() if response.content else {}
        return body

    @staticmethod
    def _info(body: dict[str, Any]) -> SheetInfo:
        tabs = body.get("sheets") or []
        tab = tabs[0]["properties"]["title"] if tabs else DEFAULT_TAB
        return SheetInfo(
            spreadsheet_id=str(body["spreadsheetId"]),
            title=str(body.get("properties", {}).get("title", "")),
            url=str(body.get("spreadsheetUrl", "")),
            tab=str(tab),
        )

    async def create_spreadsheet(
        self, access_token: str, title: str, headers: list[str]
    ) -> SheetInfo:
        body = await self._call(
            "POST",
            SHEETS_URL,
            access_token,
            json={
                "properties": {"title": title},
                "sheets": [{"properties": {"title": DEFAULT_TAB}}],
            },
        )
        info = self._info(body)
        await self.write_header(access_token, info.spreadsheet_id, info.tab, headers)
        return info

    async def get_spreadsheet(self, access_token: str, spreadsheet_id: str) -> SheetInfo:
        body = await self._call(
            "GET",
            f"{SHEETS_URL}/{quote(spreadsheet_id, safe='')}",
            access_token,
            params={
                "fields": "spreadsheetId,spreadsheetUrl,properties.title,sheets.properties.title"
            },
        )
        return self._info(body)

    async def write_header(
        self, access_token: str, spreadsheet_id: str, tab: str, headers: list[str]
    ) -> None:
        await self._call(
            "PUT",
            f"{SHEETS_URL}/{quote(spreadsheet_id, safe='')}/values/{_range(tab, 'A1')}",
            access_token,
            params={"valueInputOption": "RAW"},
            json={"values": [headers]},
        )

    async def append_row(
        self, access_token: str, spreadsheet_id: str, tab: str, values: list[str]
    ) -> None:
        await self._call(
            "POST",
            f"{SHEETS_URL}/{quote(spreadsheet_id, safe='')}/values/{_range(tab, 'A1')}:append",
            access_token,
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            json={"values": [values]},
        )
