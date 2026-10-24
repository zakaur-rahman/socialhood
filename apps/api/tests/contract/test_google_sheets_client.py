"""The Google client against Google's documented APIs (GR-27): the OAuth authorize URL and token
exchange (https://developers.google.com/identity/protocols/oauth2/web-server), the Sheets values
append and update (https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values)
and how their answers are classified. respx stands in for Google; no test reaches it."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from pydantic import SecretStr

from socialhood.google.client import GoogleError
from socialhood.google.http import (
    REVOKE_URL,
    SHEETS_URL,
    TOKEN_URL,
    USERINFO_URL,
    HttpGoogleClient,
)
from socialhood.settings import Settings

REDIRECT = "https://api.socialhood.test/v1/oauth/google/callback"
SHEET = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"


@pytest.fixture
def settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(
        update={
            "google_client_id": "client-id.apps.googleusercontent.com",
            "google_client_secret": SecretStr("fake-google-client-secret"),
            "google_redirect_uri": REDIRECT,
        }
    )


@pytest.fixture
async def google(settings: Settings) -> AsyncIterator[HttpGoogleClient]:
    async with httpx.AsyncClient() as http:
        yield HttpGoogleClient(http, settings)


def test_the_authorize_url_asks_for_the_narrow_scope_offline(settings: Settings) -> None:
    client = HttpGoogleClient(httpx.AsyncClient(), settings)
    url = urlsplit(client.authorize_url("state-1"))
    query = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert (url.netloc, url.path) == ("accounts.google.com", "/o/oauth2/v2/auth")
    assert query["scope"] == "https://www.googleapis.com/auth/drive.file openid email"
    assert (query["access_type"], query["prompt"], query["state"]) == (
        "offline",
        "consent",
        "state-1",
    )
    assert query["redirect_uri"] == REDIRECT


@respx.mock
async def test_a_code_is_exchanged_and_the_email_read(google: HttpGoogleClient) -> None:
    token = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "ya29.a",
                "refresh_token": "1//r",
                "scope": "openid email https://www.googleapis.com/auth/drive.file",
            },
        )
    )
    respx.get(USERINFO_URL).mock(return_value=httpx.Response(200, json={"email": "a@b.test"}))

    grant = await google.exchange_code("4/code")

    assert (grant.refresh_token, grant.email) == ("1//r", "a@b.test")
    assert "https://www.googleapis.com/auth/drive.file" in grant.scopes
    sent = parse_qs(token.calls.last.request.content.decode())
    assert sent["grant_type"] == ["authorization_code"]
    assert sent["code"] == ["4/code"]
    assert sent["client_secret"] == ["fake-google-client-secret"]


@respx.mock
async def test_a_grant_without_a_refresh_credential_is_refused(google: HttpGoogleClient) -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "ya29.a"}))
    with pytest.raises(GoogleError) as refused:
        await google.exchange_code("4/code")
    assert refused.value.kind == "auth"


@respx.mock
async def test_a_revoked_refresh_credential_is_auth(google: HttpGoogleClient) -> None:
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(GoogleError) as refused:
        await google.access_token("1//r")
    assert refused.value.kind == "auth"


@respx.mock
async def test_a_row_is_appended_as_raw_text_after_the_last_row(google: HttpGoogleClient) -> None:
    route = respx.post(url__startswith=f"{SHEETS_URL}/{SHEET}/values/").mock(
        return_value=httpx.Response(200, json={"updates": {"updatedRows": 1}})
    )

    await google.append_row("ya29.a", SHEET, "Leads", ["Priya", "=SUM(A1)"])

    request = route.calls.last.request
    assert request.url.path.endswith("/values/'Leads'!A1:append")
    assert request.url.params["valueInputOption"] == "RAW"  # never a formula
    assert request.url.params["insertDataOption"] == "INSERT_ROWS"
    assert json.loads(request.content) == {"values": [["Priya", "=SUM(A1)"]]}
    assert request.headers["authorization"] == "Bearer ya29.a"


@respx.mock
async def test_a_tab_with_a_quote_in_its_name_is_escaped(google: HttpGoogleClient) -> None:
    route = respx.post(url__startswith=f"{SHEETS_URL}/{SHEET}/values/").mock(
        return_value=httpx.Response(200, json={})
    )
    await google.append_row("ya29.a", SHEET, "Ravi's leads", ["x"])
    assert route.calls.last.request.url.path.endswith("/values/'Ravi''s leads'!A1:append")


@respx.mock
async def test_a_new_sheet_gets_its_header_row(google: HttpGoogleClient) -> None:
    respx.post(SHEETS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "spreadsheetId": SHEET,
                "spreadsheetUrl": f"https://docs.google.com/spreadsheets/d/{SHEET}/edit",
                "properties": {"title": "Leads sheet"},
                "sheets": [{"properties": {"title": "Leads"}}],
            },
        )
    )
    header = respx.put(url__startswith=f"{SHEETS_URL}/{SHEET}/values/").mock(
        return_value=httpx.Response(200, json={})
    )

    info = await google.create_spreadsheet("ya29.a", "Leads sheet", ["Name", "Email"])

    assert (info.spreadsheet_id, info.tab, info.title) == (SHEET, "Leads", "Leads sheet")
    assert json.loads(header.calls.last.request.content) == {"values": [["Name", "Email"]]}


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (400, "rejected"),
        (401, "auth"),
        (403, "forbidden"),
        (404, "not_found"),
        (429, "rate_limited"),
        (503, "unavailable"),
    ],
)
@respx.mock
async def test_answers_are_classified(google: HttpGoogleClient, status: int, kind: str) -> None:
    respx.post(url__startswith=f"{SHEETS_URL}/{SHEET}/values/").mock(
        return_value=httpx.Response(status, json={"error": {"message": "secret detail"}})
    )
    with pytest.raises(GoogleError) as failure:
        await google.append_row("ya29.a", SHEET, "Leads", ["x"])
    assert failure.value.kind == kind
    assert "secret detail" not in str(failure.value)  # a body can carry the person's data


@respx.mock
async def test_no_connection_is_unavailable(google: HttpGoogleClient) -> None:
    respx.post(url__startswith=f"{SHEETS_URL}/{SHEET}/values/").mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(GoogleError) as failure:
        await google.append_row("ya29.a", SHEET, "Leads", ["x"])
    assert (failure.value.kind, failure.value.retryable) == ("unavailable", True)


@respx.mock
async def test_revoking_never_raises(google: HttpGoogleClient) -> None:
    respx.post(REVOKE_URL).mock(side_effect=httpx.ConnectError("down"))
    await google.revoke("1//r")
